"""Database engine, session and ORM models (SQLite by default, any SQLAlchemy URL works)."""
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
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


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="operator")  # admin | operator
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(30), index=True)
    plant: Mapped[str] = mapped_column(String(60), default="North Plant")
    location: Mapped[str] = mapped_column(String(80), default="")
    serial: Mapped[str] = mapped_column(String(60), default="")
    vibration: Mapped[float] = mapped_column(Float, default=0)
    temperature: Mapped[float] = mapped_column(Float, default=25)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    flow_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    health: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(12), default="healthy")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    readings: Mapped[list["Reading"]] = relationship(cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(cascade="all, delete-orphan")
    insights: Mapped[list["Insight"]] = relationship(cascade="all, delete-orphan")


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    vibration: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    flow_rate: Mapped[float | None] = mapped_column(Float, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(10), index=True)  # critical|high|medium|low
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(14), default="open", index=True)  # open|acknowledged|resolved
    source: Mapped[str] = mapped_column(String(12), default="manual")  # rule|manual
    rule_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ai_review: Mapped[str] = mapped_column(String(12), default="none")  # none|pending|approved|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(14))  # anomaly|optimization|predictive
    title: Mapped[str] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|approved|dismissed
    source: Mapped[str] = mapped_column(String(12), default="manual")  # gemini|rules|manual|seed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    steps: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of {kind,label,detail}
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # work_order|calibration|model|sync|asset|alert|workflow|user
    text: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(30), default="CMMS")
    detail: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(14), default="connected")  # connected|disconnected
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Metric(Base):
    """Plant KPIs that need an external source (MTBF, OEE, energy). Editable until integrated."""
    __tablename__ = "metrics"
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float, default=0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(engine)
