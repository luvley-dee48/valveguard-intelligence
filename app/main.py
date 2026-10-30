"""Nexora backend. Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import time

from . import ai, auth, system
from .api import router as api_router
from .config import BASE_DIR, CORS_ORIGINS, SEED_DEMO_DATA
from .db import SessionLocal, init_db, iso, utcnow
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    st = ai.status()
    print(f"[nexora] Gemma 4 inference: {'ENABLED' if st['configured'] else 'DISABLED (no GEMINI_API_KEY, rule-based fallback)'}"
          f" | model={st['model']} | gemma4={st['is_gemma4']}", flush=True)
    if SEED_DEMO_DATA:
        with SessionLocal() as db:
            seed_if_empty(db)
    yield


app = FastAPI(title="Nexora Industrial Intelligence API", version="1.0.0", lifespan=lifespan)

if CORS_ORIGINS:  # the bundled frontend is same-origin and needs no CORS
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"],
                       allow_headers=["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def request_log(request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api") and path != "/api/system/requests":
        system.REQUESTS.append({"ts": iso(utcnow()), "method": request.method, "path": path,
                                "status": response.status_code, "ms": round((time.perf_counter() - t0) * 1000)})
    return response


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "ai": ai.status()}


app.include_router(auth.router)
app.include_router(api_router)
app.include_router(system.router)
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
