"""Authentication: sign up, log in, Google sign-in, JWT bearer tokens, PBKDF2 password hashing.

Every account belongs to an organisation. Signing up creates a new organisation and makes the
user its admin; all data access is scoped to that organisation (see app/api.py).
"""
import hashlib
import hmac
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import GOOGLE_CLIENT_ID, SECRET_KEY, TOKEN_HOURS
from .db import Activity, Org, User, get_db, iso

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_ROUNDS = 240_000
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, rounds, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(check.hex(), digest)
    except (ValueError, TypeError):
        return False


def make_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "org": user.org_id, "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Log in to continue.")
    try:
        data = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        user = db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Your session has expired. Log in again.")
    if not user:
        raise HTTPException(401, "This account no longer exists.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "This action needs the admin role.")
    return user


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "created_at": iso(u.created_at),
            "org": {"id": u.org.id, "name": u.org.name, "plan": u.org.plan},
            "has_password": bool(u.password_hash), "google_linked": bool(u.google_sub)}


def session_out(u: User, created: bool = False) -> dict:
    return {"token": make_token(u), "user": user_out(u), "created": created}


# --- tiny in-memory login throttle (per client + email) ---
_attempts: dict[str, deque] = defaultdict(deque)


def _throttle(key: str, limit: int = 8, window: int = 60) -> None:
    now = time.time()
    q = _attempts[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    q.append(now)


def _new_account(db: Session, name: str, email: str, company: str, **extra) -> User:
    org = Org(name=company.strip() or f"{name}'s team")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, name=name, email=email, role="admin", **extra)
    db.add(user)
    db.add(Activity(org_id=org.id, kind="user", text=f"Account created: {name}", detail=org.name))
    db.commit()
    return user


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=160)
    password: str = Field(min_length=8, max_length=128)
    company: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return v.strip()


class LoginIn(BaseModel):
    email: str
    password: str


class GoogleIn(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)  # the ID token from Google Identity Services


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    password: str | None = Field(default=None, min_length=8, max_length=128)


@router.post("/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists. Log in instead.")
    user = _new_account(db, body.name, body.email, body.company, password_hash=hash_password(body.password))
    return session_out(user, created=True)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    _throttle(f"{request.client.host if request.client else '-'}:{email}")
    user = db.scalar(select(User).where(User.email == email))
    if user and not user.password_hash and user.google_sub:
        raise HTTPException(401, "This account uses Google sign-in. Use Continue with Google.")
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return session_out(user)


# --- Google sign-in -----------------------------------------------------------------------
_jwks: jwt.PyJWKClient | None = None


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token's signature, audience, issuer and expiry. Returns its claims."""
    global _jwks
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not configured on the server (set GOOGLE_CLIENT_ID).")
    if _jwks is None:
        _jwks = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True)
    try:
        key = _jwks.get_signing_key_from_jwt(credential)
        claims = jwt.decode(credential, key.key, algorithms=["RS256"], audience=GOOGLE_CLIENT_ID,
                            issuer=GOOGLE_ISSUERS)
    except jwt.PyJWKClientError:
        raise HTTPException(502, "Could not reach Google to verify the sign-in. Try again.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Google sign-in could not be verified. Try again.")
    return claims


@router.post("/google")
def google(body: GoogleIn, request: Request, db: Session = Depends(get_db)):
    _throttle(f"{request.client.host if request.client else '-'}:google", limit=20)
    claims = verify_google_token(body.credential)
    if not claims.get("email") or not claims.get("email_verified"):
        raise HTTPException(401, "Your Google account has no verified email address.")
    sub, email = str(claims["sub"]), claims["email"].strip().lower()
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user:
        return session_out(user)
    user = db.scalar(select(User).where(User.email == email))
    if user:  # Google has verified this email, so link it to the existing account
        user.google_sub = sub
        db.commit()
        return session_out(user)
    name = (claims.get("name") or email.split("@")[0])[:80]
    user = _new_account(db, name, email, "", google_sub=sub)
    return session_out(user, created=True)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name:
        user.name = body.name.strip()
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user_out(user)
