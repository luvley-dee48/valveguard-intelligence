"""ValveGuard backend API. Run:  uvicorn app.main:app --reload --port 8000

This service is API-only. The React app in src/ is the frontend and calls it over HTTPS.
"""
import time
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import ai, auth, system
from .api import router as api_router
from .config import CORS_ORIGIN_REGEX, CORS_ORIGINS, GOOGLE_CLIENT_ID, SECRET_KEY
from .db import init_db, iso, utcnow


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    st = ai.status()
    print(f"[valveguard] AI: {'ENABLED' if st['configured'] else 'DISABLED (no GEMINI_API_KEY, rule-based fallback)'}"
          f" | model={st['model']} | google sign-in: {'ON' if GOOGLE_CLIENT_ID else 'OFF (no GOOGLE_CLIENT_ID)'}",
          flush=True)
    yield


app = FastAPI(title="ValveGuard API", version="2.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_origin_regex=CORS_ORIGIN_REGEX,
                   allow_methods=["*"], allow_headers=["*"], max_age=600)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _org_of(request) -> int | None:
    """Org id from the bearer token, only used to file the request in the right org's log."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        return jwt.decode(header[7:], SECRET_KEY, algorithms=["HS256"]).get("org")
    except jwt.PyJWTError:
        return None


@app.middleware("http")
async def request_log(request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    org = _org_of(request)
    if path.startswith("/api") and org is not None and path != "/api/system/requests":
        system.REQUESTS.append({"org": org, "ts": iso(utcnow()), "method": request.method, "path": path,
                                "status": response.status_code, "ms": round((time.perf_counter() - t0) * 1000)})
    return response


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "ai": {"configured": ai.status()["configured"]},
            "google_client_id": GOOGLE_CLIENT_ID or None}


app.include_router(auth.router)
app.include_router(api_router)
app.include_router(system.router)
