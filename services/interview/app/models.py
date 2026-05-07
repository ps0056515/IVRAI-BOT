from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_stage_updated_at", "stage", "updated_at"),
        Index("ix_leads_unit_updated_at", "unit", "updated_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    unit: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str] = mapped_column(String(40), default="enquiry", index=True)
    student_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    course_interest: Mapped[str | None] = mapped_column(String(120), nullable=True)
    branch_interest: Mapped[str | None] = mapped_column(String(120), nullable=True)
    batch_preference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emi_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    referral_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    competitor_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    placement_interest: Mapped[bool] = mapped_column(Boolean, default=False)
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    lead_band: Mapped[str] = mapped_column(String(20), default="cold", index=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_counsellor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_call_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="ivr_call")
    last_call_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    callback_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Enquiry Form (auto-filled from AI call, editable by counsellor) ──────
    enquiry_for_someone_else: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    experienced_enquiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    class_timing: Mapped[str | None] = mapped_column(String(60), nullable=True)
    time_slot: Mapped[str | None] = mapped_column(String(60), nullable=True)
    highest_degree: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year_of_passing: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mode_of_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    special_course: Mapped[str | None] = mapped_column(String(120), nullable=True)
    other_course: Mapped[str | None] = mapped_column(String(120), nullable=True)
    special_mode_of_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    referral_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    referral_mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enquiry_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    calls: Mapped[list["CallRecord"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    automation_jobs: Mapped[list["AutomationJob"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    conversation_turns: Mapped[list["ConversationTurn"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class CallRecord(Base):
    __tablename__ = "call_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    lead_id_fk: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ended_at: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ivr_key: Mapped[str | None] = mapped_column(String(10), nullable=True)
    unit_detected: Mapped[str] = mapped_column(String(40))
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_played: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="calls")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id_fk: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    event_text: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="timeline_events")


class AutomationJob(Base):
    __tablename__ = "automation_jobs"
    __table_args__ = (UniqueConstraint("provider_message_id", name="uq_provider_msg_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id_fk: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(String(120), index=True)
    automation_type: Mapped[str] = mapped_column(String(60))
    channel: Mapped[str] = mapped_column(String(30))
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    provider_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dead_lettered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="automation_jobs")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id_fk: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    amount_inr: Mapped[int] = mapped_column(Integer)
    payment_mode: Mapped[str] = mapped_column(String(40), default="upi")
    emi_part: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="payments")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id_fk: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[str] = mapped_column(String(120), index=True)
    turn_index: Mapped[int] = mapped_column(Integer, default=1)
    speaker: Mapped[str] = mapped_column(String(20))  # user | assistant
    text: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stt_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="conversation_turns")
