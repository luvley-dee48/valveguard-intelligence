"""Simulated demo fleet, loaded per organisation from the Fleet Overview ("Load demo fleet").

Only telemetry is simulated. Priorities, findings, health and alerts are computed by the same
rules as live data (app/analytics.py), so the demo exercises the real pipeline.
"""
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from .api import TELEMETRY, refresh_valve
from .db import Reading, Valve, utcnow

AREAS = ["Feedwater", "Steam header", "Cooling loop", "Condensate", "Process line"]
TYPES = ["control", "globe", "butterfly", "ball"]
# V-101..V-120 with V-120 replaced by V-121, matching the landing page demo.
DEMO_VALVES = [f"V-{n}" for n in range(101, 120)] + ["V-121"]
N_READINGS = 24  # 12 hours, every 30 minutes


def _series(tag: str, i: int, rng: random.Random) -> tuple[float, list[dict]]:
    """Return (baseline_ms, readings oldest-first) for one valve."""
    baseline = 600 + (i * 53) % 500
    command = 35 + (i * 7) % 40
    pressure, temp, vib = 4 + (i % 8), 45 + (i * 5) % 40, 0.6 + (i % 5) * 0.25
    rows = []
    for k in range(N_READINGS):
        late = max(0, k - 11) / 12  # 0 for the first half, ramps to 1 over the last 6 hours
        ratio = 1 + rng.uniform(-0.04, 0.04)
        dev = rng.uniform(-0.8, 0.8)
        v = vib + rng.uniform(-0.08, 0.08)
        if tag == "V-107":  # slowing actuator: response time +68% by now
            ratio = 1 + 0.68 * late + rng.uniform(-0.02, 0.02)
        elif tag == "V-113":  # positioner losing control: position falls behind command
            ratio = 1 + 0.5 * late + rng.uniform(-0.02, 0.02)
            dev = -14 * late - rng.uniform(0, 0.5)
        elif tag == "V-121":  # vibration transmitter stuck at one value
            v = 1.3
        rows.append({"position_pct": round(min(max(command + dev, 0), 100), 1), "command_pct": float(command),
                     "response_ms": round(baseline * ratio), "pressure_bar": round(pressure + rng.uniform(-0.15, 0.15), 2),
                     "temperature_c": round(temp + rng.uniform(-1, 1), 1), "vibration_mm_s": round(v, 2)})
    return float(baseline), rows


def seed_demo_fleet(db: Session, org_id: int, cfg: dict) -> list[Valve]:
    rng = random.Random(org_id)
    now = utcnow()
    valves = []
    for i, tag in enumerate(DEMO_VALVES):
        area, typ = AREAS[i % len(AREAS)], TYPES[i % len(TYPES)]
        baseline, rows = _series(tag, i, rng)
        valve = Valve(org_id=org_id, tag=tag, name=f"{area} {typ} valve {tag}", type=typ, area=area,
                      serial=f"VG-{4100 + i * 37}", baseline_response_ms=baseline, **rows[-1])
        db.add(valve)
        db.flush()
        for k, r in enumerate(rows):
            db.add(Reading(valve_id=valve.id, ts=now - timedelta(minutes=30 * (N_READINGS - 1 - k)),
                           **{f: r[f] for f in TELEMETRY}))
        db.flush()
        refresh_valve(db, valve, cfg)
        valves.append(valve)
    return valves
