-- Canonical Postgres schema (reference SQL).
-- Production: prefer Alembic in services/interview/alembic.

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(80) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(40) NOT NULL DEFAULT 'admin',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
  id SERIAL PRIMARY KEY,
  lead_id VARCHAR(120) UNIQUE NOT NULL,
  name VARCHAR(120),
  phone VARCHAR(32) NOT NULL,
  unit VARCHAR(40) NOT NULL,
  stage VARCHAR(40) NOT NULL DEFAULT 'enquiry',
  student_type VARCHAR(40),
  course_interest VARCHAR(120),
  branch_interest VARCHAR(120),
  batch_preference VARCHAR(120),
  emi_flag BOOLEAN NOT NULL DEFAULT FALSE,
  referral_flag BOOLEAN NOT NULL DEFAULT FALSE,
  competitor_flag BOOLEAN NOT NULL DEFAULT FALSE,
  placement_interest BOOLEAN NOT NULL DEFAULT FALSE,
  lead_score INTEGER NOT NULL DEFAULT 0,
  lead_band VARCHAR(20) NOT NULL DEFAULT 'cold',
  next_action TEXT,
  assigned_counsellor VARCHAR(120),
  ai_call_summary TEXT,
  source VARCHAR(50) NOT NULL DEFAULT 'ivr_call',
  last_call_id VARCHAR(120),
  callback_due_at TIMESTAMP,
  first_response_due_at TIMESTAMP,
  sla_breached BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  -- Enquiry Form (auto-filled from AI call, editable by counsellor)
  enquiry_for_someone_else BOOLEAN DEFAULT FALSE,
  experienced_enquiry      BOOLEAN DEFAULT FALSE,
  email                    VARCHAR(180),
  class_timing             VARCHAR(60),
  time_slot                VARCHAR(60),
  highest_degree           VARCHAR(120),
  year_of_passing          VARCHAR(10),
  mode_of_class            VARCHAR(40),
  special_course           VARCHAR(120),
  other_course             VARCHAR(120),
  special_mode_of_class    VARCHAR(40),
  referral_name            VARCHAR(120),
  referral_mobile          VARCHAR(32),
  enquiry_comments         TEXT,
  form_filled_at           TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_leads_stage_updated_at ON leads(stage, updated_at);
CREATE INDEX IF NOT EXISTS ix_leads_unit_updated_at ON leads(unit, updated_at);

CREATE TABLE IF NOT EXISTS call_records (
  id SERIAL PRIMARY KEY,
  call_id VARCHAR(120) UNIQUE NOT NULL,
  lead_id_fk INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  phone VARCHAR(32) NOT NULL,
  duration_sec INTEGER NOT NULL DEFAULT 0,
  started_at VARCHAR(60),
  ended_at VARCHAR(60),
  ivr_key VARCHAR(10),
  unit_detected VARCHAR(40) NOT NULL,
  transcript TEXT,
  recording_url TEXT,
  consent_played BOOLEAN NOT NULL DEFAULT TRUE,
  raw_payload TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS timeline_events (
  id SERIAL PRIMARY KEY,
  lead_id_fk INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  event_type VARCHAR(60) NOT NULL,
  event_text TEXT NOT NULL,
  metadata TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS automation_jobs (
  id SERIAL PRIMARY KEY,
  lead_id_fk INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  call_id VARCHAR(120) NOT NULL,
  automation_type VARCHAR(60) NOT NULL,
  channel VARCHAR(30) NOT NULL,
  payload TEXT NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 4,
  next_retry_at TIMESTAMP,
  provider_status VARCHAR(40),
  dead_lettered BOOLEAN NOT NULL DEFAULT FALSE,
  provider_message_id VARCHAR(120),
  error TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_provider_msg_id UNIQUE(provider_message_id)
);

CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  lead_id_fk INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  amount_inr INTEGER NOT NULL,
  payment_mode VARCHAR(40) NOT NULL DEFAULT 'upi',
  emi_part INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  paid_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_turns (
  id SERIAL PRIMARY KEY,
  lead_id_fk INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  call_id VARCHAR(120) NOT NULL,
  turn_index INTEGER NOT NULL DEFAULT 1,
  speaker VARCHAR(20) NOT NULL,
  text TEXT NOT NULL,
  latency_ms INTEGER,
  stt_ms INTEGER,
  llm_ms INTEGER,
  tts_ms INTEGER,
  recording_url TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
