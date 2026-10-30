"""AI diagnosis through the Gemini API (hosted Gemma 4), with a deterministic fallback.

Model identifier : GEMINI_MODEL, default "gemma-4-26b-a4b-it"  (alternative: "gemma-4-31b-it")
Inference path   : UI "Analyze with AI" -> POST /api/alerts/{id}/analyze (app/api.py: analyze_alert)
                   -> diagnose() -> _call_gemini() -> POST
                   https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent
Contribution     : turns sensor numbers into a structured diagnosis (cause, urgency, next checks).
                   The result is stored as "pending review" and a person approves or rejects it.
What it does NOT do: set severity, open alerts, create work orders or touch equipment.

Data sent to the hosted API: asset tag/type and numeric sensor values only. No user names,
emails or free-text notes. Unpaid Gemini tiers must not receive sensitive, confidential or
personal data; check the current Gemini API terms before using real plant data.
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

log = logging.getLogger("nexora.ai")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
Urgency = Literal["immediate", "within_24h", "this_week", "monitor"]


class Diagnosis(BaseModel):
    probable_cause: str = Field(max_length=400)
    failure_mode: str = Field(max_length=80)
    urgency: Urgency = "monitor"
    confidence: float = Field(ge=0, le=1)
    recommended_actions: list[str] = Field(max_length=5)
    uncertainty_notes: str = Field(default="", max_length=400)

    @field_validator("urgency", mode="before")
    @classmethod
    def _urgency(cls, v):
        v = str(v).strip().lower().replace(" ", "_").replace("-", "_")
        return v if v in ("immediate", "within_24h", "this_week", "monitor") else "monitor"

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v / 100 if v > 1 else v))

    @field_validator("recommended_actions", mode="before")
    @classmethod
    def _actions(cls, v):
        if isinstance(v, str):
            v = [v]
        return [str(x)[:200] for x in (v or [])][:5]


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


def status() -> dict:
    return {
        "configured": bool(GEMINI_API_KEY),
        "model": GEMINI_MODEL,
        "is_gemma4": GEMINI_MODEL.lower().startswith("gemma-4"),
        "endpoint": f"{API_ROOT}/models/{GEMINI_MODEL}:generateContent",
        "provider": "Gemini API (hosted Gemma 4)",
        "fallback": "rule-based diagnosis",
        "code_path": [
            "frontend/app.js  ->  POST /api/alerts/{id}/analyze  or  POST /api/insights/generate",
            "app/api.py       ->  analyze_alert() / generate_insights()",
            "app/ai.py        ->  diagnose()  ->  build_prompt()  ->  _call_gemini()",
            "Gemini API       ->  models/" + GEMINI_MODEL + ":generateContent",
            "app/ai.py        ->  Diagnosis schema validation  ->  stored as 'pending review'",
        ],
    }


def _clean(s: str) -> str:
    """Asset names are user-entered; strip anything that could read as an instruction."""
    return re.sub(r"[^A-Za-z0-9 _.\-/]", "", str(s))[:40]


def build_prompt(ctx: dict) -> str:
    facts = {
        "asset_tag": _clean(ctx["tag"]), "asset_type": _clean(ctx["type"]),
        "vibration_mm_s": ctx["vibration"], "vibration_alarm_mm_s": ctx["vib_alarm"],
        "temperature_c": ctx["temperature"], "temperature_alarm_c": ctx["temp_alarm"],
        "health_score_0_100": ctx["health"],
        "vibration_trend_mm_s_per_hour": ctx["slope_per_hour"],
        "hours_until_vibration_alarm": ctx["hours_to_threshold"],
        "failure_probability_72h_from_trend": ctx["failure_probability_72h"],
        "last_vibration_readings": ctx["recent_vibration"],
    }
    return (
        "You help a maintenance engineer interpret sensor data from one piece of industrial equipment.\n"
        "Use ONLY the numbers below. Do not invent measurements, parts or history. If the data cannot "
        "separate two causes, say so in uncertainty_notes and lower the confidence.\n"
        "You advise a human; you never order work or change settings.\n\n"
        f"DATA (JSON): {json.dumps(facts)}\n\n"
        "Reply with ONE JSON object and nothing else, using exactly these keys:\n"
        '{"probable_cause": string, "failure_mode": string (2-4 words), '
        '"urgency": "immediate"|"within_24h"|"this_week"|"monitor", '
        '"confidence": number 0-1, "recommended_actions": [up to 4 short inspection or maintenance steps], '
        '"uncertainty_notes": string}'
    )


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start:end + 1])


def _call_gemini(prompt: str) -> tuple[str, str | None]:
    """The one place the model is called. Returns (reply text, modelVersion reported by the API)."""
    url = f"{API_ROOT}/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}}
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
        return f"This key cannot use model '{GEMINI_MODEL}'. Try GEMINI_MODEL=gemma-4-31b-it or check model access."
    if "HTTP 429" in error:
        return "Quota or rate limit reached. Wait a minute or check your plan."
    if "ConnectError" in error or "Timeout" in error:
        return "Could not reach generativelanguage.googleapis.com. Check your internet connection."
    return "See the error above. The app keeps working with the rule-based fallback."


def rule_based(ctx: dict) -> Diagnosis:
    """Conventional fallback. Also the answer when no API key is configured."""
    vib_hi = ctx["vibration"] >= ctx["vib_alarm"] * 0.9
    temp_hi = ctx["temperature"] >= ctx["temp_alarm"] * 0.95
    rising = ctx["slope_per_hour"] > 0.05
    t = ctx["type"].lower()
    if vib_hi and temp_hi:
        cause, mode = "High vibration with high temperature points to bearing wear or lubrication loss.", "Bearing / lubrication"
        actions = ["Inspect bearing condition and lubricant level", "Check shaft alignment", "Compare against the last vibration spectrum"]
    elif vib_hi:
        cause = ("Vibration above alarm level; common causes are bearing defect, imbalance or misalignment."
                 if t != "pump" else "Vibration above alarm level; common causes are cavitation, bearing wear or misalignment.")
        mode = "Bearing / imbalance" if t != "pump" else "Cavitation / bearing"
        actions = ["Take a vibration spectrum to separate bearing defects from imbalance", "Check mounting and alignment", "Inspect bearing housing"]
    elif temp_hi:
        cause, mode = "Temperature above alarm level with normal vibration suggests cooling or lubrication problems.", "Thermal / lubrication"
        actions = ["Check coolant flow and lubricant level", "Inspect heat exchanger or filters"]
    elif rising and ctx["failure_probability_72h"] >= 0.5:
        cause, mode = "Vibration is within limits but trending up fast enough to reach the alarm level.", "Developing wear"
        actions = ["Schedule an inspection before the projected alarm time", "Increase monitoring frequency"]
    else:
        cause, mode = "Readings are within normal limits.", "None detected"
        actions = ["Continue routine monitoring"]
    urgency = ("immediate" if ctx["vibration"] >= ctx["vib_alarm"] * 1.15 else
               "within_24h" if (vib_hi or temp_hi) else
               "this_week" if ctx["failure_probability_72h"] >= 0.5 else "monitor")
    return Diagnosis(probable_cause=cause, failure_mode=mode, urgency=urgency,
                     confidence=0.55 if (vib_hi or temp_hi) else 0.4, recommended_actions=actions,
                     uncertainty_notes="Rule-based result from thresholds and trend only; no AI model was used.")


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


SAMPLE_CTX = {"tag": "C-201", "type": "compressor", "vibration": 7.0, "vib_alarm": 6.0, "temperature": 72,
              "temp_alarm": 90, "health": 50, "slope_per_hour": 0.226, "hours_to_threshold": 0,
              "failure_probability_72h": 0.99, "recent_vibration": [5.2, 5.6, 6.0, 6.4, 6.7, 7.0]}


def selftest() -> dict:
    """Live check for the System page: real prompt, real call, raw reply, parsed result."""
    prompt = build_prompt(SAMPLE_CTX)
    base = {"model": GEMINI_MODEL, "endpoint": f"{API_ROOT}/models/{GEMINI_MODEL}:generateContent",
            "is_gemma4": GEMINI_MODEL.lower().startswith("gemma-4"), "prompt": prompt}
    if not GEMINI_API_KEY:
        return {**base, "ok": False, "configured": False, "error": "no_api_key", "raw_reply": None,
                "parsed": None, "latency_ms": 0, "api_model_version": None,
                "hint": "Add GEMINI_API_KEY to .env and restart the server."}
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
