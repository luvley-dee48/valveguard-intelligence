"""Demo data so the dashboard is not empty on first run. Disable with SEED_DEMO_DATA=false."""
import json
import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .analytics import compute_health, status_from_health
from .api import log_activity
from .db import Alert, Asset, Insight, Integration, Metric, Reading, Workflow, utcnow

# tag, name, type, location, vibration, temperature, pressure, flow, trend (mm/s change over 12h)
ASSETS = [
    ("C-101", "Compressor C-101", "compressor", "Bay 1", 1.2, 62, 14.2, None, 0.0),
    ("C-201", "Compressor C-201", "compressor", "Bay 4", 7.0, 72, 13.1, None, 2.6),
    ("T-103", "Turbine T-103", "turbine", "Turbine Hall", 1.4, 94, 38.0, None, 0.0),
    ("P-301", "Pump P-301", "pump", "Feed Water Station", 3.4, 68, 6.2, 420, 0.5),
    ("P-302", "Pump P-302", "pump", "Feed Water Station", 1.8, 58, 6.0, 435, 0.0),
    ("P-303", "Pump P-303", "pump", "Cooling Loop", 2.4, 61, 4.4, 380, 0.1),
    ("G-401", "Generator G-401", "generator", "Power House", 2.1, 71, None, None, 0.0),
    ("G-402", "Generator G-402", "generator", "Power House", 1.5, 66, None, None, 0.0),
    ("R-101", "Reactor R-101", "reactor", "Reactor Hall", 0.9, 88, 21.5, 120, 0.0),
    ("C-102", "Compressor C-102", "compressor", "Bay 2", 1.9, 63, 13.8, None, 0.0),
    ("T-104", "Turbine T-104", "turbine", "Turbine Hall", 1.6, 79, 36.5, None, 0.0),
    ("F-201", "Exhaust Fan F-201", "fan", "Stack", 2.9, 65, None, 900, 0.0),
]


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(func.count(Asset.id))):
        return
    rng = random.Random(7)
    now = utcnow()
    assets: dict[str, Asset] = {}
    for n, (tag, name, typ, loc, vib, temp, pres, flow, trend) in enumerate(ASSETS, start=1):
        health = compute_health(vib, temp, 6.0)
        a = Asset(tag=tag, name=name, type=typ, plant="North Plant", location=loc,
                  serial=f"NX-{8800 + n * 37}-{typ[:2].upper()}", vibration=vib, temperature=temp,
                  pressure=pres, flow_rate=flow, health=health, status=status_from_health(health))
        db.add(a)
        db.flush()
        assets[tag] = a
        # 24 readings, 30 minutes apart, ending now; the last one equals the asset's current value
        for i in range(24):
            frac = i / 23
            v = vib - trend * (1 - frac) + rng.uniform(-0.12, 0.12) * (0 if i == 23 else 1)
            t = temp + rng.uniform(-1.2, 1.2) * (0 if i == 23 else 1)
            db.add(Reading(asset_id=a.id, ts=now - timedelta(minutes=30 * (23 - i)),
                           vibration=round(max(v, 0.1), 2), temperature=round(t, 1),
                           pressure=pres, flow_rate=flow))

    def alert(tag, sev, title, desc, mins, rule=None, status="open"):
        db.add(Alert(asset_id=assets[tag].id if tag else None, severity=sev, title=title, description=desc,
                     source="rule" if rule else "manual", rule_key=rule, status=status,
                     created_at=now - timedelta(minutes=mins)))

    alert("C-201", "critical", "Vibration threshold exceeded",
          "C-201: vibration 7.0 mm/s (alarm 6.0 mm/s).", 2, "vibration")
    alert("T-103", "high", "Temperature threshold exceeded",
          "T-103: temperature 94.0 C (alarm 90 C).", 8, "temperature")
    alert("P-301", "high", "Vibration trending up", "P-301: vibration up 0.5 mm/s over 12 hours.", 15)
    alert("R-101", "medium", "Feed temperature drifting", "R-101 running 4 C above setpoint.", 95)
    alert("G-401", "medium", "Insulation test due", "Scheduled insulation resistance test is overdue.", 240)
    alert("F-201", "medium", "Filter differential pressure", "Exhaust filter differential is rising.", 410)
    alert("P-303", "low", "Seal flush check", "Routine seal flush inspection is due this week.", 600)
    alert("C-102", "low", "Lubricant sample", "Oil sample collected, awaiting lab result.", 720)
    alert("T-104", "low", "Firmware update available", "Sensor gateway firmware 2.1.4 is available.", 900)

    db.add_all([
        Insight(asset_id=assets["C-201"].id, kind="anomaly", title="Anomaly detected: Compressor C-201",
                body="Vibration is above the alarm level and climbing. Likely bearing defect; inspect before the next shift.",
                confidence=0.92, source="rules", created_at=now - timedelta(minutes=2)),
        Insight(asset_id=assets["R-101"].id, kind="optimization", title="Optimization opportunity: Reactor R-101",
                body="Adjusting feed rate on Reactor R-101 could improve yield by about 2.4%. (Demo data.)",
                confidence=0.6, source="seed", created_at=now - timedelta(minutes=15)),
        Insight(asset_id=assets["P-301"].id, kind="predictive", title="Predictive maintenance: Pump P-301",
                body="Vibration is trending toward the alarm level. Schedule an inspection within the week.",
                confidence=0.68, source="rules", created_at=now - timedelta(hours=1)),
    ])

    steps = [
        {"kind": "trigger", "label": "Alert Trigger", "detail": "Vibration anomaly on C-201"},
        {"kind": "analysis", "label": "AI Analysis", "detail": "Gemma 4 diagnosis, human reviewed"},
        {"kind": "action", "label": "Create Work Order", "detail": "Maintenance team, after approval"},
        {"kind": "action", "label": "Notify Team", "detail": "#maint-ops"},
        {"kind": "action", "label": "Update CMMS", "detail": "Maximo record"},
    ]
    db.add_all([
        Workflow(name="Critical anomaly escalation",
                 description="When vibration passes the alarm level, run an AI diagnosis, then draft a work order for approval and notify the team.",
                 steps=json.dumps(steps), run_count=4, last_run=now - timedelta(hours=2)),
        Workflow(name="Weekly inspection round",
                 description="Every Monday, list assets with a failure risk above 50% for the inspection plan.",
                 steps=json.dumps(steps[:1] + steps[2:4]), enabled=False),
    ])
    db.add_all([
        Integration(name="IBM Maximo CMMS", kind="CMMS", detail="Record only. No live connector in this build.", status="connected"),
        Integration(name="OPC-UA / MQTT broker", kind="Telemetry", detail="Record only. Readings arrive through the REST API.", status="connected"),
        Integration(name="Slack #maint-ops", kind="Messaging", detail="Record only. No live connector in this build.", status="disconnected"),
    ])
    db.add_all([Metric(key="mtbf", value=18.6, delta=8.2), Metric(key="oee", value=87.3, delta=4.1),
                Metric(key="energy", value=2.54, delta=-6.3)])
    log_activity(db, "work_order", "Work order WO-48291 created", "Compressor C-201")
    log_activity(db, "calibration", "Sensor calibration completed", "Vibration sensor V-201")
    log_activity(db, "model", "Model retrained", "Anomaly detection model v2.4")
    log_activity(db, "sync", "Integration sync", "CMMS: 124 records synced")
    db.commit()
