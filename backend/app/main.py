
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    create_engine,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    select,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
    Session,
)

from .auth_model import analyze_authentication

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./sentinelai.db"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


# ============================================================
# DATABASE MODELS
# ============================================================

class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )

    user: Mapped[str] = mapped_column(
        String(255), index=True
    )

    type: Mapped[str] = mapped_column(
        String(60), index=True
    )

    ip: Mapped[str] = mapped_column(String(45))

    country: Mapped[str] = mapped_column(String(2))

    failed_logins: Mapped[int] = mapped_column(
        Integer, default=0
    )

    privileged_token: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    description: Mapped[str] = mapped_column(
        String(1000), default=""
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )

    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), index=True
    )

    risk_score: Mapped[int] = mapped_column(Integer)

    severity: Mapped[str] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(
        String(40),
        default="awaiting_human_review"
    )

    evidence: Mapped[list] = mapped_column(JSON)

    recommended_actions: Mapped[list] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str = Field(
        min_length=1,
        max_length=255
    )

    type: Literal[
        "impossible_travel",
        "brute_force",
        "normal_login",
        "token_creation",
        "failed_login",
        "privilege_escalation",
    ]

    ip: str = Field(min_length=3, max_length=45)

    country: str = Field(min_length=2, max_length=2)

    failed_logins: int = Field(
        default=0,
        ge=0,
        le=100000
    )

    privileged_token: bool = False

    description: str = Field(
        default="",
        max_length=1000
    )

    occurred_at: datetime | None = None


class StatusInput(BaseModel):
    status: Literal[
        "awaiting_human_review",
        "in_progress",
        "resolved",
        "dismissed",
    ]


# ============================================================
# DEMO SECURITY EVENTS
# ============================================================

SEEDS = [
    dict(
        id="evt-001",
        user="alex@example.test",
        type="impossible_travel",
        ip="198.51.100.24",
        country="RU",
        failed_logins=37,
        privileged_token=True,
        description=(
            "Rapid geo-change with privileged token creation"
        ),
    ),
    dict(
        id="evt-002",
        user="jordan@example.test",
        type="brute_force",
        ip="203.0.113.10",
        country="US",
        failed_logins=22,
        privileged_token=False,
        description="Repeated failed authentication attempts",
    ),
    dict(
        id="evt-003",
        user="sam@example.test",
        type="normal_login",
        ip="192.0.2.8",
        country="US",
        failed_logins=0,
        privileged_token=False,
        description="Successful login from known location",
    ),
    dict(
        id="evt-004",
        user="taylor@example.test",
        type="token_creation",
        ip="203.0.113.55",
        country="US",
        failed_logins=3,
        privileged_token=True,
        description="Privileged token created after failed logins",
    ),
]


def seed(db: Session):
    count = db.scalar(
        select(func.count()).select_from(Event)
    )

    if count == 0:
        for item in SEEDS:
            db.add(
                Event(
                    **item,
                    occurred_at=datetime.now(timezone.utc)
                )
            )

        db.commit()


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Prototype schema initialization.
    # Production systems should use Alembic migrations.
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        seed(db)

    yield


app = FastAPI(
    title="SentinelAI",
    version="0.3.0",
    lifespan=lifespan
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
    ],
    allow_headers=["*"],
)


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():
    with SessionLocal() as db:
        yield db


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def serialize_event(e: Event):
    return {
        k: getattr(e, k)
        for k in (
            "id",
            "user",
            "type",
            "ip",
            "country",
            "failed_logins",
            "privileged_token",
            "description",
            "occurred_at",
        )
    }


def serialize_investigation(
    i: Investigation,
    e: Event
):
    return {
        "id": i.id,
        "event_id": i.event_id,
        "user": e.user,
        "risk_score": i.risk_score,
        "severity": i.severity,
        "evidence": i.evidence,
        "recommended_actions": i.recommended_actions,
        "status": i.status,
        "auto_actions_executed": False,
        "summary": (
            f"{i.severity.upper()} risk for {e.user}: "
            f"{len(i.evidence)} corroborating signal(s)."
        ),
        "scoring_method": (
            "Deterministic prototype rules, "
            "not a calibrated probability."
        ),
        "authentication_analysis": analyze_authentication(e.type, e.failed_logins),
        "created_at": i.created_at,
    }


# ============================================================
# RULE-BASED THREAT DETECTION ENGINE
# ============================================================

def detect(e: Event, db: Session):

    score = 0
    evidence = []

    def add(signal, points, detail):
        nonlocal score

        score += points

        evidence.append({
            "signal": signal,
            "points": points,
            "detail": detail,
        })

    # --------------------------------------------------------
    # Impossible travel
    # --------------------------------------------------------

    if e.type == "impossible_travel":
        add(
            "Impossible travel",
            45,
            "Reported geo-velocity anomaly "
            "(requires upstream verification)"
        )

    # --------------------------------------------------------
    # Failed authentication attempts
    # --------------------------------------------------------

    if e.failed_logins >= 20:
        add(
            "Authentication failures",
            25,
            f"{e.failed_logins} failed attempts"
        )

    elif e.failed_logins >= 5:
        add(
            "Authentication failures",
            10,
            f"{e.failed_logins} failed attempts"
        )

    # --------------------------------------------------------
    # Privileged token
    # --------------------------------------------------------

    if e.privileged_token:
        add(
            "Privileged token",
            24,
            "New privileged token detected"
        )

    # --------------------------------------------------------
    # Brute-force pattern
    # --------------------------------------------------------

    if e.type == "brute_force":
        add(
            "Brute force pattern",
            30,
            "Source classified as brute-force activity"
        )

    # --------------------------------------------------------
    # Privilege escalation
    # --------------------------------------------------------

    if e.type == "privilege_escalation":
        add(
            "Privilege escalation",
            40,
            "Source classified as privilege escalation"
        )

    # --------------------------------------------------------
    # Repeated failed logins in a 15-minute window
    # --------------------------------------------------------

    since = (
        e.occurred_at.replace(tzinfo=None)
        - timedelta(minutes=15)
    )

    count = db.scalar(
        select(func.count())
        .select_from(Event)
        .where(
            Event.user == e.user,
            Event.type == "failed_login",
            Event.occurred_at >= since,
            Event.occurred_at <= e.occurred_at.replace(
                tzinfo=None
            ),
        )
    ) or 0

    if count >= 5:
        add(
            "Repeated failures in 15 minutes",
            20,
            f"{count} stored failed-login events"
        )

    # --------------------------------------------------------
    # Risk score
    # --------------------------------------------------------

    score = min(score, 100)

    if score >= 85:
        severity = "critical"

    elif score >= 60:
        severity = "high"

    elif score >= 30:
        severity = "medium"

    else:
        severity = "low"

    # --------------------------------------------------------
    # Recommended actions
    # --------------------------------------------------------

    if score < 60:
        actions = [
            "Review activity and verify identity"
        ]

    else:
        actions = [
            "Request analyst review",
            "Consider token revocation",
            "Consider credential reset",
        ]

    return score, severity, evidence, actions


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": app.version
    }


# ============================================================
# EVENT ENDPOINTS
# ============================================================

@app.get("/api/events")
def list_events(
    db: Session = Depends(get_db)
):
    events = db.scalars(
        select(Event)
        .order_by(Event.occurred_at.desc())
        .limit(200)
    ).all()

    return [
        serialize_event(e)
        for e in events
    ]


@app.get("/api/events/{event_id}")
def event_detail(
    event_id: str,
    db: Session = Depends(get_db)
):
    e = db.get(Event, event_id)

    if not e:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return serialize_event(e)


@app.post("/api/events", status_code=201)
def ingest_event(
    payload: EventInput,
    db: Session = Depends(get_db)
):
    e = Event(
        id="evt-" + uuid4().hex[:12],
        **payload.model_dump(
            exclude={"occurred_at"}
        ),
        occurred_at=(
            payload.occurred_at
            or datetime.now(timezone.utc)
        ),
    )

    db.add(e)
    db.commit()

    return serialize_event(e)


# ============================================================
# INVESTIGATION ENDPOINTS
# ============================================================

@app.post("/api/investigations/{event_id}")
def run_investigation(
    event_id: str,
    db: Session = Depends(get_db)
):
    e = db.get(Event, event_id)

    if not e:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    # Check whether this event has already been investigated.
    existing = db.scalars(
        select(Investigation)
        .where(
            Investigation.event_id == event_id
        )
        .order_by(
            Investigation.created_at.desc()
        )
    ).first()

    # Reuse the latest existing report.
    if existing:
        return serialize_investigation(existing, e)

    # Run the threat detection engine.
    score, severity, evidence, actions = detect(e, db)

    # Save a new investigation.
    i = Investigation(
        id="inv-" + uuid4().hex[:12],
        event_id=e.id,
        risk_score=score,
        severity=severity,
        evidence=evidence,
        recommended_actions=actions,
        status="awaiting_human_review",
        created_at=datetime.now(timezone.utc),
    )

    db.add(i)
    db.commit()

    return serialize_investigation(i, e)


@app.get("/api/investigations")
def list_investigations(
    db: Session = Depends(get_db)
):
    investigations = db.scalars(
        select(Investigation)
        .order_by(
            Investigation.created_at.desc()
        )
        .limit(200)
    ).all()

    results = []

    for i in investigations:
        e = db.get(Event, i.event_id)

        if e:
            results.append(
                serialize_investigation(i, e)
            )

    return results


# ============================================================
# GET INDIVIDUAL INVESTIGATION REPORT
# ============================================================

@app.get("/api/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db)
):
    i = db.get(Investigation, investigation_id)

    if not i:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found"
        )

    e = db.get(Event, i.event_id)

    if not e:
        raise HTTPException(
            status_code=404,
            detail="Associated event not found"
        )

    return serialize_investigation(i, e)


# ============================================================
# UPDATE INVESTIGATION STATUS
# ============================================================

@app.patch("/api/investigations/{investigation_id}")
def update_investigation(
    investigation_id: str,
    payload: StatusInput,
    db: Session = Depends(get_db)
):
    i = db.get(Investigation, investigation_id)

    if not i:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found"
        )

    i.status = payload.status

    db.commit()

    e = db.get(Event, i.event_id)

    if not e:
        raise HTTPException(
            status_code=404,
            detail="Associated event not found"
        )

    return serialize_investigation(i, e)


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

@app.get("/api/stats")
def stats(
    db: Session = Depends(get_db)
):
    events_count = db.scalar(
        select(func.count())
        .select_from(Event)
    )

    investigations_count = db.scalar(
        select(func.count())
        .select_from(Investigation)
    )

    critical_count = db.scalar(
        select(func.count())
        .select_from(Investigation)
        .where(
            Investigation.severity == "critical"
        )
    )

    return {
        "events": events_count,
        "investigations": investigations_count,
        "critical_investigations": critical_count,
    }
