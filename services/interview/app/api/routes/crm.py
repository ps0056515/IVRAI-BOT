from __future__ import annotations

from datetime import datetime, timedelta
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from urllib.parse import unquote

from app import models
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.schemas import (
    CallWebhookIn,
    CallWebhookOut,
    AutomationJobOut,
    CounsellingUpdateIn,
    LeadDetail,
    LeadSummary,
    LeadWithActivity,
    PaymentIn,
    PipelineSummaryOut,
    StageUpdateIn,
    ConversationReplayOut,
    ConversationTurnOut,
    ProviderCallbackIn,
    RetryJobOut,
    SLABreachOut,
    EnquiryFormIn,
    EnquiryFormOut,
)
from app.services.automation import create_default_jobs
from app.services.enrichment import (
    assign_counsellor,
    detect_course,
    detect_student_type,
    detect_unit,
    next_action,
    score_and_flags,
    summary,
)
from app.worker.tasks import process_automation_job


router = APIRouter(tags=["crm"])


def _lead_summary(lead: models.Lead) -> LeadSummary:
    return LeadSummary(
        lead_id=lead.lead_id,
        name=lead.name,
        phone=lead.phone,
        unit=lead.unit,
        stage=lead.stage,
        student_type=lead.student_type,
        lead_score=lead.lead_score,
        lead_band=lead.lead_band,  # type: ignore[arg-type]
        emi_flag=lead.emi_flag,
        referral_flag=lead.referral_flag,
        assigned_counsellor=lead.assigned_counsellor,
        next_action=lead.next_action,
        callback_due_at=lead.callback_due_at,
        first_response_due_at=lead.first_response_due_at,
        sla_breached=lead.sla_breached,
        updated_at=lead.updated_at,
    )


def _save_timeline(db: Session, lead_fk: int, event_type: str, event_text: str, metadata: str | None = None) -> None:
    db.add(
        models.TimelineEvent(
            lead_id_fk=lead_fk,
            event_type=event_type,
            event_text=event_text,
            event_metadata=metadata,
            created_at=datetime.utcnow(),
        )
    )


def _compute_sla(lead_band: str) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    if lead_band == "hot":
        return now + timedelta(minutes=30), now + timedelta(minutes=1)
    if lead_band == "warm":
        return now + timedelta(hours=2), now + timedelta(minutes=2)
    return now + timedelta(hours=24), now + timedelta(minutes=5)


@router.post("/v1/calls/webhook", response_model=CallWebhookOut, summary="Ingest call-end webhook and create/update CRM lead")
def ingest_call_webhook(
    payload: CallWebhookIn,
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
) -> CallWebhookOut:
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    existing_call = db.query(models.CallRecord).filter(models.CallRecord.call_id == payload.call_id).first()
    if existing_call:
        lead = db.query(models.Lead).filter(models.Lead.id == existing_call.lead_id_fk).first()
        if not lead:
            raise HTTPException(status_code=409, detail="Duplicate call id with missing lead.")
        return CallWebhookOut(
            lead=_lead_summary(lead),
            ai_call_summary=lead.ai_call_summary or "Already processed.",
            automations_triggered=[],
        )

    is_session_end = payload.source == "voice_ws_end"
    unit = (payload.unit or "").lower().strip() or detect_unit(payload.transcript, payload.ivr_key)
    # For session-end webhooks, prefer AI-extracted course; fallback to regex
    course = payload.course_interest or detect_course(payload.transcript)
    student_type = "experienced" if payload.experienced_enquiry else detect_student_type(payload.transcript)
    flags, score, band = score_and_flags(payload.transcript, payload.duration_sec, payload.ended_at)
    counsellor = assign_counsellor(unit, payload.branch_interest or payload.branch_interest)
    action = next_action(band, flags["emi_flag"], flags["demo_interest"])
    ai_summary = summary(student_type, unit, course, flags, score, band)

    lead = (
        db.query(models.Lead)
        .filter(models.Lead.phone == payload.caller_number, models.Lead.unit == unit)
        .order_by(models.Lead.updated_at.desc())
        .first()
    )
    if not lead:
        lead = models.Lead(
            lead_id=f"{unit.upper()}-{payload.caller_number[-6:]}-{payload.call_id[-6:]}",
            name=payload.caller_name,
            phone=payload.caller_number,
            unit=unit,
            stage="support" if unit in {"support", "placement"} else "enquiry",
            source=payload.source,
            created_at=datetime.utcnow(),
        )
        db.add(lead)
        db.flush()

    # For session-end: AI-extracted name wins over websocket default "Voice UI User"
    incoming_name = payload.caller_name
    if incoming_name and incoming_name not in ("Voice UI User", "websocket-user", ""):
        lead.name = incoming_name
    elif not lead.name:
        lead.name = incoming_name
    lead.student_type = student_type
    lead.course_interest = course or lead.course_interest
    lead.branch_interest = payload.branch_interest or lead.branch_interest
    lead.batch_preference = payload.batch_preference or lead.batch_preference
    lead.emi_flag = flags["emi_flag"]
    lead.referral_flag = flags["referral_flag"]
    lead.competitor_flag = flags["competitor_flag"]
    lead.placement_interest = flags["placement_interest"]
    lead.lead_score = score
    lead.lead_band = band
    lead.next_action = action
    lead.assigned_counsellor = counsellor
    lead.ai_call_summary = ai_summary
    lead.last_call_id = payload.call_id
    callback_due_at, first_response_due_at = _compute_sla(band)
    lead.callback_due_at = callback_due_at
    lead.first_response_due_at = first_response_due_at
    lead.sla_breached = False
    lead.updated_at = datetime.utcnow()

    call = models.CallRecord(
        call_id=payload.call_id,
        lead_id_fk=lead.id,
        phone=payload.caller_number,
        duration_sec=payload.duration_sec,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        ivr_key=payload.ivr_key,
        unit_detected=unit,
        transcript=payload.transcript,
        recording_url=payload.assistant_recording_url or payload.user_recording_url or payload.recording_url,
        consent_played=payload.consent_played,
        raw_payload=payload.model_dump_json(),
    )
    db.add(call)
    _save_timeline(db, lead.id, "call_ended", f"Call {payload.call_id} processed. Score {score} ({band}).")

    turn_idx = 1
    suffix = payload.call_id.rsplit("-", 1)[-1]
    if suffix.isdigit():
        turn_idx = int(suffix)
    if payload.transcript:
        db.add(
            models.ConversationTurn(
                lead_id_fk=lead.id,
                call_id=payload.call_id,
                turn_index=turn_idx,
                speaker="user",
                text=payload.transcript,
                latency_ms=payload.latency_ms,
                stt_ms=payload.stt_ms,
                llm_ms=payload.llm_ms,
                tts_ms=payload.tts_ms,
                recording_url=payload.user_recording_url or payload.recording_url,
            )
        )
    if payload.assistant_reply:
        db.add(
            models.ConversationTurn(
                lead_id_fk=lead.id,
                call_id=payload.call_id,
                turn_index=turn_idx,
                speaker="assistant",
                text=payload.assistant_reply,
                latency_ms=payload.latency_ms,
                stt_ms=payload.stt_ms,
                llm_ms=payload.llm_ms,
                tts_ms=payload.tts_ms,
                recording_url=payload.assistant_recording_url or payload.recording_url,
            )
        )

    # ── For session-end: update lead phone/email from form if extracted ──────
    if is_session_end:
        if payload.email:
            lead.email = payload.email
        # If extracted phone is real (not a websocket placeholder), update lead phone
        extracted_phone = payload.caller_number
        if extracted_phone and not extracted_phone.startswith("websocket-"):
            lead.phone = extracted_phone

    # ── Auto-fill enquiry form from voice-extracted fields ──────────────────
    _form_fields = {
        "enquiry_for_someone_else": payload.enquiry_for_someone_else,
        "experienced_enquiry": payload.experienced_enquiry,
        "email": payload.email,
        "class_timing": payload.class_timing,
        "time_slot": payload.time_slot,
        "highest_degree": payload.highest_degree,
        "year_of_passing": payload.year_of_passing,
        "mode_of_class": payload.mode_of_class,
        "special_course": payload.special_course,
        "other_course": payload.other_course,
        "special_mode_of_class": payload.special_mode_of_class,
        "referral_name": payload.referral_name,
        "referral_mobile": payload.referral_mobile,
        "enquiry_comments": payload.enquiry_comments,
    }
    _has_form_data = any(v is not None for v in _form_fields.values())
    if _has_form_data:
        for field, value in _form_fields.items():
            if value is not None:
                setattr(lead, field, value)
        lead.form_filled_at = datetime.utcnow()
        _save_timeline(db, lead.id, "enquiry_form_auto_filled",
                       "Enquiry form auto-filled by AI voice extraction.")

    jobs = create_default_jobs(lead, payload.call_id)
    for job in jobs:
        db.add(job)
    db.flush()
    queue_ok = True
    for job in jobs:
        try:
            process_automation_job.delay(job.id)
        except Exception as exc:
            queue_ok = False
            job.status = "queued_local"
            job.error = str(exc)
    _save_timeline(db, lead.id, "automation_queued", f"{len(jobs)} automation jobs queued.")
    if not queue_ok:
        _save_timeline(
            db,
            lead.id,
            "queue_degraded",
            "Redis/Celery unavailable; jobs stored for manual retry.",
        )
    db.commit()
    db.refresh(lead)

    return CallWebhookOut(
        lead=_lead_summary(lead),
        ai_call_summary=ai_summary,
        automations_triggered=[j.automation_type for j in jobs],
    )


@router.get("/v1/leads", response_model=list[LeadSummary], summary="List leads")
def list_leads(
    unit: str | None = None,
    stage: str | None = None,
    counsellor: str | None = None,
    lead_band: str | None = Query(default=None, pattern="^(hot|warm|cold)$"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> list[LeadSummary]:
    q = db.query(models.Lead)
    if unit:
        q = q.filter(models.Lead.unit == unit.lower())
    if stage:
        q = q.filter(models.Lead.stage == stage.lower())
    if lead_band:
        q = q.filter(models.Lead.lead_band == lead_band.lower())
    if counsellor:
        q = q.filter(models.Lead.assigned_counsellor.ilike(f"%{counsellor}%"))
    leads = q.order_by(models.Lead.updated_at.desc()).limit(limit).all()
    return [_lead_summary(l) for l in leads]


@router.get("/v1/leads/{lead_id}", response_model=LeadWithActivity, summary="Lead detail with timeline")
def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> LeadWithActivity:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    timeline = (
        db.query(models.TimelineEvent)
        .filter(models.TimelineEvent.lead_id_fk == lead.id)
        .order_by(models.TimelineEvent.id.desc())
        .limit(100)
        .all()
    )
    jobs = (
        db.query(models.AutomationJob)
        .filter(models.AutomationJob.lead_id_fk == lead.id)
        .order_by(models.AutomationJob.id.desc())
        .limit(100)
        .all()
    )
    detail = LeadDetail(
        **_lead_summary(lead).model_dump(),
        course_interest=lead.course_interest,
        branch_interest=lead.branch_interest,
        batch_preference=lead.batch_preference,
        competitor_flag=lead.competitor_flag,
        placement_interest=lead.placement_interest,
        source=lead.source,
        last_call_id=lead.last_call_id,
        created_at=lead.created_at,
        ai_call_summary=lead.ai_call_summary,
    )
    return LeadWithActivity(
        lead=detail,
        timeline=[
            {
                "event_type": t.event_type,
                "event_text": t.event_text,
                "metadata": t.event_metadata,
                "created_at": t.created_at,
            }
            for t in timeline
        ],
        automations=[
            {
                "id": j.id,
                "automation_type": j.automation_type,
                "channel": j.channel,
                "status": j.status,
                "provider_status": j.provider_status,
                "attempts": j.attempts,
                "dead_lettered": j.dead_lettered,
                "next_retry_at": j.next_retry_at,
                "error": j.error,
                "created_at": j.created_at,
            }
            for j in jobs
        ],
    )


@router.post("/v1/leads/{lead_id}/stage", response_model=LeadSummary, summary="Update lead stage")
def update_stage(
    lead_id: str,
    payload: StageUpdateIn,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> LeadSummary:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    lead.stage = payload.stage
    if payload.stage in {"fee_payment", "enrolled", "placed", "support"}:
        lead.sla_breached = False
    elif payload.stage in {"enquiry", "demo", "counselling"}:
        callback_due_at, first_response_due_at = _compute_sla(lead.lead_band)
        lead.callback_due_at = callback_due_at
        lead.first_response_due_at = first_response_due_at
    lead.updated_at = datetime.utcnow()
    _save_timeline(db, lead.id, "stage_updated", payload.note or f"Moved to {payload.stage}.")
    db.commit()
    db.refresh(lead)
    return _lead_summary(lead)


@router.post("/v1/leads/{lead_id}/counselling", response_model=LeadSummary, summary="Update counselling outcome")
def update_counselling(
    lead_id: str,
    payload: CounsellingUpdateIn,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> LeadSummary:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    lead.stage = "counselling"
    lead.emi_flag = payload.needs_emi or lead.emi_flag
    callback_due_at, first_response_due_at = _compute_sla(lead.lead_band)
    lead.callback_due_at = callback_due_at
    lead.first_response_due_at = first_response_due_at
    lead.updated_at = datetime.utcnow()
    _save_timeline(db, lead.id, "counselling", payload.note)
    db.commit()
    db.refresh(lead)
    return _lead_summary(lead)


@router.post("/v1/leads/{lead_id}/payments", response_model=LeadSummary, summary="Record payment for admissions")
def record_payment(
    lead_id: str,
    payload: PaymentIn,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> LeadSummary:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    db.add(
        models.Payment(
            lead_id_fk=lead.id,
            amount_inr=payload.amount_inr,
            payment_mode=payload.payment_mode,
            emi_part=payload.emi_part,
            notes=payload.notes,
        )
    )
    lead.stage = "fee_payment"
    lead.sla_breached = False
    lead.updated_at = datetime.utcnow()
    _save_timeline(db, lead.id, "payment", f"Payment received: Rs.{payload.amount_inr} via {payload.payment_mode}.")
    db.commit()
    db.refresh(lead)
    return _lead_summary(lead)


@router.get("/v1/analytics/admissions-pipeline", response_model=PipelineSummaryOut, summary="Admissions pipeline counts")
def admissions_pipeline(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> PipelineSummaryOut:
    rows = dict(
        db.query(models.Lead.stage, func.count(models.Lead.id))
        .group_by(models.Lead.stage)
        .all()
    )
    return PipelineSummaryOut(
        enquiry=int(rows.get("enquiry", 0)),
        demo=int(rows.get("demo", 0)),
        counselling=int(rows.get("counselling", 0)),
        fee_payment=int(rows.get("fee_payment", 0)),
        enrolled=int(rows.get("enrolled", 0)),
        placed=int(rows.get("placed", 0)),
        support=int(rows.get("support", 0)),
    )


@router.get("/v1/leads/{lead_id}/conversation", response_model=ConversationReplayOut, summary="Conversation replay for QA")
def get_conversation_replay(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> ConversationReplayOut:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    turns = (
        db.query(models.ConversationTurn)
        .filter(models.ConversationTurn.lead_id_fk == lead.id)
        .order_by(models.ConversationTurn.turn_index.asc(), models.ConversationTurn.id.asc())
        .all()
    )
    return ConversationReplayOut(
        lead_id=lead_id,
        turns=[
            ConversationTurnOut(
                call_id=t.call_id,
                turn_index=t.turn_index,
                speaker=t.speaker,
                text=t.text,
                latency_ms=t.latency_ms,
                stt_ms=t.stt_ms,
                llm_ms=t.llm_ms,
                tts_ms=t.tts_ms,
                recording_url=t.recording_url,
                created_at=t.created_at,
            )
            for t in turns
        ],
    )


@router.get("/v1/calls/{call_id}/recording", summary="Download call turn recording for QA")
def get_call_recording(
    call_id: str,
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_roles(*settings.recording_roles)),
):
    rec = db.query(models.CallRecord).filter(models.CallRecord.call_id == call_id).first()
    if not rec or not rec.recording_url:
        raise HTTPException(status_code=404, detail="Recording not found.")
    local_path = unquote(rec.recording_url.replace("file:///", ""))
    if not os.path.isfile(local_path):
        raise HTTPException(status_code=404, detail="Recording file missing.")
    return FileResponse(local_path, media_type="audio/mpeg", filename=f"{call_id}.mp3")


@router.get("/v1/automation/jobs", response_model=list[AutomationJobOut], summary="List automation jobs")
def list_automation_jobs(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> list[AutomationJobOut]:
    q = db.query(models.AutomationJob)
    if status:
        q = q.filter(models.AutomationJob.status == status)
    jobs = q.order_by(models.AutomationJob.created_at.desc()).limit(limit).all()
    return [
        AutomationJobOut(
            id=j.id,
            automation_type=j.automation_type,
            channel=j.channel,
            status=j.status,
            provider_status=j.provider_status,
            attempts=j.attempts,
            dead_lettered=j.dead_lettered,
            next_retry_at=j.next_retry_at,
            error=j.error,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.post("/v1/automation/jobs/{job_id}/retry", response_model=RetryJobOut, summary="Retry one automation job")
def retry_automation_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> RetryJobOut:
    job = db.query(models.AutomationJob).filter(models.AutomationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.dead_lettered = False
    job.status = "queued"
    job.error = None
    job.next_retry_at = datetime.utcnow()
    db.commit()
    try:
        process_automation_job.delay(job.id)
    except Exception as exc:
        job.status = "queued_local"
        job.error = str(exc)
        db.commit()
    return RetryJobOut(job_id=job.id, status=job.status)


@router.post("/v1/providers/callback", summary="Provider delivery callback")
def provider_callback(
    payload: ProviderCallbackIn,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    job = (
        db.query(models.AutomationJob)
        .filter(models.AutomationJob.provider_message_id == payload.provider_message_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Unknown provider message id.")
    normalized = payload.status.lower()
    job.provider_status = normalized
    if normalized in {"delivered", "sent", "read"}:
        job.status = "sent"
        job.error = None
    elif normalized in {"failed", "undelivered", "rejected"}:
        job.status = "failed"
        job.error = payload.error or "provider callback failure"
    db.add(
        models.TimelineEvent(
            lead_id_fk=job.lead_id_fk,
            event_type="provider_callback",
            event_text=f"{job.channel} callback status={normalized}",
            event_metadata=payload.error,
        )
    )
    db.commit()
    return {"status": "ok"}


@router.get("/v1/sla/breaches", response_model=list[SLABreachOut], summary="List leads breaching SLA")
def list_sla_breaches(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> list[SLABreachOut]:
    now = datetime.utcnow()
    breached = (
        db.query(models.Lead)
        .filter(
            models.Lead.stage.in_(["enquiry", "demo", "counselling"]),
            models.Lead.callback_due_at.is_not(None),
            models.Lead.callback_due_at < now,
        )
        .order_by(models.Lead.callback_due_at.asc())
        .all()
    )
    for lead in breached:
        lead.sla_breached = True
    db.commit()
    return [
        SLABreachOut(
            lead_id=l.lead_id,
            unit=l.unit,
            stage=l.stage,
            assigned_counsellor=l.assigned_counsellor,
            callback_due_at=l.callback_due_at,
            first_response_due_at=l.first_response_due_at,
        )
        for l in breached
    ]


@router.get("/v1/ops/metrics", summary="Operational metrics snapshot")
def ops_metrics(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> dict[str, int]:
    return {
        "leads_total": db.query(func.count(models.Lead.id)).scalar() or 0,
        "calls_total": db.query(func.count(models.CallRecord.id)).scalar() or 0,
        "jobs_total": db.query(func.count(models.AutomationJob.id)).scalar() or 0,
        "jobs_failed": db.query(func.count(models.AutomationJob.id)).filter(models.AutomationJob.status == "failed").scalar() or 0,
        "jobs_dead_lettered": db.query(func.count(models.AutomationJob.id)).filter(models.AutomationJob.dead_lettered.is_(True)).scalar() or 0,
        "sla_breached": db.query(func.count(models.Lead.id)).filter(models.Lead.sla_breached.is_(True)).scalar() or 0,
    }


@router.get("/v1/leads/{lead_id}/enquiry-form", response_model=EnquiryFormOut, summary="Get post-call enquiry form for a lead")
def get_enquiry_form(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> EnquiryFormOut:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return EnquiryFormOut(
        lead_id=lead_id,
        enquiry_for_someone_else=lead.enquiry_for_someone_else or False,
        experienced_enquiry=lead.experienced_enquiry or False,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        class_timing=lead.class_timing,
        time_slot=lead.time_slot,
        highest_degree=lead.highest_degree,
        year_of_passing=lead.year_of_passing,
        course_interest=lead.course_interest,
        branch_interest=lead.branch_interest,
        mode_of_class=lead.mode_of_class,
        special_course=lead.special_course,
        other_course=lead.other_course,
        special_mode_of_class=lead.special_mode_of_class,
        referral_name=lead.referral_name,
        referral_mobile=lead.referral_mobile,
        enquiry_comments=lead.enquiry_comments,
        form_filled_at=lead.form_filled_at,
    )


@router.post("/v1/leads/{lead_id}/enquiry-form", response_model=EnquiryFormOut, summary="Save post-call enquiry form for a lead")
def save_enquiry_form(
    lead_id: str,
    payload: EnquiryFormIn,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
) -> EnquiryFormOut:
    lead = db.query(models.Lead).filter(models.Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    # Update only provided (non-None) fields; always update booleans
    lead.enquiry_for_someone_else = payload.enquiry_for_someone_else
    lead.experienced_enquiry = payload.experienced_enquiry
    if payload.name is not None:
        lead.name = payload.name
    if payload.phone is not None:
        lead.phone = payload.phone
    if payload.email is not None:
        lead.email = payload.email
    if payload.class_timing is not None:
        lead.class_timing = payload.class_timing
    if payload.time_slot is not None:
        lead.time_slot = payload.time_slot
    if payload.highest_degree is not None:
        lead.highest_degree = payload.highest_degree
    if payload.year_of_passing is not None:
        lead.year_of_passing = payload.year_of_passing
    if payload.course_interest is not None:
        lead.course_interest = payload.course_interest
    if payload.branch_interest is not None:
        lead.branch_interest = payload.branch_interest
    if payload.mode_of_class is not None:
        lead.mode_of_class = payload.mode_of_class
    if payload.special_course is not None:
        lead.special_course = payload.special_course
    if payload.other_course is not None:
        lead.other_course = payload.other_course
    if payload.special_mode_of_class is not None:
        lead.special_mode_of_class = payload.special_mode_of_class
    if payload.referral_name is not None:
        lead.referral_name = payload.referral_name
    if payload.referral_mobile is not None:
        lead.referral_mobile = payload.referral_mobile
    if payload.enquiry_comments is not None:
        lead.enquiry_comments = payload.enquiry_comments
    lead.form_filled_at = datetime.utcnow()
    lead.updated_at = datetime.utcnow()
    _save_timeline(db, lead.id, "enquiry_form_saved", "Enquiry form saved/updated by counsellor.")
    db.commit()
    db.refresh(lead)
    return EnquiryFormOut(
        lead_id=lead_id,
        enquiry_for_someone_else=lead.enquiry_for_someone_else or False,
        experienced_enquiry=lead.experienced_enquiry or False,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        class_timing=lead.class_timing,
        time_slot=lead.time_slot,
        highest_degree=lead.highest_degree,
        year_of_passing=lead.year_of_passing,
        course_interest=lead.course_interest,
        branch_interest=lead.branch_interest,
        mode_of_class=lead.mode_of_class,
        special_course=lead.special_course,
        other_course=lead.other_course,
        special_mode_of_class=lead.special_mode_of_class,
        referral_name=lead.referral_name,
        referral_mobile=lead.referral_mobile,
        enquiry_comments=lead.enquiry_comments,
        form_filled_at=lead.form_filled_at,
    )


@router.post("/v1/ops/retention-run", summary="Apply retention cleanup for old conversation artifacts")
def retention_run(
    days: int = Query(default=90, ge=7, le=3650),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_roles("admin", "qa")),
) -> dict[str, int]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    old_turns = db.query(models.ConversationTurn).filter(models.ConversationTurn.created_at < cutoff).all()
    removed_files = 0
    for t in old_turns:
        if t.recording_url and t.recording_url.startswith("file:///"):
            local_path = unquote(t.recording_url.replace("file:///", ""))
            if os.path.isfile(local_path):
                try:
                    os.remove(local_path)
                    removed_files += 1
                except OSError:
                    pass
        t.recording_url = None
    db.commit()
    return {"conversation_turns_touched": len(old_turns), "recording_files_removed": removed_files}
