"""initial hardened crm schema

Revision ID: 20260506_01
Revises:
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260506_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False, server_default="enquiry"),
        sa.Column("student_type", sa.String(length=40), nullable=True),
        sa.Column("course_interest", sa.String(length=120), nullable=True),
        sa.Column("branch_interest", sa.String(length=120), nullable=True),
        sa.Column("batch_preference", sa.String(length=120), nullable=True),
        sa.Column("emi_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("referral_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("competitor_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("placement_interest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lead_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lead_band", sa.String(length=20), nullable=False, server_default="cold"),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("assigned_counsellor", sa.String(length=120), nullable=True),
        sa.Column("ai_call_summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="ivr_call"),
        sa.Column("last_call_id", sa.String(length=120), nullable=True),
        sa.Column("callback_due_at", sa.DateTime(), nullable=True),
        sa.Column("first_response_due_at", sa.DateTime(), nullable=True),
        sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("lead_id"),
    )
    op.create_index("ix_leads_stage_updated_at", "leads", ["stage", "updated_at"])
    op.create_index("ix_leads_unit_updated_at", "leads", ["unit", "updated_at"])

    op.create_table(
        "call_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("call_id", sa.String(length=120), nullable=False),
        sa.Column("lead_id_fk", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.String(length=60), nullable=True),
        sa.Column("ended_at", sa.String(length=60), nullable=True),
        sa.Column("ivr_key", sa.String(length=10), nullable=True),
        sa.Column("unit_detected", sa.String(length=40), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("consent_played", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("call_id"),
    )

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id_fk", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("event_text", sa.Text(), nullable=False),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "automation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id_fk", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", sa.String(length=120), nullable=False),
        sa.Column("automation_type", sa.String(length=60), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("provider_status", sa.String(length=40), nullable=True),
        sa.Column("dead_lettered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint("uq_provider_msg_id", "automation_jobs", ["provider_message_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id_fk", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("payment_mode", sa.String(length=40), nullable=False, server_default="upi"),
        sa.Column("emi_part", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id_fk", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", sa.String(length=120), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("speaker", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("stt_ms", sa.Integer(), nullable=True),
        sa.Column("llm_ms", sa.Integer(), nullable=True),
        sa.Column("tts_ms", sa.Integer(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("conversation_turns")
    op.drop_table("payments")
    op.drop_table("automation_jobs")
    op.drop_table("timeline_events")
    op.drop_table("call_records")
    op.drop_index("ix_leads_unit_updated_at", table_name="leads")
    op.drop_index("ix_leads_stage_updated_at", table_name="leads")
    op.drop_table("leads")
    op.drop_table("users")
