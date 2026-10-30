"""Deterministic analytics. No AI here on purpose: thresholds, health scores and
trend forecasts are plain maths so they are cheap, repeatable and auditable."""
import math
from datetime import timedelta

from .db import iso

SENSITIVITY = {"strict": 0.85, "standard": 1.0, "relaxed": 1.15}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_health(vibration: float, temperature: float, vib_alarm: float) -> int:
    """0-100 score: 60% vibration headroom, 40% temperature headroom (60C ok -> 110C bad)."""
    v = clamp(1 - (vibration - 1.5) / max(vib_alarm * 1.6 - 1.5, 1), 0, 1)
    t = clamp(1 - (temperature - 60) / 50, 0, 1)
    return round(100 * (0.6 * v + 0.4 * t))


def status_from_health(health: int) -> str:
    return "healthy" if health >= 85 else "warning" if health >= 60 else "critical"


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


def forecast(readings: list[tuple], threshold: float, horizon_h: float = 12, step_min: int = 30) -> dict | None:
    """readings: ascending [(datetime, vibration)]. Returns trend, forecast band and 72h risk."""
    if not readings:
        return None
    t0, cur = readings[-1]
    pts = [((t - t0).total_seconds() / 3600, v) for t, v in readings]
    slope, _, std = linreg(pts)
    std = max(std, 0.15)

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
        "failure_probability_72h": round(prob, 2),
    }
