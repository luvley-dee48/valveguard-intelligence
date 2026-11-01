"""Public entry point for the live demo page (src/routes/demo.tsx).

A visitor presses "Start demo" and the browser calls POST /api/demo/session once. That creates a
throwaway organisation, seeds the same 20 simulated valves the product uses (app/seed.py) and
returns a JWT for it, so the demo can run a real investigation without a sign-up form.

Nothing here special-cases inference: the page then calls the ordinary
POST /api/valves/{id}/reports endpoint, which calls app/ai.py exactly like a signed-up team's
request would. The session is isolated by org_id like every other row in the database.
"""
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import ai
from .api import get_settings
from .auth import hash_password, session_out
from .db import Activity, Org, User, get_db
from .seed import DEMO_VALVES, seed_demo_fleet

router = APIRouter(prefix="/api/demo", tags=["demo"])

# A public endpoint that writes rows needs a ceiling. Sessions are cheap and isolated, but a
# loop shouldn't be able to fill the disk; this is per-instance, like the other throttles.
SESSIONS_PER_HOUR_PER_CLIENT = 12
_sessions: dict[str, deque] = defaultdict(deque)


def _throttle(client: str) -> None:
    now = time.time()
    q = _sessions[client]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= SESSIONS_PER_HOUR_PER_CLIENT:
        raise HTTPException(429, "Too many demo sessions from this address. Wait a little, then try again.")
    q.append(now)


@router.get("/ai-status")
def ai_status() -> dict:
    """What the browser needs to label model output honestly. Never includes the API key."""
    return {**ai.status(), "documented_models": ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]}


@router.post("/session", status_code=201)
def demo_session(request: Request, db: Session = Depends(get_db)) -> dict:
    _throttle(request.client.host if request.client else "-")
    org = Org(name="Live demo · simulated fleet")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, name="Demo visitor", role="admin",
                email=f"demo+{secrets.token_hex(6)}@valveguard.example",
                password_hash=hash_password(secrets.token_urlsafe(24)))
    db.add(user)
    db.flush()
    db.add(Activity(org_id=org.id, kind="user", text="Demo session created",
                    detail=f"{len(DEMO_VALVES)} simulated valves"))
    seed_demo_fleet(db, org.id, get_settings(db, org.id))
    db.commit()
    return {**session_out(user, created=True), "valves": len(DEMO_VALVES)}
