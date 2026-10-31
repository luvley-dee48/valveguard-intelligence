"""Deterministic valve analytics. No AI here on purpose: thresholds, health scores, priorities
and trend forecasts are plain maths so they are cheap, repeatable and auditable. The AI only
interprets what this module finds."""
import math
from datetime import timedelta

from .db import iso

SENSITIVITY = {"strict": 0.85, "standard": 1.0, "relaxed": 1.15}
PRIORITIES = ("normal", "inspect_soon", "urgent_review", "verify_sensor")
FLATLINE_MIN_READINGS = 8
FLATLINE_SENSORS = (("pressure_bar", "pressure"), ("temperature_c", "temperature"), ("vibration_mm_s", "vibration"))


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def thresholds(cfg: dict) -> dict:
    """Alarm levels after applying the org's sensitivity (strict = lower limits)."""
    s = SENSITIVITY[cfg["sensitivity"]]
    return {
        "response_inspect_ratio": round(1 + 0.4 * s, 3), "response_urgent_ratio": round(1 + 1.0 * s, 3),
        "deviation_inspect_pct": round(5 * s, 2), "deviation_urgent_pct": round(10 * s, 2),
        "temperature_alarm_c": cfg["temperature_alarm"] * s, "vibration_alarm_mm_s": cfg["vibration_alarm"] * s,
    }


def _flatlined(recent: list[dict], key: str) -> bool:
    vals = [r[key] for r in recent[-FLATLINE_MIN_READINGS:]]
    return len(vals) >= FLATLINE_MIN_READINGS and None not in vals and max(vals) - min(vals) < 1e-6


def evaluate(v: dict, recent: list[dict], cfg: dict) -> dict:
    """v: latest valve telemetry. recent: ascending readings as dicts (may include the latest).
    Returns priority, headline finding, health 0-100 and every rule that fired."""
    th = thresholds(cfg)
    findings: list[dict] = []

    def add(rule, level, title, detail, value, limit):
        findings.append({"rule": rule, "level": level, "title": title, "detail": detail,
                         "value": round(value, 2), "threshold": round(limit, 2)})

    ratio = v["response_ms"] / v["baseline_response_ms"] if v["baseline_response_ms"] else 1.0
    pct = round((ratio - 1) * 100)
    if ratio >= th["response_urgent_ratio"]:
        add("response_time", "urgent", f"Response time +{pct}%",
            f"{v['response_ms']:.0f} ms vs baseline {v['baseline_response_ms']:.0f} ms.", ratio, th["response_urgent_ratio"])
    elif ratio >= th["response_inspect_ratio"]:
        add("response_time", "inspect", f"Response time +{pct}%",
            f"{v['response_ms']:.0f} ms vs baseline {v['baseline_response_ms']:.0f} ms.", ratio, th["response_inspect_ratio"])

    dev = abs(v["position_pct"] - v["command_pct"])
    if dev >= th["deviation_inspect_pct"]:
        urgent = dev >= th["deviation_urgent_pct"]
        add("position_deviation", "urgent" if urgent else "inspect", "Position-command mismatch",
            f"Position {v['position_pct']:.1f}% vs command {v['command_pct']:.1f}% ({dev:.1f} points).",
            dev, th["deviation_urgent_pct"] if urgent else th["deviation_inspect_pct"])

    t = v.get("temperature_c")
    if t is not None and t >= th["temperature_alarm_c"]:
        urgent = t >= th["temperature_alarm_c"] * 1.1
        add("temperature", "urgent" if urgent else "inspect", "Body temperature above alarm",
            f"{t:.1f} °C (alarm {th['temperature_alarm_c']:.0f} °C).", t, th["temperature_alarm_c"])

    vib = v.get("vibration_mm_s")
    if vib is not None and vib >= th["vibration_alarm_mm_s"]:
        urgent = vib >= th["vibration_alarm_mm_s"] * 1.5
        add("vibration", "urgent" if urgent else "inspect", "Vibration above alarm",
            f"{vib:.1f} mm/s (alarm {th['vibration_alarm_mm_s']:.1f} mm/s).", vib, th["vibration_alarm_mm_s"])

    for key, label in FLATLINE_SENSORS:
        if _flatlined(recent, key):
            add(f"flatline_{label}", "verify", f"Flatlined {label} sensor",
                f"Last {FLATLINE_MIN_READINGS} {label} readings are identical ({recent[-1][key]}).",
                recent[-1][key], 0)

    levels = {f["level"] for f in findings}
    priority = ("urgent_review" if "urgent" in levels else "verify_sensor" if "verify" in levels
                else "inspect_soon" if "inspect" in levels else "normal")
    order = {"urgent": 0, "verify": 1, "inspect": 2}
    findings.sort(key=lambda f: order[f["level"]])

    penalty = 40 * clamp((ratio - 1) / (th["response_urgent_ratio"] - 1), 0, 1)
    penalty += 30 * clamp(dev / th["deviation_urgent_pct"], 0, 1)
    if t is not None:
        penalty += 15 * clamp((t - th["temperature_alarm_c"] * 0.8) / (th["temperature_alarm_c"] * 0.3), 0, 1)
    if vib is not None:
        penalty += 15 * clamp((vib - th["vibration_alarm_mm_s"] * 0.5) / th["vibration_alarm_mm_s"], 0, 1)
    if "verify" in levels:
        penalty += 10
    return {"priority": priority, "finding": findings[0]["title"] if findings else "Within baseline",
            "health": round(clamp(100 - penalty, 0, 100)), "findings": findings,
            "metrics": {"response_ratio": round(ratio, 3), "position_deviation_pct": round(dev, 2)},
            "thresholds": th}


def linreg(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Least squares -> (slope, intercept, residual std)."""
    n = len(points)
    if n < 3:
        return 0.0, (points[-1][1] if points else 0.0), 0.0
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    slope = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx if sxx else 0.0
    icpt = my - slope * mx
    resid = [p[1] - (icpt + slope * p[0]) for p in points]
    std = math.sqrt(sum(r * r for r in resid) / max(n - 2, 1))
    return slope, icpt, std


def norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def forecast(readings: list[tuple], threshold: float, horizon_h: float = 12, step_min: int = 30,
             min_std: float = 0.15) -> dict | None:
    """readings: ascending [(datetime, value)]. Returns trend, forecast band and 72h breach risk."""
    if not readings:
        return None
    t0, cur = readings[-1]
    pts = [((t - t0).total_seconds() / 3600, v) for t, v in readings]
    slope, _, std = linreg(pts)
    std = max(std, min_std)

    def sigma(h: float) -> float:
        return std * (1 + h / 12)

    series = []
    for i in range(1, int(horizon_h * 60 / step_min) + 1):
        h = i * step_min / 60
        p = cur + slope * h
        s = sigma(h)
        series.append({"t": iso(t0 + timedelta(hours=h)), "predicted": round(p, 2),
                       "lower": round(max(0.0, p - 1.64 * s), 2), "upper": round(p + 1.64 * s, 2)})

    if cur >= threshold:
        prob, hours = 0.99, 0.0
    else:
        prob = min(norm_cdf((cur + slope * 72 - threshold) / sigma(72)), 0.99)
        hours = round((threshold - cur) / slope, 1) if slope > 1e-6 else None
    return {
        "actual": [{"t": iso(t), "v": round(v, 2)} for t, v in readings],
        "forecast": series,
        "threshold": round(threshold, 2),
        "slope_per_hour": round(slope, 3),
        "hours_to_threshold": hours,
        "breach_probability_72h": round(prob, 2),
    }
