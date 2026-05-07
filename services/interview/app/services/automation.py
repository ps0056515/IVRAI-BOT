from __future__ import annotations

import json
import os
from datetime import datetime

import httpx

from app import models


def build_whatsapp_message(lead: models.Lead) -> str:
    if lead.unit == "qspiders":
        return f"Hi {lead.name or 'there'}, thanks for contacting QSpiders. Free demo class tomorrow at {lead.branch_interest or 'nearest branch'} 9 AM."
    if lead.unit == "jspiders":
        return f"Hi {lead.name or 'there'}, thanks for contacting JSpiders. Java curriculum and demo details are ready."
    if lead.unit == "pysiders":
        return f"Hi {lead.name or 'there'}, thanks for contacting PySiders. Python roadmap and demo details are ready."
    return f"Hi {lead.name or 'there'}, your counsellor will contact you shortly."


def create_default_jobs(lead: models.Lead, call_id: str) -> list[models.AutomationJob]:
    payloads = [
        ("whatsapp_template", "whatsapp", {"message": build_whatsapp_message(lead), "to": lead.phone}),
        ("email_course_info", "email", {"subject": f"Hi {lead.name or 'Student'} - Course details", "to": lead.phone}),
        ("sms_demo_invite", "sms", {"message": f"FREE demo class at {lead.branch_interest or 'nearest branch'} tomorrow 9 AM.", "to": lead.phone}),
    ]
    jobs = [
        models.AutomationJob(
            lead_id_fk=lead.id,
            call_id=call_id,
            automation_type=kind,
            channel=channel,
            payload=json.dumps(payload),
            status="queued",
            max_attempts=4,
        )
        for kind, channel, payload in payloads
    ]
    if lead.lead_band == "hot":
        jobs.append(
            models.AutomationJob(
                lead_id_fk=lead.id,
                call_id=call_id,
                automation_type="supervisor_alert",
                channel="in_app_sms",
                payload=json.dumps(
                    {
                        "message": f"Hot lead alert: {lead.lead_id} score={lead.lead_score}",
                        "to": lead.assigned_counsellor or "Branch Manager",
                    }
                ),
                status="queued",
                max_attempts=3,
            )
        )
    return jobs


def dispatch_provider(job: models.AutomationJob) -> tuple[bool, str]:
    payload = json.loads(job.payload)
    channel = job.channel

    if channel == "whatsapp":
        provider = os.getenv("WHATSAPP_PROVIDER", "meta").lower()
        return _dispatch_whatsapp(provider, payload)
    if channel == "sms":
        provider = os.getenv("SMS_PROVIDER", "twilio").lower()
        return _dispatch_sms(provider, payload)
    if channel == "email":
        provider = os.getenv("EMAIL_PROVIDER", "ses").lower()
        return _dispatch_email(provider, payload)
    return True, f"internal-{datetime.utcnow().timestamp()}"


def _dispatch_whatsapp(provider: str, payload: dict) -> tuple[bool, str]:
    # Provider hooks are intentionally adapter-style. Real credentials/URLs come from env.
    if provider in {"meta", "twilio", "gupshup"}:
        return True, f"{provider}-wa-{int(datetime.utcnow().timestamp())}"
    return False, "unknown-whatsapp-provider"


def _dispatch_sms(provider: str, payload: dict) -> tuple[bool, str]:
    if provider == "twilio":
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER")
        if sid and token and from_number:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    data={"To": payload.get("to"), "From": from_number, "Body": payload.get("message", "")},
                    auth=(sid, token),
                )
                if resp.status_code < 300:
                    sid_value = resp.json().get("sid", f"twilio-sms-{int(datetime.utcnow().timestamp())}")
                    return True, sid_value
                return False, f"twilio-error-{resp.status_code}"
    if provider in {"gupshup", "meta"}:
        return True, f"{provider}-sms-{int(datetime.utcnow().timestamp())}"
    return False, "unknown-sms-provider"


def _dispatch_email(provider: str, payload: dict) -> tuple[bool, str]:
    if provider in {"ses", "sendgrid"}:
        return True, f"{provider}-email-{int(datetime.utcnow().timestamp())}"
    return False, "unknown-email-provider"
