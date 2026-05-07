from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ServiceInfo(BaseModel):
    service: str
    version: str
    student_voice_ui: str
    voice_websocket: str
    crm_ui: str
    api_docs: str


class PublicIntegrationInfo(BaseModel):
    voice_websocket_url: str
    voice_demo_ui_url: str


class CallWebhookIn(BaseModel):
    call_id: str
    caller_number: str
    caller_name: str | None = None
    duration_sec: int = Field(default=0, ge=0)
    ivr_key: str | None = None
    unit: str | None = None
    transcript: str = ""
    assistant_reply: str | None = None
    recording_url: str | None = None
    user_recording_url: str | None = None
    assistant_recording_url: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    branch_interest: str | None = None
    batch_preference: str | None = None
    course_interest: str | None = None
    source: str = "ivr_call"
    consent_played: bool = True
    latency_ms: int | None = None
    stt_ms: int | None = None
    llm_ms: int | None = None
    tts_ms: int | None = None
    # Enquiry form fields — populated from AI extraction at session end
    enquiry_for_someone_else: bool | None = None
    experienced_enquiry: bool | None = None
    email: str | None = None
    class_timing: str | None = None
    time_slot: str | None = None
    highest_degree: str | None = None
    year_of_passing: str | None = None
    mode_of_class: str | None = None
    special_course: str | None = None
    other_course: str | None = None
    special_mode_of_class: str | None = None
    referral_name: str | None = None
    referral_mobile: str | None = None
    enquiry_comments: str | None = None


class LeadSummary(BaseModel):
    lead_id: str
    name: str | None = None
    phone: str
    unit: str
    stage: str
    student_type: str | None = None
    lead_score: int
    lead_band: Literal["hot", "warm", "cold"]
    emi_flag: bool
    referral_flag: bool
    assigned_counsellor: str | None = None
    next_action: str | None = None
    callback_due_at: datetime | None = None
    first_response_due_at: datetime | None = None
    sla_breached: bool = False
    updated_at: datetime


class CallWebhookOut(BaseModel):
    lead: LeadSummary
    ai_call_summary: str
    automations_triggered: list[str]


class TimelineEventOut(BaseModel):
    event_type: str
    event_text: str
    metadata: str | None
    created_at: datetime


class AutomationJobOut(BaseModel):
    id: int
    automation_type: str
    channel: str
    status: str
    provider_status: str | None
    attempts: int
    dead_lettered: bool
    next_retry_at: datetime | None
    error: str | None
    created_at: datetime


class LeadDetail(LeadSummary):
    course_interest: str | None
    branch_interest: str | None
    batch_preference: str | None
    competitor_flag: bool
    placement_interest: bool
    source: str
    last_call_id: str | None
    created_at: datetime
    ai_call_summary: str | None


class LeadWithActivity(BaseModel):
    lead: LeadDetail
    timeline: list[TimelineEventOut]
    automations: list[AutomationJobOut]


class StageUpdateIn(BaseModel):
    stage: Literal["enquiry", "demo", "counselling", "fee_payment", "enrolled", "placed", "support"]
    note: str | None = None


class CounsellingUpdateIn(BaseModel):
    note: str
    interested: bool = True
    needs_emi: bool = False


class PaymentIn(BaseModel):
    amount_inr: int = Field(gt=0)
    payment_mode: str = "upi"
    emi_part: int = Field(default=1, ge=1)
    notes: str | None = None


class PipelineSummaryOut(BaseModel):
    enquiry: int
    demo: int
    counselling: int
    fee_payment: int
    enrolled: int
    placed: int
    support: int


class RetryJobOut(BaseModel):
    job_id: int
    status: str


class ProviderCallbackIn(BaseModel):
    provider_message_id: str
    status: str
    error: str | None = None


class SLABreachOut(BaseModel):
    lead_id: str
    unit: str
    stage: str
    assigned_counsellor: str | None
    callback_due_at: datetime | None
    first_response_due_at: datetime | None


class ConversationTurnOut(BaseModel):
    call_id: str
    turn_index: int
    speaker: str
    text: str
    latency_ms: int | None
    stt_ms: int | None
    llm_ms: int | None
    tts_ms: int | None
    recording_url: str | None
    created_at: datetime


class ConversationReplayOut(BaseModel):
    lead_id: str
    turns: list[ConversationTurnOut]


class EnquiryFormIn(BaseModel):
    # Personal Information
    enquiry_for_someone_else: bool = False
    experienced_enquiry: bool = False
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    class_timing: str | None = None
    time_slot: str | None = None
    highest_degree: str | None = None
    year_of_passing: str | None = None
    # Regular Course
    course_interest: str | None = None
    branch_interest: str | None = None
    mode_of_class: str | None = None
    # Special Course
    special_course: str | None = None
    other_course: str | None = None
    special_mode_of_class: str | None = None
    # Referral
    referral_name: str | None = None
    referral_mobile: str | None = None
    enquiry_comments: str | None = None


class EnquiryFormOut(BaseModel):
    lead_id: str
    # Personal Information
    enquiry_for_someone_else: bool
    experienced_enquiry: bool
    name: str | None
    phone: str | None
    email: str | None
    class_timing: str | None
    time_slot: str | None
    highest_degree: str | None
    year_of_passing: str | None
    # Regular Course
    course_interest: str | None
    branch_interest: str | None
    mode_of_class: str | None
    # Special Course
    special_course: str | None
    other_course: str | None
    special_mode_of_class: str | None
    # Referral
    referral_name: str | None
    referral_mobile: str | None
    enquiry_comments: str | None
    form_filled_at: datetime | None
