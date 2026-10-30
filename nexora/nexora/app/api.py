"""REST API. Everything here requires a logged-in user (JWT bearer token)."""
import json
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai
from .analytics import SENSITIVITY, compute_health, forecast, status_from_health
from .auth import current_user, require_admin
from .db import (Activity, Alert, Asset, Insight, Integration, Metric, Reading, Setting,
                 User, Workflow, get_db, iso, utcnow)

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

Severity = Literal["critical", "high", "medium", "low"]
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_SETTINGS = {"sensitivity": "standard", "auto_work_order": "true",
                    "vibration_alarm": "6.0", "temperature_alarm": "90", "plant_name": "North Plant"}


# ------------------------------------------------------------------ helpers
def log_activity(db: Session, kind: str, text: str, detail: str = "") -> None:
    db.add(Activity(kind=kind, text=text[:200], detail=detail[:200]))


def get_settings(db: Session) -> dict:
    stored = {s.key: s.value for s in db.scalars(select(Setting))}
    merged = {**DEFAULT_SETTINGS, **stored}
    return {"sensitivity": merged["sensitivity"], "auto_work_order": merged["auto_work_order"] == "true",
            "vibration_alarm": float(merged["vibration_alarm"]),
            "temperature_alarm": float(merged["temperature_alarm"]), "plant_name": merged["plant_name"]}


def vib_threshold(cfg: dict) -> float:
    return cfg["vibration_alarm"] * SENSITIVITY[cfg["sensitivity"]]


def asset_out(a: Asset) -> dict:
    return {"id": a.id, "tag": a.tag, "name": a.name, "type": a.type, "plant": a.plant,
            "location": a.location, "serial": a.serial, "vibration": a.vibration,
            "temperature": a.temperature, "pressure": a.pressure, "flow_rate": a.flow_rate,
            "health": a.health, "status": a.status, "updated_at": iso(a.updated_at)}


def alert_out(a: Alert, tags: dict[int, str]) -> dict:
    return {"id": a.id, "asset_id": a.asset_id, "asset_tag": tags.get(a.asset_id) if a.asset_id else None,
            "severity": a.severity, "title": a.title, "description": a.description, "status": a.status,
            "source": a.source, "ai_review": a.ai_review,
            "ai_analysis": json.loads(a.ai_analysis) if a.ai_analysis else None,
            "created_at": iso(a.created_at), "updated_at": iso(a.updated_at)}


def insight_out(i: Insight, tags: dict[int, str]) -> dict:
    return {"id": i.id, "asset_id": i.asset_id, "asset_tag": tags.get(i.asset_id) if i.asset_id else None,
            "kind": i.kind, "title": i.title, "body": i.body, "confidence": i.confidence,
            "status": i.status, "source": i.source, "created_at": iso(i.created_at)}


def workflow_out(w: Workflow) -> dict:
    return {"id": w.id, "name": w.name, "description": w.description, "enabled": w.enabled,
            "steps": json.loads(w.steps or "[]"), "run_count": w.run_count, "last_run": iso(w.last_run)}


def integration_out(i: Integration) -> dict:
    return {"id": i.id, "name": i.name, "kind": i.kind, "detail": i.detail, "status": i.status,
            "updated_at": iso(i.updated_at)}


def tag_map(db: Session) -> dict[int, str]:
    return {i: t for i, t in db.execute(select(Asset.id, Asset.tag))}


def get_or_404(db: Session, model, ident: int, label: str):
    obj = db.get(model, ident)
    if not obj:
        raise HTTPException(404, f"{label} not found.")
    return obj


def recent_series(db: Session, asset_id: int, limit: int = 24) -> list[tuple]:
    rows = db.execute(select(Reading.ts, Reading.vibration).where(Reading.asset_id == asset_id)
                      .order_by(Reading.ts.desc()).limit(limit)).all()
    return [(r[0], r[1]) for r in reversed(rows)]


def risk_for(db: Session, asset: Asset, cfg: dict) -> dict | None:
    return forecast(recent_series(db, asset.id), vib_threshold(cfg))


def build_ctx(db: Session, asset: Asset, cfg: dict) -> dict:
    fc = risk_for(db, asset, cfg) or {"slope_per_hour": 0, "hours_to_threshold": None,
                                      "failure_probability_72h": 0, "actual": []}
    return {"tag": asset.tag, "type": asset.type, "vibration": asset.vibration,
            "temperature": asset.temperature, "health": asset.health,
            "vib_alarm": round(vib_threshold(cfg), 2), "temp_alarm": cfg["temperature_alarm"],
            "slope_per_hour": fc["slope_per_hour"], "hours_to_threshold": fc["hours_to_threshold"],
            "failure_probability_72h": fc["failure_probability_72h"],
            "recent_vibration": [p["v"] for p in fc["actual"][-8:]]}


def apply_reading(db: Session, asset: Asset, vib: float, temp: float,
                  pressure: float | None, flow: float | None, actor: str = "sensor") -> dict:
    """Single place where new sensor data updates the asset, health and rule-based alerts."""
    cfg = get_settings(db)
    asset.vibration, asset.temperature = vib, temp
    if pressure is not None:
        asset.pressure = pressure
    if flow is not None:
        asset.flow_rate = flow
    asset.health = compute_health(vib, temp, cfg["vibration_alarm"])
    asset.status = status_from_health(asset.health)
    db.add(Reading(asset_id=asset.id, ts=utcnow(), vibration=vib, temperature=temp,
                   pressure=asset.pressure, flow_rate=asset.flow_rate))

    thr, created = vib_threshold(cfg), []
    rules = [("vibration", vib >= thr, vib < thr * 0.9,
              "critical" if vib >= thr * 1.15 else "high", "Vibration threshold exceeded",
              f"{asset.tag}: vibration {vib:.1f} mm/s (alarm {thr:.1f} mm/s)."),
             ("temperature", temp >= cfg["temperature_alarm"], temp < cfg["temperature_alarm"] * 0.95,
              "high", "Temperature threshold exceeded",
              f"{asset.tag}: temperature {temp:.1f} C (alarm {cfg['temperature_alarm']:.0f} C).")]
    for key, breach, clear, sev, title, desc in rules:
        existing = db.scalar(select(Alert).where(Alert.asset_id == asset.id, Alert.rule_key == key,
                                                 Alert.status != "resolved"))
        if breach:
            if existing:
                existing.description = desc
                if SEV_ORDER[sev] < SEV_ORDER[existing.severity]:
                    existing.severity = sev
            else:
                alert = Alert(asset_id=asset.id, severity=sev, title=title, description=desc,
                              source="rule", rule_key=key)
                db.add(alert)
                db.flush()
                created.append(alert.id)
                log_activity(db, "alert", f"Alert raised: {title}", asset.tag)
                if sev == "critical" and cfg["auto_work_order"]:
                    log_activity(db, "work_order", f"Work order WO-{48000 + alert.id} created", asset.tag)
        elif clear and existing:
            existing.status = "resolved"
            log_activity(db, "alert", f"Alert cleared: {title}", asset.tag)
    return {"created_alerts": created}


# ------------------------------------------------------------------ assets
class AssetIn(BaseModel):
    tag: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9\-_.]+$")
    name: str = Field(min_length=1, max_length=80)
    type: str = Field(min_length=1, max_length=30)
    plant: str = Field(default="North Plant", max_length=60)
    location: str = Field(default="", max_length=80)
    serial: str = Field(default="", max_length=60)
    vibration: float = Field(default=1.0, ge=0, le=100)
    temperature: float = Field(default=25.0, ge=-50, le=400)
    pressure: float | None = Field(default=None, ge=0, le=10000)
    flow_rate: float | None = Field(default=None, ge=0, le=100000)


class AssetPatch(BaseModel):
    tag: str | None = Field(default=None, min_length=1, max_length=30, pattern=r"^[A-Za-z0-9\-_.]+$")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    type: str | None = Field(default=None, min_length=1, max_length=30)
    plant: str | None = Field(default=None, max_length=60)
    location: str | None = Field(default=None, max_length=80)
    serial: str | None = Field(default=None, max_length=60)
    vibration: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=-50, le=400)
    pressure: float | None = Field(default=None, ge=0, le=10000)
    flow_rate: float | None = Field(default=None, ge=0, le=100000)


class ReadingIn(BaseModel):
    vibration: float = Field(ge=0, le=100)
    temperature: float = Field(ge=-50, le=400)
    pressure: float | None = Field(default=None, ge=0, le=10000)
    flow_rate: float | None = Field(default=None, ge=0, le=100000)


def _check_tag_free(db: Session, tag: str, own_id: int | None = None) -> None:
    other = db.scalar(select(Asset).where(Asset.tag == tag))
    if other and other.id != own_id:
        raise HTTPException(409, f"An asset with tag {tag} already exists.")


@router.get("/assets", tags=["assets"])
def list_assets(q: str = "", type: str = "", status: str = "", db: Session = Depends(get_db)):
    stmt = select(Asset).order_by(Asset.health.asc(), Asset.tag)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Asset.tag.ilike(like) | Asset.name.ilike(like) | Asset.location.ilike(like))
    if type:
        stmt = stmt.where(Asset.type == type)
    if status:
        stmt = stmt.where(Asset.status == status)
    return [asset_out(a) for a in db.scalars(stmt)]


@router.post("/assets", status_code=201, tags=["assets"])
def create_asset(body: AssetIn, db: Session = Depends(get_db)):
    _check_tag_free(db, body.tag)
    asset = Asset(**body.model_dump())
    db.add(asset)
    db.flush()
    apply_reading(db, asset, body.vibration, body.temperature, body.pressure, body.flow_rate)
    log_activity(db, "asset", f"Asset registered: {asset.tag}", asset.name)
    db.commit()
    return asset_out(asset)


@router.get("/assets/{asset_id}", tags=["assets"])
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    return asset_out(get_or_404(db, Asset, asset_id, "Asset"))


@router.put("/assets/{asset_id}", tags=["assets"])
def replace_asset(asset_id: int, body: AssetIn, db: Session = Depends(get_db)):
    asset = get_or_404(db, Asset, asset_id, "Asset")
    _check_tag_free(db, body.tag, asset.id)
    for k in ("tag", "name", "type", "plant", "location", "serial"):
        setattr(asset, k, getattr(body, k))
    apply_reading(db, asset, body.vibration, body.temperature, body.pressure, body.flow_rate)
    db.commit()
    return asset_out(asset)


@router.patch("/assets/{asset_id}", tags=["assets"])
def update_asset(asset_id: int, body: AssetPatch, db: Session = Depends(get_db)):
    asset = get_or_404(db, Asset, asset_id, "Asset")
    data = body.model_dump(exclude_unset=True)
    if "tag" in data:
        _check_tag_free(db, data["tag"], asset.id)
    sensor = {k: data.pop(k) for k in ("vibration", "temperature", "pressure", "flow_rate") if k in data}
    for k, v in data.items():
        setattr(asset, k, v)
    if sensor:
        apply_reading(db, asset, sensor.get("vibration", asset.vibration),
                      sensor.get("temperature", asset.temperature),
                      sensor.get("pressure"), sensor.get("flow_rate"))
    db.commit()
    return asset_out(asset)


@router.delete("/assets/{asset_id}", status_code=204, tags=["assets"], dependencies=[Depends(require_admin)])
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = get_or_404(db, Asset, asset_id, "Asset")
    log_activity(db, "asset", f"Asset removed: {asset.tag}", asset.name)
    db.delete(asset)
    db.commit()


@router.get("/assets/{asset_id}/readings", tags=["telemetry"])
def asset_readings(asset_id: int, limit: int = Query(48, ge=1, le=500), db: Session = Depends(get_db)):
    get_or_404(db, Asset, asset_id, "Asset")
    rows = db.scalars(select(Reading).where(Reading.asset_id == asset_id)
                      .order_by(Reading.ts.desc()).limit(limit)).all()
    return [{"id": r.id, "ts": iso(r.ts), "vibration": r.vibration, "temperature": r.temperature,
             "pressure": r.pressure, "flow_rate": r.flow_rate} for r in reversed(rows)]


@router.post("/assets/{asset_id}/readings", status_code=201, tags=["telemetry"])
def add_reading(asset_id: int, body: ReadingIn, db: Session = Depends(get_db)):
    asset = get_or_404(db, Asset, asset_id, "Asset")
    result = apply_reading(db, asset, body.vibration, body.temperature, body.pressure, body.flow_rate)
    db.commit()
    return {"asset": asset_out(asset), **result}


@router.get("/assets/{asset_id}/prediction", tags=["telemetry"])
def asset_prediction(asset_id: int, db: Session = Depends(get_db)):
    asset = get_or_404(db, Asset, asset_id, "Asset")
    fc = risk_for(db, asset, get_settings(db))
    return {"asset": asset_out(asset), **(fc or {})}


# ------------------------------------------------------------------ alerts
class AlertIn(BaseModel):
    asset_id: int | None = None
    severity: Severity
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    status: Literal["open", "acknowledged", "resolved"] = "open"


class AlertPatch(BaseModel):
    asset_id: int | None = None
    severity: Severity | None = None
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: Literal["open", "acknowledged", "resolved"] | None = None


class ReviewIn(BaseModel):
    decision: Literal["approve", "reject"]


def _check_asset(db: Session, asset_id: int | None) -> None:
    if asset_id is not None and not db.get(Asset, asset_id):
        raise HTTPException(422, "The selected asset does not exist.")


@router.get("/alerts", tags=["alerts"])
def list_alerts(status: str = "", severity: str = "", db: Session = Depends(get_db)):
    stmt = select(Alert)
    if status == "active":
        stmt = stmt.where(Alert.status != "resolved")
    elif status:
        stmt = stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    tags = tag_map(db)
    alerts = sorted(db.scalars(stmt), key=lambda a: (SEV_ORDER[a.severity], -a.created_at.timestamp()))
    return [alert_out(a, tags) for a in alerts]


@router.post("/alerts", status_code=201, tags=["alerts"])
def create_alert(body: AlertIn, db: Session = Depends(get_db)):
    _check_asset(db, body.asset_id)
    alert = Alert(**body.model_dump(), source="manual")
    db.add(alert)
    log_activity(db, "alert", f"Alert created: {alert.title}")
    db.commit()
    return alert_out(alert, tag_map(db))


@router.put("/alerts/{alert_id}", tags=["alerts"])
def replace_alert(alert_id: int, body: AlertIn, db: Session = Depends(get_db)):
    alert = get_or_404(db, Alert, alert_id, "Alert")
    _check_asset(db, body.asset_id)
    for k, v in body.model_dump().items():
        setattr(alert, k, v)
    db.commit()
    return alert_out(alert, tag_map(db))


@router.patch("/alerts/{alert_id}", tags=["alerts"])
def update_alert(alert_id: int, body: AlertPatch, db: Session = Depends(get_db)):
    alert = get_or_404(db, Alert, alert_id, "Alert")
    data = body.model_dump(exclude_unset=True)
    if "asset_id" in data:
        _check_asset(db, data["asset_id"])
    for k, v in data.items():
        setattr(alert, k, v)
    if "status" in data:
        log_activity(db, "alert", f"Alert {data['status']}: {alert.title}")
    db.commit()
    return alert_out(alert, tag_map(db))


@router.delete("/alerts/{alert_id}", status_code=204, tags=["alerts"])
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Alert, alert_id, "Alert"))
    db.commit()


@router.post("/alerts/{alert_id}/analyze", tags=["ai"])
def analyze_alert(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """AI diagnosis for one alert. Stored as pending: a person must review it."""
    alert = get_or_404(db, Alert, alert_id, "Alert")
    asset = db.get(Asset, alert.asset_id) if alert.asset_id else None
    if not asset:
        raise HTTPException(422, "Link this alert to an asset before requesting an analysis.")
    if not ai.allow_call(user.id):
        raise HTTPException(429, "AI analysis limit reached for this hour. Try again later.")
    result = ai.diagnose(build_ctx(db, asset, get_settings(db)))
    alert.ai_analysis = json.dumps(result)
    alert.ai_review = "pending"
    log_activity(db, "model", f"AI analysis ready for review: {asset.tag}",
                 result["model"] or "rule-based")
    db.commit()
    return alert_out(alert, tag_map(db))


@router.post("/alerts/{alert_id}/analysis/review", tags=["ai"])
def review_analysis(alert_id: int, body: ReviewIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    alert = get_or_404(db, Alert, alert_id, "Alert")
    if alert.ai_review != "pending":
        raise HTTPException(409, "There is no AI analysis waiting for review on this alert.")
    if body.decision == "approve":
        alert.ai_review = "approved"
        if alert.status == "open":
            alert.status = "acknowledged"
        log_activity(db, "work_order", f"Work order WO-{48000 + alert.id} drafted",
                     f"Approved by {user.name}")
    else:
        alert.ai_review = "rejected"
        log_activity(db, "model", f"AI analysis rejected on alert #{alert.id}", f"By {user.name}")
    db.commit()
    return alert_out(alert, tag_map(db))


# ------------------------------------------------------------------ insights
class InsightIn(BaseModel):
    kind: Literal["anomaly", "optimization", "predictive"]
    title: str = Field(min_length=3, max_length=140)
    body: str = Field(default="", max_length=1500)
    asset_id: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class InsightPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=140)
    body: str | None = Field(default=None, max_length=1500)
    status: Literal["pending", "approved", "dismissed"] | None = None


@router.get("/insights", tags=["insights"])
def list_insights(status: str = "", db: Session = Depends(get_db)):
    stmt = select(Insight).order_by(Insight.created_at.desc())
    if status:
        stmt = stmt.where(Insight.status == status)
    tags = tag_map(db)
    return [insight_out(i, tags) for i in db.scalars(stmt)]


@router.post("/insights", status_code=201, tags=["insights"])
def create_insight(body: InsightIn, db: Session = Depends(get_db)):
    _check_asset(db, body.asset_id)
    ins = Insight(**body.model_dump(), source="manual")
    db.add(ins)
    db.commit()
    return insight_out(ins, tag_map(db))


@router.patch("/insights/{insight_id}", tags=["insights"])
def update_insight(insight_id: int, body: InsightPatch, db: Session = Depends(get_db)):
    ins = get_or_404(db, Insight, insight_id, "Insight")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ins, k, v)
    db.commit()
    return insight_out(ins, tag_map(db))


@router.delete("/insights/{insight_id}", status_code=204, tags=["insights"])
def delete_insight(insight_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Insight, insight_id, "Insight"))
    db.commit()


@router.get("/ai/status", tags=["ai"])
def ai_status():
    return ai.status()


@router.post("/insights/generate", tags=["ai"])
def generate_insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Diagnose the riskiest assets (chosen by plain thresholds and trend, not by the model)."""
    cfg = get_settings(db)
    ranked = []
    for a in db.scalars(select(Asset)):
        fc = risk_for(db, a, cfg)
        prob = fc["failure_probability_72h"] if fc else 0
        if a.status == "critical" or prob >= 0.5:
            ranked.append((prob, a))
    ranked.sort(key=lambda x: -x[0])
    pending = {i.asset_id for i in db.scalars(select(Insight).where(Insight.status == "pending"))}
    created, skipped = [], 0
    for prob, a in ranked[:3]:
        if a.id in pending:
            skipped += 1
            continue
        if not ai.allow_call(user.id):
            raise HTTPException(429, "AI analysis limit reached for this hour. Try again later.")
        res = ai.diagnose(build_ctx(db, a, cfg))
        d = res["analysis"]
        ins = Insight(asset_id=a.id, kind="anomaly" if a.status == "critical" else "predictive",
                      title=f"{d['failure_mode']}: {a.name}",
                      body=f"{d['probable_cause']} Suggested: " + "; ".join(d["recommended_actions"][:3]) + ".",
                      confidence=d["confidence"], source=res["source"])
        db.add(ins)
        created.append(ins)
    if created:
        log_activity(db, "model", f"{len(created)} insight(s) generated", "Pending review")
    db.commit()
    tags = tag_map(db)
    return {"created": [insight_out(i, tags) for i in created], "skipped_existing": skipped,
            "candidates": len(ranked)}


# ------------------------------------------------------------------ workflows
class StepIn(BaseModel):
    kind: Literal["trigger", "analysis", "action"]
    label: str = Field(min_length=1, max_length=60)
    detail: str = Field(default="", max_length=100)


class WorkflowIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=600)
    enabled: bool = True
    steps: list[StepIn] = Field(default_factory=list, max_length=10)


class WorkflowPatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=600)
    enabled: bool | None = None
    steps: list[StepIn] | None = Field(default=None, max_length=10)


@router.get("/workflows", tags=["workflows"])
def list_workflows(db: Session = Depends(get_db)):
    return [workflow_out(w) for w in db.scalars(select(Workflow).order_by(Workflow.id))]


@router.post("/workflows", status_code=201, tags=["workflows"])
def create_workflow(body: WorkflowIn, db: Session = Depends(get_db)):
    w = Workflow(name=body.name, description=body.description, enabled=body.enabled,
                 steps=json.dumps([s.model_dump() for s in body.steps]))
    db.add(w)
    db.commit()
    return workflow_out(w)


@router.put("/workflows/{wf_id}", tags=["workflows"])
def replace_workflow(wf_id: int, body: WorkflowIn, db: Session = Depends(get_db)):
    w = get_or_404(db, Workflow, wf_id, "Workflow")
    w.name, w.description, w.enabled = body.name, body.description, body.enabled
    w.steps = json.dumps([s.model_dump() for s in body.steps])
    db.commit()
    return workflow_out(w)


@router.patch("/workflows/{wf_id}", tags=["workflows"])
def update_workflow(wf_id: int, body: WorkflowPatch, db: Session = Depends(get_db)):
    w = get_or_404(db, Workflow, wf_id, "Workflow")
    data = body.model_dump(exclude_unset=True)
    if "steps" in data:
        w.steps = json.dumps(data.pop("steps"))
    for k, v in data.items():
        setattr(w, k, v)
    db.commit()
    return workflow_out(w)


@router.delete("/workflows/{wf_id}", status_code=204, tags=["workflows"])
def delete_workflow(wf_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Workflow, wf_id, "Workflow"))
    db.commit()


@router.post("/workflows/{wf_id}/run", tags=["workflows"])
def run_workflow(wf_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Records a manual run. Steps are descriptive; no external system is called."""
    w = get_or_404(db, Workflow, wf_id, "Workflow")
    if not w.enabled:
        raise HTTPException(409, "Enable this workflow before running it.")
    w.run_count += 1
    w.last_run = utcnow()
    log_activity(db, "workflow", f"Workflow run: {w.name}", f"Started by {user.name}")
    db.commit()
    return workflow_out(w)


# ------------------------------------------------------------------ integrations
class IntegrationIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    kind: str = Field(default="CMMS", max_length=30)
    detail: str = Field(default="", max_length=160)
    status: Literal["connected", "disconnected"] = "connected"


class IntegrationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    kind: str | None = Field(default=None, max_length=30)
    detail: str | None = Field(default=None, max_length=160)
    status: Literal["connected", "disconnected"] | None = None


@router.get("/integrations", tags=["integrations"])
def list_integrations(db: Session = Depends(get_db)):
    return [integration_out(i) for i in db.scalars(select(Integration).order_by(Integration.id))]


@router.post("/integrations", status_code=201, tags=["integrations"])
def create_integration(body: IntegrationIn, db: Session = Depends(get_db)):
    i = Integration(**body.model_dump())
    db.add(i)
    db.commit()
    return integration_out(i)


@router.put("/integrations/{int_id}", tags=["integrations"])
def replace_integration(int_id: int, body: IntegrationIn, db: Session = Depends(get_db)):
    i = get_or_404(db, Integration, int_id, "Integration")
    for k, v in body.model_dump().items():
        setattr(i, k, v)
    db.commit()
    return integration_out(i)


@router.patch("/integrations/{int_id}", tags=["integrations"])
def update_integration(int_id: int, body: IntegrationPatch, db: Session = Depends(get_db)):
    i = get_or_404(db, Integration, int_id, "Integration")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(i, k, v)
    db.commit()
    return integration_out(i)


@router.delete("/integrations/{int_id}", status_code=204, tags=["integrations"])
def delete_integration(int_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Integration, int_id, "Integration"))
    db.commit()


# ------------------------------------------------------------------ settings & metrics
class SettingsIn(BaseModel):
    sensitivity: Literal["strict", "standard", "relaxed"] = "standard"
    auto_work_order: bool = True
    vibration_alarm: float = Field(default=6.0, gt=0, le=50)
    temperature_alarm: float = Field(default=90, gt=0, le=400)
    plant_name: str = Field(default="North Plant", min_length=1, max_length=60)


class SettingsPatch(BaseModel):
    sensitivity: Literal["strict", "standard", "relaxed"] | None = None
    auto_work_order: bool | None = None
    vibration_alarm: float | None = Field(default=None, gt=0, le=50)
    temperature_alarm: float | None = Field(default=None, gt=0, le=400)
    plant_name: str | None = Field(default=None, min_length=1, max_length=60)


def _store_settings(db: Session, data: dict) -> dict:
    for k, v in data.items():
        v = str(v).lower() if isinstance(v, bool) else str(v)
        row = db.get(Setting, k)
        if row:
            row.value = v
        else:
            db.add(Setting(key=k, value=v))
    db.commit()
    return get_settings(db)


@router.get("/settings", tags=["settings"])
def read_settings(db: Session = Depends(get_db)):
    return get_settings(db)


@router.put("/settings", tags=["settings"], dependencies=[Depends(require_admin)])
def replace_settings(body: SettingsIn, db: Session = Depends(get_db)):
    return _store_settings(db, body.model_dump())


@router.patch("/settings", tags=["settings"], dependencies=[Depends(require_admin)])
def update_settings(body: SettingsPatch, db: Session = Depends(get_db)):
    return _store_settings(db, body.model_dump(exclude_unset=True))


class MetricIn(BaseModel):
    value: float = Field(ge=0, le=1_000_000)
    delta: float = Field(default=0, ge=-1000, le=1000)


@router.get("/metrics", tags=["settings"])
def read_metrics(db: Session = Depends(get_db)):
    return {m.key: {"value": m.value, "delta": m.delta} for m in db.scalars(select(Metric))}


@router.put("/metrics/{key}", tags=["settings"], dependencies=[Depends(require_admin)])
def put_metric(key: Literal["mtbf", "oee", "energy"], body: MetricIn, db: Session = Depends(get_db)):
    m = db.get(Metric, key)
    if m:
        m.value, m.delta = body.value, body.delta
    else:
        db.add(Metric(key=key, value=body.value, delta=body.delta))
    db.commit()
    return {"key": key, **body.model_dump()}


# ------------------------------------------------------------------ dashboards
@router.get("/overview", tags=["dashboard"])
def overview(db: Session = Depends(get_db)):
    cfg = get_settings(db)
    assets = list(db.scalars(select(Asset).order_by(Asset.health.asc(), Asset.tag)))
    health = {s: sum(1 for a in assets if a.status == s) for s in ("healthy", "warning", "critical")}
    active = list(db.scalars(select(Alert).where(Alert.status != "resolved")))
    summary = {s: sum(1 for a in active if a.severity == s) for s in SEV_ORDER}
    tags = tag_map(db)
    recent = sorted(active, key=lambda a: (SEV_ORDER[a.severity], -a.created_at.timestamp()))[:3]
    pending = db.scalars(select(Insight).where(Insight.status == "pending")
                         .order_by(Insight.created_at.desc()).limit(3))
    activity = db.scalars(select(Activity).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(4))
    metrics = {m.key: {"value": m.value, "delta": m.delta} for m in db.scalars(select(Metric))}
    wf = db.scalar(select(Workflow).where(Workflow.enabled.is_(True)).order_by(Workflow.id))
    return {
        "plant_name": cfg["plant_name"],
        "kpis": {"assets": len(assets), "alerts": len(active), "critical_alerts": summary["critical"], **metrics},
        "health": health,
        "alert_summary": {**summary, "total": len(active)},
        "recent_alerts": [alert_out(a, tags) for a in recent],
        "insights": [insight_out(i, tags) for i in pending],
        "activity": [{"id": a.id, "kind": a.kind, "text": a.text, "detail": a.detail,
                      "created_at": iso(a.created_at)} for a in activity],
        "map_assets": [asset_out(a) for a in assets[:4]],
        "top_risk_asset_id": assets[0].id if assets else None,
        "workflow": workflow_out(wf) if wf else None,
    }


@router.get("/analytics/fleet", tags=["dashboard"])
def fleet_analytics(db: Session = Depends(get_db)):
    cfg = get_settings(db)
    assets = list(db.scalars(select(Asset)))
    rows = []
    for a in assets:
        fc = risk_for(db, a, cfg) or {}
        rows.append({**asset_out(a), "failure_probability_72h": fc.get("failure_probability_72h", 0),
                     "hours_to_threshold": fc.get("hours_to_threshold"),
                     "slope_per_hour": fc.get("slope_per_hour", 0)})
    by_type: dict[str, list] = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r["health"])
    return {
        "avg_health": round(sum(r["health"] for r in rows) / len(rows)) if rows else 0,
        "counts": {s: sum(1 for r in rows if r["status"] == s) for s in ("healthy", "warning", "critical")},
        "by_type": [{"type": t, "count": len(v), "avg_health": round(sum(v) / len(v))}
                    for t, v in sorted(by_type.items())],
        "risk": sorted(rows, key=lambda r: -r["failure_probability_72h"])[:8],
        "vibration_alarm": round(vib_threshold(cfg), 2),
    }


@router.get("/activity", tags=["dashboard"])
def list_activity(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(Activity).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit))
    return [{"id": a.id, "kind": a.kind, "text": a.text, "detail": a.detail, "created_at": iso(a.created_at)}
            for a in rows]


@router.get("/reports/summary", tags=["dashboard"])
def report_summary(db: Session = Depends(get_db)):
    assets = list(db.scalars(select(Asset)))
    alerts = list(db.scalars(select(Alert)))
    day_ago = utcnow() - timedelta(days=1)
    return {
        "generated_at": iso(utcnow()),
        "assets": {"total": len(assets), **{s: sum(1 for a in assets if a.status == s)
                                             for s in ("healthy", "warning", "critical")}},
        "alerts": {"total": len(alerts), "open": sum(1 for a in alerts if a.status == "open"),
                   "resolved": sum(1 for a in alerts if a.status == "resolved"),
                   "raised_last_24h": sum(1 for a in alerts if a.created_at >= day_ago)},
        "ai": {"reviewed_approved": sum(1 for a in alerts if a.ai_review == "approved"),
               "reviewed_rejected": sum(1 for a in alerts if a.ai_review == "rejected"),
               "waiting_for_review": sum(1 for a in alerts if a.ai_review == "pending")},
        "readings_stored": db.scalar(select(func.count(Reading.id))),
    }
