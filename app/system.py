"""System page backend: lets a person verify auth, tables, API traffic and the AI connection.
Everything is scoped to the caller's organisation; other organisations' rows are never exposed."""
from collections import deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai
from .api import log_ai
from .auth import current_user, require_admin, user_out
from .config import GOOGLE_CLIENT_ID, TOKEN_HOURS
from .db import AiCall, Base, User, engine, get_db, iso

REQUESTS: deque = deque(maxlen=300)  # filled by the middleware in main.py; entries carry the org id
router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(current_user)])

# Tables that hold per-organisation rows, and the column that scopes them.
ORG_SCOPED = {"valves": "org_id", "alerts": "org_id", "reports": "org_id", "activity": "org_id",
              "ai_calls": "org_id", "users": "org_id"}


@router.get("/status")
def status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tables = []
    for name, col in ORG_SCOPED.items():
        t = Base.metadata.tables[name]
        tables.append({"name": name, "rows": db.scalar(select(func.count()).select_from(t).where(t.c[col] == user.org_id)),
                       "columns": [c.name for c in t.columns if c.name not in ("password_hash", "google_sub")]})
    return {
        "user": user_out(user), "token_hours": TOKEN_HOURS,
        "password_storage": "PBKDF2-SHA256, 240,000 rounds, random salt per user (never stored in plain text)",
        "google_sign_in": bool(GOOGLE_CLIENT_ID),
        "database": {"dialect": engine.dialect.name, "tables": tables}, "ai": ai.status(),
        "ai_calls": {"total": db.scalar(select(func.count(AiCall.id)).where(AiCall.org_id == user.org_id)),
                     "by_model": db.scalar(select(func.count(AiCall.id)).where(
                         AiCall.org_id == user.org_id, AiCall.source == "gemini"))},
    }


@router.get("/tables/{name}")
def table_rows(name: str, limit: int = Query(8, ge=1, le=50), user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    if name not in ORG_SCOPED:
        raise HTTPException(404, "No such table.")
    if name == "users" and user.role != "admin":
        raise HTTPException(403, "Only an admin can view the users table.")
    table = Base.metadata.tables[name]
    cols = [c for c in table.columns if c.name not in ("password_hash", "google_sub")]
    pk = list(table.primary_key.columns)[0]
    rows = db.execute(select(*cols).where(table.c[ORG_SCOPED[name]] == user.org_id)
                      .order_by(pk.desc()).limit(limit)).mappings().all()
    return {"table": name, "columns": [c.name for c in cols],
            "rows": [{k: (iso(v) if isinstance(v, datetime) else v) for k, v in r.items()} for r in rows]}


@router.get("/requests")
def requests_log(user: User = Depends(current_user)):
    return [{k: v for k, v in r.items() if k != "org"} for r in reversed(REQUESTS) if r.get("org") == user.org_id]


@router.get("/ai-calls")
def ai_calls(limit: int = Query(15, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AiCall).where(AiCall.org_id == user.org_id).order_by(AiCall.id.desc()).limit(limit))
    return [{"id": c.id, "ts": iso(c.ts), "kind": c.kind, "valve_tag": c.valve_tag, "model": c.model,
             "api_model_version": c.api_model_version, "source": c.source, "error": c.error,
             "latency_ms": c.latency_ms, "response_preview": c.response_preview} for c in rows]


@router.post("/ai-selftest")
def ai_selftest(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not ai.allow_call(user.id):
        raise HTTPException(429, "AI limit reached for this hour. Try again later.")
    result = ai.selftest()
    if result.get("configured"):
        log_ai(db, user, "selftest", "V-113", {"source": "gemini" if result["ok"] else "rules",
               "model": result["model"] if result["ok"] else None, "api_model_version": result["api_model_version"],
               "error": result["error"], "latency_ms": result["latency_ms"],
               "response_preview": (result["raw_reply"] or "")[:600]})
        db.commit()
    return result
