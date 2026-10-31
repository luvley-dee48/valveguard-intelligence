"""REST API. Everything here requires a logged-in user (JWT bearer token) and is scoped to
that user's organisation: a query never returns another organisation's rows."""
import json
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import ai
from .analytics import PRIORITIES, evaluate, forecast, thresholds
from .auth import current_user, require_admin
from .config import FREE_REPORTS_PER_MONTH, FREE_VALVE_LIMIT
from .db import Activity, AiCall, Alert, Reading, Report, Setting, User, Valve, get_db, iso, utcnow

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

Severity = Literal["critical", "high", "medium", "low"]
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_ORDER = {"urgent_review": 0, "verify_sensor": 1, "inspect_soon": 2, "normal": 3}
LEVEL_SEVERITY = {"urgent": "critical", "verify": "high", "inspect": "medium"}
ValveType = Literal["control", "globe", "ball", "butterfly", "gate", "check"]
Review = Literal["accepted", "needs_data", "false_positive"]
TELEMETRY = ("position_pct", "command_pct", "response_ms", "pressure_bar", "temperature_c", "vibration_mm_s")
DEFAULT_SETTINGS = {"sensitivity": "standard", "temperature_alarm": "120", "vibration_alarm": "4.5"}


# ------------------------------------------------------------------ helpers
def log_activity(db: Session, org_id: int, kind: str, text: str, detail: str = "") -> None:
    db.add(Activity(org_id=org_id, kind=kind, text=text[:200], detail=detail[:200]))


def log_ai(db: Session, user: User, kind: str, valve_tag: str | None, res: dict) -> None:
    """Record every model call (or fallback) so its real contribution can be inspected."""
    db.add(AiCall(org_id=user.org_id, user_id=user.id, kind=kind, valve_tag=valve_tag, model=res.get("model"),
                  api_model_version=res.get("api_model_version"), source=res["source"],
                  error=(res.get("error") or None) and res["error"][:240], latency_ms=res.get("latency_ms", 0),
                  response_preview=res.get("response_preview", "")))


def get_settings(db: Session, org_id: int) -> dict:
    stored = {s.key: s.value for s in db.scalars(select(Setting).where(Setting.org_id == org_id))}
    merged = {**DEFAULT_SETTINGS, **stored}
    return {"sensitivity": merged["sensitivity"], "temperature_alarm": float(merged["temperature_alarm"]),
            "vibration_alarm": float(merged["vibration_alarm"])}


def telemetry(v: Valve) -> dict:
    return {k: getattr(v, k) for k in TELEMETRY}


def eval_input(v: Valve) -> dict:
    return {**telemetry(v), "baseline_response_ms": v.baseline_response_ms}


def valve_out(v: Valve, trend: list[float] | None = None) -> dict:
    out = {"id": v.id, "tag": v.tag, "name": v.name, "type": v.type, "area": v.area, "serial": v.serial,
           **telemetry(v), "baseline_response_ms": v.baseline_response_ms,
           "response_ratio": round(v.response_ms / v.baseline_response_ms, 3) if v.baseline_response_ms else None,
           "position_deviation_pct": round(abs(v.position_pct - v.command_pct), 2),
           "health": v.health, "priority": v.priority, "finding": v.finding,
           "created_at": iso(v.created_at), "updated_at": iso(v.updated_at)}
    if trend is not None:
        out["trend"] = trend
    return out


def alert_out(a: Alert, tags: dict[int, str]) -> dict:
    return {"id": a.id, "valve_id": a.valve_id, "valve_tag": tags.get(a.valve_id) if a.valve_id else None,
            "severity": a.severity, "title": a.title, "description": a.description, "status": a.status,
            "source": a.source, "rule": a.rule_key, "created_at": iso(a.created_at), "updated_at": iso(a.updated_at)}


def report_out(r: Report, tags: dict[int, str]) -> dict:
    return {"id": r.id, "valve_id": r.valve_id, "valve_tag": tags.get(r.valve_id),
            "evidence": json.loads(r.evidence), "analysis": json.loads(r.analysis),
            "source": r.source, "model": r.model, "error": r.error, "latency_ms": r.latency_ms,
            "review": r.review, "review_note": r.review_note, "reviewed_by": r.reviewed_by,
            "reviewed_at": iso(r.reviewed_at), "created_at": iso(r.created_at)}


def tag_map(db: Session, org_id: int) -> dict[int, str]:
    return {i: t for i, t in db.execute(select(Valve.id, Valve.tag).where(Valve.org_id == org_id))}


def owned(db: Session, model, ident: int, user: User, label: str):
    """Fetch a row that belongs to the caller's organisation, else 404 (never 403: don't leak ids)."""
    obj = db.get(model, ident)
    if not obj or obj.org_id != user.org_id:
        raise HTTPException(404, f"{label} not found.")
    return obj


def recent_readings(db: Session, valve_id: int, limit: int = 24) -> list[dict]:
    rows = db.scalars(select(Reading).where(Reading.valve_id == valve_id)
                      .order_by(Reading.ts.desc(), Reading.id.desc()).limit(limit)).all()
    return [{"ts": r.ts, **{k: getattr(r, k) for k in TELEMETRY}} for r in reversed(rows)]


def sync_alerts(db: Session, valve: Valve, findings: list[dict]) -> None:
    """Open, update or resolve rule alerts so they always match the valve's current findings."""
    firing = {f["rule"]: f for f in findings}
    existing = {a.rule_key: a for a in db.scalars(select(Alert).where(
        Alert.valve_id == valve.id, Alert.source == "rule", Alert.status != "resolved"))}
    for rule, f in firing.items():
        sev = LEVEL_SEVERITY[f["level"]]
        desc = f"{valve.tag}: {f['detail']}"
        if rule in existing:
            a = existing[rule]
            a.title, a.description = f["title"], desc
            if SEV_ORDER[sev] < SEV_ORDER[a.severity]:
                a.severity = sev
        else:
            db.add(Alert(org_id=valve.org_id, valve_id=valve.id, severity=sev, title=f["title"],
                         description=desc, source="rule", rule_key=rule))
            log_activity(db, valve.org_id, "alert", f"Alert raised: {f['title']}", valve.tag)
    for rule, a in existing.items():
        if rule not in firing:
            a.status = "resolved"
            log_activity(db, valve.org_id, "alert", f"Alert cleared: {a.title}", valve.tag)


def refresh_valve(db: Session, valve: Valve, cfg: dict) -> dict:
    """Single place where priority, finding and health are (re)computed from telemetry."""
    res = evaluate(eval_input(valve), recent_readings(db, valve.id), cfg)
    valve.health, valve.priority, valve.finding = res["health"], res["priority"], res["finding"]
    sync_alerts(db, valve, res["findings"])
    return res


def apply_reading(db: Session, valve: Valve, data: dict, cfg: dict) -> dict:
    """Store one reading, update the valve's latest values and re-run the rules. Sensors that
    are missing from the reading are stored as null, so they can't fake a flatline."""
    for k in TELEMETRY:
        if data.get(k) is not None:
            setattr(valve, k, data[k])
    db.add(Reading(valve_id=valve.id, ts=utcnow(), **{k: data.get(k) for k in TELEMETRY}))
    db.flush()
    return refresh_valve(db, valve, cfg)


def response_forecast(valve: Valve, recent: list[dict], th: dict) -> dict | None:
    series = [(r["ts"], r["response_ms"]) for r in recent]
    return forecast(series, valve.baseline_response_ms * th["response_inspect_ratio"],
                    min_std=max(valve.baseline_response_ms * 0.02, 1))


def build_evidence(db: Session, valve: Valve, cfg: dict) -> dict:
    """Everything the AI is allowed to see, all computed here. Stored with each report."""
    recent = recent_readings(db, valve.id)
    res = evaluate(eval_input(valve), recent, cfg)
    fc = response_forecast(valve, recent, res["thresholds"]) or {}
    return {"tag": valve.tag, "type": valve.type, "telemetry": telemetry(valve),
            "baseline_response_ms": valve.baseline_response_ms, "findings": res["findings"],
            "priority": res["priority"], "health": res["health"], "metrics": res["metrics"],
            "trend": {"slope_ms_per_hour": fc.get("slope_per_hour", 0),
                      "hours_to_inspect_threshold": fc.get("hours_to_threshold"),
                      "breach_probability_72h": fc.get("breach_probability_72h", 0)},
            "recent_response_ms": [r["response_ms"] for r in recent[-8:]],
            "recent_deviation_pct": [round(abs(r["position_pct"] - r["command_pct"]), 2) for r in recent[-8:]],
            "readings_used": len(recent), "computed_at": iso(utcnow())}


def month_start():
    return utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def plan_usage(db: Session, user: User) -> dict:
    free = user.org.plan == "free"
    return {"plan": user.org.plan,
            "valves_used": db.scalar(select(func.count(Valve.id)).where(Valve.org_id == user.org_id)),
            "valve_limit": FREE_VALVE_LIMIT if free else None,
            "reports_used_this_month": db.scalar(select(func.count(Report.id)).where(
                Report.org_id == user.org_id, Report.created_at >= month_start())),
            "report_limit": FREE_REPORTS_PER_MONTH if free else None}


def check_valve_quota(db: Session, user: User, adding: int = 1) -> None:
    u = plan_usage(db, user)
    if u["valve_limit"] is not None and u["valves_used"] + adding > u["valve_limit"]:
        raise HTTPException(403, f"The free plan includes up to {u['valve_limit']} valves. "
                                 f"You have {u['valves_used']}. Upgrade to add more.")


# ------------------------------------------------------------------ valves
class TelemetryIn(BaseModel):
    position_pct: float = Field(ge=0, le=100)
    command_pct: float = Field(ge=0, le=100)
    response_ms: float = Field(gt=0, le=120_000)
    pressure_bar: float | None = Field(default=None, ge=0, le=1000)
    temperature_c: float | None = Field(default=None, ge=-200, le=800)
    vibration_mm_s: float | None = Field(default=None, ge=0, le=200)


class ValveIn(TelemetryIn):
    tag: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9\-_.]+$")
    name: str = Field(default="", max_length=80)
    type: ValveType = "control"
    area: str = Field(default="", max_length=60)
    serial: str = Field(default="", max_length=60)
    baseline_response_ms: float = Field(default=800, gt=0, le=120_000)


class ValvePatch(BaseModel):
    tag: str | None = Field(default=None, min_length=1, max_length=30, pattern=r"^[A-Za-z0-9\-_.]+$")
    name: str | None = Field(default=None, max_length=80)
    type: ValveType | None = None
    area: str | None = Field(default=None, max_length=60)
    serial: str | None = Field(default=None, max_length=60)
    baseline_response_ms: float | None = Field(default=None, gt=0, le=120_000)


def _check_tag_free(db: Session, org_id: int, tag: str, own_id: int | None = None) -> None:
    other = db.scalar(select(Valve).where(Valve.org_id == org_id, Valve.tag == tag))
    if other and other.id != own_id:
        raise HTTPException(409, f"A valve with tag {tag} already exists.")


@router.get("/valves", tags=["valves"])
def list_valves(q: str = "", area: str = "", type: str = "", priority: str = "",
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Valve).where(Valve.org_id == user.org_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Valve.tag.ilike(like) | Valve.name.ilike(like) | Valve.area.ilike(like)
                          | Valve.finding.ilike(like))
    if area:
        stmt = stmt.where(Valve.area == area)
    if type:
        stmt = stmt.where(Valve.type == type)
    if priority == "flagged":
        stmt = stmt.where(Valve.priority != "normal")
    elif priority:
        if priority not in PRIORITIES:
            raise HTTPException(422, f"priority must be one of: flagged, {', '.join(PRIORITIES)}.")
        stmt = stmt.where(Valve.priority == priority)
    valves = sorted(db.scalars(stmt), key=lambda v: (PRIORITY_ORDER[v.priority], v.health, v.tag))
    # one query for every sparkline: response time over the last 12 hours
    trends: dict[int, list[float]] = {v.id: [] for v in valves}
    if valves:
        rows = db.execute(select(Reading.valve_id, Reading.response_ms)
                          .where(Reading.valve_id.in_(trends), Reading.ts >= utcnow() - timedelta(hours=12))
                          .order_by(Reading.ts, Reading.id))
        for vid, ms in rows:
            trends[vid].append(ms)
    return [valve_out(v, trends[v.id]) for v in valves]


@router.post("/valves", status_code=201, tags=["valves"])
def create_valve(body: ValveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    check_valve_quota(db, user)
    _check_tag_free(db, user.org_id, body.tag)
    meta = body.model_dump(include={"tag", "name", "type", "area", "serial", "baseline_response_ms"})
    valve = Valve(org_id=user.org_id, **{**meta, "name": meta["name"] or meta["tag"]})
    db.add(valve)
    db.flush()
    apply_reading(db, valve, body.model_dump(include=set(TELEMETRY)), get_settings(db, user.org_id))
    log_activity(db, user.org_id, "valve", f"Valve registered: {valve.tag}", valve.name)
    db.commit()
    return valve_out(valve)


@router.get("/valves/{valve_id}", tags=["valves"])
def get_valve(valve_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    valve = owned(db, Valve, valve_id, user, "Valve")
    res = evaluate(eval_input(valve), recent_readings(db, valve.id), get_settings(db, user.org_id))
    return {**valve_out(valve), "findings": res["findings"], "thresholds": res["thresholds"]}


@router.patch("/valves/{valve_id}", tags=["valves"])
def update_valve(valve_id: int, body: ValvePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    valve = owned(db, Valve, valve_id, user, "Valve")
    data = body.model_dump(exclude_unset=True)
    if "tag" in data:
        _check_tag_free(db, user.org_id, data["tag"], valve.id)
    for k, v in data.items():
        setattr(valve, k, v)
    if "baseline_response_ms" in data:
        refresh_valve(db, valve, get_settings(db, user.org_id))
    db.commit()
    return valve_out(valve)


@router.delete("/valves/{valve_id}", status_code=204, tags=["valves"])
def delete_valve(valve_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    valve = owned(db, Valve, valve_id, user, "Valve")
    log_activity(db, user.org_id, "valve", f"Valve removed: {valve.tag}", valve.name)
    db.delete(valve)
    db.commit()


@router.get("/valves/{valve_id}/readings", tags=["telemetry"])
def valve_readings(valve_id: int, limit: int = Query(48, ge=1, le=500),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned(db, Valve, valve_id, user, "Valve")
    return [{**r, "ts": iso(r["ts"])} for r in recent_readings(db, valve_id, limit)]


@router.post("/valves/{valve_id}/readings", status_code=201, tags=["telemetry"])
def add_reading(valve_id: int, body: TelemetryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    valve = owned(db, Valve, valve_id, user, "Valve")
    res = apply_reading(db, valve, body.model_dump(), get_settings(db, user.org_id))
    db.commit()
    return {"valve": valve_out(valve), "findings": res["findings"]}


@router.get("/valves/{valve_id}/prediction", tags=["telemetry"])
def valve_prediction(valve_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Response-time trend and forecast against the 'inspect soon' threshold."""
    valve = owned(db, Valve, valve_id, user, "Valve")
    th = thresholds(get_settings(db, user.org_id))
    fc = response_forecast(valve, recent_readings(db, valve.id), th)
    return {"metric": "response_ms", **(fc or {"actual": [], "forecast": [], "threshold": None,
                                            "slope_per_hour": 0, "hours_to_threshold": None,
                                            "breach_probability_72h": 0})}


# ------------------------------------------------------------------ AI investigation reports
class ReviewIn(BaseModel):
    decision: Review
    note: str = Field(default="", max_length=500)


@router.post("/valves/{valve_id}/reports", status_code=201, tags=["reports"])
def create_report(valve_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Build evidence from telemetry, ask the model to interpret it, store as pending review."""
    valve = owned(db, Valve, valve_id, user, "Valve")
    usage = plan_usage(db, user)
    if usage["report_limit"] is not None and usage["reports_used_this_month"] >= usage["report_limit"]:
        raise HTTPException(403, f"The free plan includes {usage['report_limit']} investigation reports "
                                 "per month, and this month's are used. Upgrade for more.")
    if not ai.allow_call(user.id):
        raise HTTPException(429, "AI investigation limit reached for this hour. Try again later.")
    evidence = build_evidence(db, valve, get_settings(db, user.org_id))
    res = ai.diagnose(evidence)
    log_ai(db, user, "report", valve.tag, res)
    rep = Report(org_id=user.org_id, valve_id=valve.id, created_by=user.id, evidence=json.dumps(evidence),
                 analysis=json.dumps(res["analysis"]), source=res["source"], model=res["model"],
                 error=(res["error"] or None) and res["error"][:240], latency_ms=res["latency_ms"])
    db.add(rep)
    log_activity(db, user.org_id, "report", f"AI report drafted: {valve.tag}", res["model"] or "rule-based")
    db.commit()
    return report_out(rep, {valve.id: valve.tag})


@router.get("/reports", tags=["reports"])
def list_reports(valve_id: int | None = None, review: str = "", limit: int = Query(50, ge=1, le=200),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Report).where(Report.org_id == user.org_id).order_by(Report.created_at.desc(), Report.id.desc())
    if valve_id is not None:
        stmt = stmt.where(Report.valve_id == valve_id)
    if review:
        stmt = stmt.where(Report.review == review)
    tags = tag_map(db, user.org_id)
    return [report_out(r, tags) for r in db.scalars(stmt.limit(limit))]


@router.get("/reports/{report_id}", tags=["reports"])
def get_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return report_out(owned(db, Report, report_id, user, "Report"), tag_map(db, user.org_id))


@router.post("/reports/{report_id}/review", tags=["reports"])
def review_report(report_id: int, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rep = owned(db, Report, report_id, user, "Report")
    rep.review, rep.review_note = body.decision, body.note.strip()
    rep.reviewed_by, rep.reviewed_at = user.name, utcnow()
    tags = tag_map(db, user.org_id)
    if body.decision == "accepted":  # someone now owns the investigation
        for a in db.scalars(select(Alert).where(Alert.valve_id == rep.valve_id, Alert.status == "open")):
            a.status = "acknowledged"
    label = {"accepted": "accepted", "needs_data": "marked needs more data", "false_positive": "marked false positive"}
    log_activity(db, user.org_id, "review", f"Report #{rep.id} {label[body.decision]}",
                 f"{tags.get(rep.valve_id, '')} · {user.name}")
    db.commit()
    return report_out(rep, tags)


# ------------------------------------------------------------------ alerts
class AlertIn(BaseModel):
    valve_id: int | None = None
    severity: Severity
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)


class AlertPatch(BaseModel):
    severity: Severity | None = None
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: Literal["open", "acknowledged", "resolved"] | None = None


@router.get("/alerts", tags=["alerts"])
def list_alerts(status: str = "", severity: str = "", valve_id: int | None = None,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Alert).where(Alert.org_id == user.org_id)
    if status == "active":
        stmt = stmt.where(Alert.status != "resolved")
    elif status:
        stmt = stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if valve_id is not None:
        stmt = stmt.where(Alert.valve_id == valve_id)
    tags = tag_map(db, user.org_id)
    alerts = sorted(db.scalars(stmt), key=lambda a: (SEV_ORDER[a.severity], -a.created_at.timestamp()))
    return [alert_out(a, tags) for a in alerts]


@router.post("/alerts", status_code=201, tags=["alerts"])
def create_alert(body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.valve_id is not None:
        owned(db, Valve, body.valve_id, user, "Valve")
    alert = Alert(org_id=user.org_id, **body.model_dump(), source="manual")
    db.add(alert)
    log_activity(db, user.org_id, "alert", f"Alert created: {alert.title}", user.name)
    db.commit()
    return alert_out(alert, tag_map(db, user.org_id))


@router.patch("/alerts/{alert_id}", tags=["alerts"])
def update_alert(alert_id: int, body: AlertPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    alert = owned(db, Alert, alert_id, user, "Alert")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(alert, k, v)
    if "status" in data:
        log_activity(db, user.org_id, "alert", f"Alert {data['status']}: {alert.title}", user.name)
    db.commit()
    return alert_out(alert, tag_map(db, user.org_id))


@router.delete("/alerts/{alert_id}", status_code=204, tags=["alerts"])
def delete_alert(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(db, Alert, alert_id, user, "Alert"))
    db.commit()


# ------------------------------------------------------------------ settings
class SettingsPatch(BaseModel):
    sensitivity: Literal["strict", "standard", "relaxed"] | None = None
    temperature_alarm: float | None = Field(default=None, gt=0, le=800)
    vibration_alarm: float | None = Field(default=None, gt=0, le=200)


@router.get("/settings", tags=["settings"])
def read_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cfg = get_settings(db, user.org_id)
    return {**cfg, "thresholds": thresholds(cfg)}


@router.patch("/settings", tags=["settings"])
def update_settings(body: SettingsPatch, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        row = db.get(Setting, (user.org_id, k))
        if row:
            row.value = str(v)
        else:
            db.add(Setting(org_id=user.org_id, key=k, value=str(v)))
    db.flush()
    cfg = get_settings(db, user.org_id)
    for valve in db.scalars(select(Valve).where(Valve.org_id == user.org_id)):  # new limits apply now
        refresh_valve(db, valve, cfg)
    db.commit()
    return {**cfg, "thresholds": thresholds(cfg)}


# ------------------------------------------------------------------ fleet
@router.get("/fleet/overview", tags=["fleet"])
def fleet_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every number on the Fleet Overview, computed from stored rows."""
    valves = list(db.scalars(select(Valve).where(Valve.org_id == user.org_id)))
    counts = {p: sum(1 for v in valves if v.priority == p) for p in PRIORITIES}
    active = list(db.scalars(select(Alert).where(Alert.org_id == user.org_id, Alert.status != "resolved")))
    areas: dict[str, dict] = {}
    for v in valves:
        a = areas.setdefault(v.area or "Unassigned", {"area": v.area or "Unassigned", "valves": 0, "flagged": 0})
        a["valves"] += 1
        a["flagged"] += v.priority != "normal"
    tags = {v.id: v.tag for v in valves}
    recent = sorted(active, key=lambda a: (SEV_ORDER[a.severity], -a.created_at.timestamp()))[:5]
    activity = db.scalars(select(Activity).where(Activity.org_id == user.org_id)
                          .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(6))
    pending = db.scalar(select(func.count(Report.id)).where(Report.org_id == user.org_id,
                                                            Report.review == "pending"))
    return {
        "org": {"name": user.org.name, **plan_usage(db, user)},
        "valves": {"total": len(valves), "flagged": len(valves) - counts["normal"], **counts},
        "avg_health": round(sum(v.health for v in valves) / len(valves)) if valves else None,
        "alerts": {"active": len(active), **{s: sum(1 for a in active if a.severity == s) for s in SEV_ORDER}},
        "reports_pending_review": pending,
        "areas": sorted(areas.values(), key=lambda a: a["area"]),
        "recent_alerts": [alert_out(a, tags) for a in recent],
        "activity": [{"id": a.id, "kind": a.kind, "text": a.text, "detail": a.detail,
                      "created_at": iso(a.created_at)} for a in activity],
    }


@router.post("/fleet/demo", status_code=201, tags=["fleet"])
def load_demo_fleet(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Add the 20 simulated valves (V-101..V-121) with 12 hours of telemetry to this organisation."""
    from .seed import DEMO_VALVES, seed_demo_fleet
    if db.scalar(select(func.count(Valve.id)).where(Valve.org_id == user.org_id)):
        raise HTTPException(409, "Your fleet already has valves. The demo fleet can only be loaded into an empty fleet.")
    check_valve_quota(db, user, len(DEMO_VALVES))
    try:
        seed_demo_fleet(db, user.org_id, get_settings(db, user.org_id))
        log_activity(db, user.org_id, "valve", f"Demo fleet loaded: {len(DEMO_VALVES)} simulated valves", user.name)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The demo fleet is already loading. Refresh the page.")
    return fleet_overview(user, db)


@router.get("/activity", tags=["fleet"])
def list_activity(limit: int = Query(20, ge=1, le=100), user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    rows = db.scalars(select(Activity).where(Activity.org_id == user.org_id)
                      .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit))
    return [{"id": a.id, "kind": a.kind, "text": a.text, "detail": a.detail, "created_at": iso(a.created_at)}
            for a in rows]
