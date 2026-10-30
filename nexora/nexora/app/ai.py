"""AI diagnosis through the Gemini API (hosted Gemma 4), with a deterministic fallback.

What the model does:  turns a handful of sensor numbers into a short, structured
                      diagnosis (probable cause, urgency, suggested checks) in plain language.
What it does NOT do:  decide severity, open alerts, create work orders or touch equipment.
                      Every output is stored as "pending review" and a human approves it.

Data sent to the hosted API: asset tag/type and numeric sensor values only. No user
names, emails or free-text notes. Do not point this at confidential plant data on an
unpaid Gemini tier; check the current Gemini API terms first.
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
    return {"configured": bool(GEMINI_API_KEY), "model": GEMINI_MODEL,
            "provider": "Gemini API (hosted Gemma 4)", "fallback": "rule-based diagnosis"}


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


def _call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}}
    r = httpx.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=40)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


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
    conf = 0.55 if (vib_hi or temp_hi) else 0.4
    return Diagnosis(probable_cause=cause, failure_mode=mode, urgency=urgency, confidence=conf,
                     recommended_actions=actions,
                     uncertainty_notes="Rule-based result from thresholds and trend only; no AI model was used.")


def diagnose(ctx: dict) -> dict:
    """Returns {analysis, source, model, error?}. Never raises: falls back to rules."""
    error = None
    if GEMINI_API_KEY:
        try:
            diag = Diagnosis.model_validate(_extract_json(_call_gemini(build_prompt(ctx))))
            return {"analysis": diag.model_dump(), "source": "gemini", "model": GEMINI_MODEL}
        except (httpx.HTTPError, ValueError, KeyError, IndexError, ValidationError) as exc:
            error = f"{type(exc).__name__}"
            log.warning("Gemini call failed (%s); using rule-based fallback", error)
    else:
        error = "no_api_key"
    return {"analysis": rule_based(ctx).model_dump(), "source": "rules", "model": None, "error": error}
