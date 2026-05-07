from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from app.db.session import SessionLocal
from app.models import AutomationJob, TimelineEvent
from app.services.automation import dispatch_provider
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.process_automation_job", max_retries=10, default_retry_delay=20)
def process_automation_job(job_id: int) -> str:
    db = SessionLocal()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return f"job {job_id} not found"

        now = datetime.utcnow()
        if job.dead_lettered:
            return "dead_lettered"
        if job.next_retry_at and job.next_retry_at > now:
            return "waiting_retry_window"

        job.status = "processing"
        job.attempts += 1
        db.commit()

        ok, provider_msg = dispatch_provider(job)
        if ok:
            job.status = "sent"
            job.provider_message_id = provider_msg
            job.provider_status = "sent"
            job.error = None
            job.next_retry_at = None
            db.add(
                TimelineEvent(
                    lead_id_fk=job.lead_id_fk,
                    event_type="automation_sent",
                    event_text=f"{job.automation_type} sent via {job.channel}.",
                    event_metadata=provider_msg,
                    created_at=datetime.utcnow(),
                )
            )
        else:
            is_last_attempt = job.attempts >= job.max_attempts
            if is_last_attempt:
                job.status = "dead_lettered"
                job.dead_lettered = True
            else:
                job.status = "retrying"
            job.provider_status = "failed"
            job.error = provider_msg
            if not is_last_attempt:
                # Exponential backoff capped at 10 minutes.
                delay_seconds = min(600, 15 * (2 ** max(0, job.attempts - 1)))
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            db.add(
                TimelineEvent(
                    lead_id_fk=job.lead_id_fk,
                    event_type="automation_failed",
                    event_text=f"{job.automation_type} failed via {job.channel}.",
                    event_metadata=provider_msg,
                    created_at=datetime.utcnow(),
                )
            )
            if not is_last_attempt:
                process_automation_job.apply_async((job.id,), countdown=delay_seconds)
        db.commit()
        return job.status
    finally:
        db.close()
