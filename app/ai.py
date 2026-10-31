"""AI investigation reports through the Gemini API, with a deterministic fallback.

Model identifier : GEMINI_MODEL, default "gemma-4-26b-a4b-it" (any Gemini API model id works,
                   e.g. "gemma-4-31b-it" or a "gemini-*" model)
Inference path   : UI "Run AI investigation" -> POST /api/valves/{id}/reports (app/api.py)
                   -> diagnose() -> _call_gemini() -> POST
                   https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent
Contribution     : interprets findings the backend has ALREADY computed (app/analytics.py) and
                   explains likely causes, a first action and data gaps. The report is stored as
                   "pending review" and a person records Accept / Needs more data / False positive.
What it does NOT do: compute fleet statistics, priorities or health scores, open alerts, or
                   order work.

Data sent to the hosted API: valve tag/type and numeric telemetry only. No user names, emails
or free-text notes. Unpaid Gemini tiers must not receive sensitive, confidential or personal
data; check the current Gemini API terms before using real plant data.
"""
import json
import logging
import re
import time
from collections import defaultdict, deque
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import AI_CALLS_PER_HOUR, GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger("valveguard.ai")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
Urgency = Literal["immediate", "within_24h", "this_week", "monitor"]
Likelihood = Literal["high", "medium", "low"]


def _norm(v, allowed: tuple[str, ...], default: str) -> str:
    v = str(v).strip().lower().replace(" ", "_").replace("-", "_")
    return v if v in allowed else default


class Explanation(BaseModel):
    cause: str = Field(max_length=160)
    likelihood: Likelihood = "medium"

    @field_validator("likelihood", mode="before")
    @classmethod
    def _lk(cls, v):
        return _norm(v, ("high", "medium", "low"), "medium")


class Diagnosis(BaseModel):
    summary: str = Field(max_length=500)
    likely_explanations: list[Explanation] = Field(min_length=1, max_length=3)
    recommended_first_action: str = Field(max_length=240)
    next_checks: list[str] = Field(default_factory=list, max_length=4)
    data_gaps: list[str] = Field(default_factory=list, max_length=4)
    urgency: Urgency = "monitor"
    confidence: float = Field(ge=0, le=1)

    @field_validator("urgency", mode="before")
    @classmethod
    def _urgency(cls, v):
        return _norm(v, ("immediate", "within_24h", "this_week", "monitor"), "monitor")

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v / 100 if v > 1 else v))

    @field_validator("likely_explanations", mode="before")
    @classmethod
    def _expl(cls, v):
        if isinstance(v, (str, dict)):
            v = [v]
        return [{"cause": x} if isinstance(x, str) else x for x in (v or [])][:3]

    @field_validator("next_checks", "data_gaps", mode="before")
    @classmethod
    def _lists(cls, v):
        if isinstance(v, str):
            v = [v] if v.strip() else []
        return [str(x)[:200] for x in (v or [])][:4]


# --- per-user rate limit so a demo can't burn the API quota ---
_calls: dict[int, deque] = defaultdict(deque)


def allow_call(user_id: int) -> bool:
    now = time.time()
    q = _calls[user_id]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= AI_CALLS_PER_HOUR:
        return False
    q.append(now)
    return True


def _json_mode() -> bool:
    """Gemini models support JSON output mode; Gemma models on the same API do not."""
    return GEMINI_MODEL.lower().startswith("gemini")


def status() -> dict:
    return {
        "configured": bool(GEMINI_API_KEY),
        "model": GEMINI_MODEL,
        "json_mode": _json_mode(),
        "endpoint": f"{API_ROOT}/models/{GEMINI_MODEL}:generateContent",
        "provider": "Gemini API",
        "fallback": "rule-based diagnosis",
        "calls_per_hour_per_user": AI_CALLS_PER_HOUR,
    }


def _clean(s) -> str:
    """Valve names are user-entered; strip anything that could read as an instruction."""
    return re.sub(r"[^A-Za-z0-9 _.\-/]", "", str(s))[:40]


def build_prompt(ctx: dict) -> str:
    facts = {
        "valve_tag": _clean(ctx["tag"]), "valve_type": _clean(ctx["type"]),
        "telemetry": ctx["telemetry"],
        "baseline_response_ms": ctx["baseline_response_ms"],
        "computed_findings": [{k: f[k] for k in ("rule", "level", "title", "detail")} for f in ctx["findings"]],
        "priority_assigned_by_rules": ctx["priority"],
        "health_score_0_100": ctx["health"],
        "response_time_trend": ctx["trend"],
        "recent_response_ms": ctx["recent_response_ms"],
        "recent_position_deviation_pct": ctx["recent_deviation_pct"],
    }
    return (
        "You help a maintenance engineer investigate one industrial process valve.\n"
        "The monitoring system has ALREADY computed the findings, priority and health score below "
        "with fixed rules. Do not recompute or change them, and do not invent measurements, parts, "
        "fault codes or maintenance history. Your job is to interpret the findings: give likely "
        "physical explanations, the first thing a technician should check, and what data is missing. "
        "If the data cannot separate two causes, say so and lower the confidence. A finding at level "
        "'verify' means the sensor itself may be faulty, so treat that reading as untrustworthy.\n"
        "You advise a human; you never order work or change settings.\n\n"
        f"DATA (JSON): {json.dumps(facts)}\n\n"
        "Reply with ONE JSON object and nothing else, using exactly these keys:\n"
        '{"summary": string (2-3 sentences), '
        '"likely_explanations": [{"cause": string, "likelihood": "high"|"medium"|"low"}] (1-3 items, most likely first), '
        '"recommended_first_action": string, '
        '"next_checks": [up to 4 short inspection steps], '
        '"data_gaps": [up to 4 pieces of missing data that would raise confidence], '
        '"urgency": "immediate"|"within_24h"|"this_week"|"monitor", '
        '"confidence": number 0-1}'
    )


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start:end + 1])


def _call_gemini(prompt: str) -> tuple[str, str | None]:
    """The one place the model is called. Returns (reply text, modelVersion reported by the API)."""
    url = f"{API_ROOT}/models/{GEMINI_MODEL}:generateContent"
    gen = {"temperature": 0.2, "maxOutputTokens": 2048}
    if _json_mode():
        gen["responseMimeType"] = "application/json"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
    r = httpx.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=60)
    r.raise_for_status()
    data = r.json()
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought")), data.get("modelVersion")


def _describe(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            msg = exc.response.json()["error"]["message"]
        except Exception:
            msg = exc.response.text
        return f"HTTP {exc.response.status_code}: {msg[:160]}"
    return f"{type(exc).__name__}: {str(exc)[:120]}"


def _hint(error: str) -> str:
    if "HTTP 400" in error or "HTTP 403" in error:
        return "The API key was rejected or the Gemini API is not enabled for it. Create a new key in Google AI Studio."
    if "HTTP 404" in error:
        return f"This key cannot use model '{GEMINI_MODEL}'. Check GEMINI_MODEL and your model access."
    if "HTTP 429" in error:
        return "Quota or rate limit reached. Wait a minute or check your plan."
    if "ConnectError" in error or "Timeout" in error:
        return "Could not reach generativelanguage.googleapis.com. Check your internet connection."
    if "validation error" in error.lower() or "JSON" in error:
        return "The model replied, but not in the required JSON shape. Try again or use a gemini-* model (JSON mode)."
    return "See the error above. The app keeps working with the rule-based fallback."


def rule_based(ctx: dict) -> Diagnosis:
    """Conventional fallback. Also the answer when no API key is configured."""
    rules = {f["rule"] for f in ctx["findings"]}
    flat = sorted(r.removeprefix("flatline_") for r in rules if r.startswith("flatline_"))
    slow, dev = "response_time" in rules, "position_deviation" in rules
    expl, gaps = [], ["Maintenance history for this valve", "Positioner diagnostic / fault codes"]
    if slow and dev:
        summary = "The valve is responding slowly and not reaching its commanded position."
        expl = [("Positioner degradation", "high"), ("Actuator friction or sticking stem", "medium"),
                ("Low instrument air supply", "low")]
        first = "Review positioner diagnostics and run a valve signature (step) test."
        checks = ["Check instrument air supply pressure", "Inspect stem packing for over-tightening",
                  "Verify positioner calibration"]
    elif slow:
        summary = "Stroke response time is well above this valve's baseline."
        expl = [("Actuator friction or packing drag", "high"), ("Low or restricted instrument air supply", "medium"),
                ("Positioner tuning drift", "low")]
        first = "Run a partial stroke test and compare against the baseline signature."
        checks = ["Check air supply pressure and filter regulator", "Inspect packing and stem condition"]
    elif dev:
        summary = "The measured position does not match the commanded position."
        expl = [("Positioner calibration drift", "high"), ("Loose feedback linkage", "medium"),
                ("Trim or seat damage", "low")]
        first = "Verify positioner calibration and feedback linkage."
        checks = ["Compare local position indicator against the transmitted position",
                  "Check for process pressure changes at the time of deviation"]
    else:
        summary, first, checks = "", "", []
    if "temperature" in rules:
        expl.append(("Packing or body leak causing heating", "medium"))
        checks.append("Inspect packing gland and body joints for leaks")
    if "vibration" in rules:
        expl.append(("Cavitation or flashing across the trim", "medium"))
        checks.append("Check differential pressure across the valve against its sizing")
    if flat:
        names = " and ".join(flat)
        summary = (summary + " " if summary else "") + f"The {names} sensor has stopped changing, so its readings cannot be trusted."
        expl.insert(0, (f"Failed or disconnected {names} transmitter", "high"))
        first = first or f"Verify the {names} transmitter and its wiring before trusting other conclusions."
        gaps.insert(0, f"A trustworthy {names} reading")
    if not expl:
        summary = "Readings are within baseline. No investigation is needed."
        expl = [("No fault indicated", "high")]
        first, checks, gaps = "Continue routine monitoring.", [], []
    urgency = {"urgent_review": "within_24h", "verify_sensor": "this_week",
               "inspect_soon": "this_week"}.get(ctx["priority"], "monitor")
    return Diagnosis(summary=summary.strip(), urgency=urgency,
                     likely_explanations=[{"cause": c, "likelihood": lk} for c, lk in expl[:3]],
                     recommended_first_action=first, next_checks=checks[:4], data_gaps=gaps[:4],
                     confidence=0.55 if ctx["findings"] else 0.4)


def diagnose(ctx: dict) -> dict:
    """Never raises. Returns analysis + provenance: source, model, latency_ms, error."""
    t0, error = time.perf_counter(), None
    ms = lambda: int((time.perf_counter() - t0) * 1000)  # noqa: E731
    if GEMINI_API_KEY:
        try:
            text, version = _call_gemini(build_prompt(ctx))
            diag = Diagnosis.model_validate(_extract_json(text))
            return {"analysis": diag.model_dump(), "source": "gemini", "model": GEMINI_MODEL,
                    "api_model_version": version, "latency_ms": ms(), "error": None,
                    "response_preview": text[:600]}
        except (httpx.HTTPError, ValueError, KeyError, IndexError, ValidationError) as exc:
            error = _describe(exc)
            log.warning("Gemini call failed (%s); using rule-based fallback", error)
    else:
        error = "no_api_key"
    return {"analysis": rule_based(ctx).model_dump(), "source": "rules", "model": None,
            "api_model_version": None, "latency_ms": ms(), "error": error, "response_preview": ""}


SAMPLE_CTX = {
    "tag": "V-113", "type": "control",
    "telemetry": {"position_pct": 41.0, "command_pct": 55.0, "response_ms": 1720, "pressure_bar": 7.9,
                  "temperature_c": 84.0, "vibration_mm_s": 1.6},
    "baseline_response_ms": 820, "priority": "urgent_review", "health": 34,
    "findings": [{"rule": "response_time", "level": "urgent", "title": "Response time +110%",
                  "detail": "1720 ms vs baseline 820 ms."},
                 {"rule": "position_deviation", "level": "urgent", "title": "Position-command mismatch",
                  "detail": "Position 41.0% vs command 55.0% (14.0 points)."}],
    "trend": {"slope_ms_per_hour": 38.5, "hours_to_inspect_threshold": 0, "breach_probability_72h": 0.99},
    "recent_response_ms": [1210, 1290, 1380, 1460, 1550, 1640, 1720],
    "recent_deviation_pct": [6.0, 7.5, 9.0, 10.5, 12.0, 13.0, 14.0],
}


def selftest() -> dict:
    """Live check: real prompt, real call, raw reply, parsed result."""
    prompt = build_prompt(SAMPLE_CTX)
    base = {"model": GEMINI_MODEL, "endpoint": f"{API_ROOT}/models/{GEMINI_MODEL}:generateContent",
            "json_mode": _json_mode(), "prompt": prompt}
    if not GEMINI_API_KEY:
        return {**base, "ok": False, "configured": False, "error": "no_api_key", "raw_reply": None,
                "parsed": None, "latency_ms": 0, "api_model_version": None,
                "hint": "Add GEMINI_API_KEY to .env and restart the backend."}
    t0, text, version = time.perf_counter(), None, None
    try:
        text, version = _call_gemini(prompt)
        parsed = Diagnosis.model_validate(_extract_json(text)).model_dump()
        return {**base, "ok": True, "configured": True, "error": None, "raw_reply": text, "parsed": parsed,
                "latency_ms": int((time.perf_counter() - t0) * 1000), "api_model_version": version, "hint": ""}
    except Exception as exc:  # diagnostic endpoint: report everything
        err = _describe(exc)
        return {**base, "ok": False, "configured": True, "error": err, "raw_reply": text, "parsed": None,
                "latency_ms": int((time.perf_counter() - t0) * 1000), "api_model_version": version, "hint": _hint(err)}
