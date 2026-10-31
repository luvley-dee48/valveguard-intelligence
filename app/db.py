"""Database engine, session and ORM models (SQLite by default, any SQLAlchemy URL works).

Tenancy: every user belongs to one organisation, and every valve, alert, report and log row
carries an org_id. API queries always filter on the caller's org_id.
"""
from datetime import datetime, timezone

from sqlalchemy import (DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column, relationship,
                            sessionmaker)

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


class Base(DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "orgs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | professional | enterprise
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(300), nullable=True)  # null for Google-only accounts
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="admin")  # admin | operator
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    org: Mapped[Org] = relationship(lazy="joined")


class Valve(Base):
    __tablename__ = "valves"
    __table_args__ = (UniqueConstraint("org_id", "tag"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    tag: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(20), default="control")  # control|globe|ball|butterfly|gate|check
    area: Mapped[str] = mapped_column(String(60), default="")
    serial: Mapped[str] = mapped_column(String(60), default="")
    # latest telemetry
    position_pct: Mapped[float] = mapped_column(Float, default=0)
    command_pct: Mapped[float] = mapped_column(Float, default=0)
    response_ms: Mapped[float] = mapped_column(Float, default=0)
    baseline_response_ms: Mapped[float] = mapped_column(Float, default=800)
    pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration_mm_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    # derived by app/analytics.py, never by the AI
    health: Mapped[int] = mapped_column(Integer, default=100)
    priority: Mapped[str] = mapped_column(String(16), default="normal", index=True)
    finding: Mapped[str] = mapped_column(String(160), default="Within baseline")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    readings: Mapped[list["Reading"]] = relationship(cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(cascade="all, delete-orphan")


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    valve_id: Mapped[int] = mapped_column(ForeignKey("valves.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    position_pct: Mapped[float] = mapped_column(Float)
    command_pct: Mapped[float] = mapped_column(Float)
    response_ms: Mapped[float] = mapped_column(Float)
    pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration_mm_s: Mapped[float | None] = mapped_column(Float, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    valve_id: Mapped[int | None] = mapped_column(ForeignKey("valves.id"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(10), index=True)  # critical|high|medium|low
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(14), default="open", index=True)  # open|acknowledged|resolved
    source: Mapped[str] = mapped_column(String(12), default="manual")  # rule|manual
    rule_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Report(Base):
    """One AI investigation of one valve. Evidence is computed by the backend; the model
    only interprets it. A person records the outcome in `review`."""
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    valve_id: Mapped[int] = mapped_column(ForeignKey("valves.id"), index=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[str] = mapped_column(Text)  # JSON: findings + metrics sent to the model
    analysis: Mapped[str] = mapped_column(Text)  # JSON: validated model (or rules) output
    source: Mapped[str] = mapped_column(String(12))  # gemini | rules
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error: Mapped[str | None] = mapped_column(String(240), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    review: Mapped[str] = mapped_column(String(16), default="pending")  # pending|accepted|needs_data|false_positive
    review_note: Mapped[str] = mapped_column(String(500), default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # valve|alert|report|review|user
    text: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AiCall(Base):
    """Every model call (or fallback) is logged so the AI's real contribution is auditable."""
    __tablename__ = "ai_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # report | selftest
    valve_tag: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)  # null when rules answered
    api_model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(12))  # gemini | rules
    error: Mapped[str | None] = mapped_column(String(240), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    response_preview: Mapped[str] = mapped_column(Text, default="")


class Setting(Base):
    __tablename__ = "settings"
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(engine)
