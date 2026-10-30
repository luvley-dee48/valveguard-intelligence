"""System page backend: lets a person verify auth, tables, seeded rows, API traffic and Gemma 4."""
from collections import deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai
from .auth import current_user, user_out
from .config import SEED_DEMO_DATA, TOKEN_HOURS
from .db import AiCall, Base, User, engine, get_db, iso, utcnow
from .api import log_ai

REQUESTS: deque = deque(maxlen=300)  # filled by the middleware in main.py
router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(current_user)])


@router.get("/status")
def status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tables = [{"name": name, "rows": db.scalar(select(func.count()).select_from(t)),
               "columns": [c.name for c in t.columns if c.name != "password_hash"]}
              for name, t in Base.metadata.tables.items()]
    return {
        "user": user_out(user), "token_hours": TOKEN_HOURS,
        "password_storage": "PBKDF2-SHA256, 240,000 rounds, random salt per user (never stored in plain text)",
        "database": {"dialect": engine.dialect.name, "url": engine.url.render_as_string(hide_password=True),
                     "tables": tables},
        "seed_demo_data": SEED_DEMO_DATA, "ai": ai.status(),
        "ai_calls": {"total": db.scalar(select(func.count(AiCall.id))),
                     "by_gemma": db.scalar(select(func.count(AiCall.id)).where(AiCall.source == "gemini"))},
    }


@router.get("/tables/{name}")
def table_rows(name: str, limit: int = Query(8, ge=1, le=50), user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    table = Base.metadata.tables.get(name)
    if table is None:
        raise HTTPException(404, "No such table.")
    if name == "users" and user.role != "admin":
        raise HTTPException(403, "Only an admin can view the users table.")
    cols = [c for c in table.columns if c.name != "password_hash"]
    pk = list(table.primary_key.columns)[0]
    rows = db.execute(select(*cols).order_by(pk.desc()).limit(limit)).mappings().all()
    return {"table": name, "columns": [c.name for c in cols],
            "rows": [{k: (iso(v) if isinstance(v, datetime) else v) for k, v in r.items()} for r in rows]}


@router.get("/requests")
def requests_log():
    return list(reversed(REQUESTS))


@router.get("/ai-calls")
def ai_calls(limit: int = Query(15, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(AiCall).order_by(AiCall.id.desc()).limit(limit))
    return [{"id": c.id, "ts": iso(c.ts), "kind": c.kind, "asset_tag": c.asset_tag, "model": c.model,
             "api_model_version": c.api_model_version, "source": c.source, "error": c.error,
             "latency_ms": c.latency_ms, "response_preview": c.response_preview} for c in rows]


@router.post("/ai-selftest")
def ai_selftest(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not ai.allow_call(user.id):
        raise HTTPException(429, "AI limit reached for this hour. Try again later.")
    result = ai.selftest()
    if result.get("configured"):
        log_ai(db, user, "selftest", "C-201", {"source": "gemini" if result["ok"] else "rules",
               "model": result["model"] if result["ok"] else None, "api_model_version": result["api_model_version"],
               "error": result["error"], "latency_ms": result["latency_ms"],
               "response_preview": (result["raw_reply"] or "")[:600]})
        db.commit()
    return result
