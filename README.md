# VoiceBot

Monorepo with two deployable services: a **voice** media pipeline and an **interview** control API for IVR + CRM orchestration.

**Voice (real time):** Whisper (STT) → Claude Haiku (LLM) → gTTS (TTS)

```
Browser mic → raw PCM → WebSocket → Whisper → Claude → gTTS → MP3 → browser
```

## Layout

| Path | Role |
|------|------|
| `services/voice/` | WebSocket STT/LLM/TTS + static demo UI in `static/` |
| `services/interview/` | FastAPI CRM API, auth, admissions pipeline, Postgres models, and Celery worker tasks |
| `packages/contracts/` | Shared contracts: [voice WebSocket](packages/contracts/voice-websocket.md), [interview OpenAPI](packages/contracts/openapi/interview-api.yaml) |
| `server.py`, `static_server.py` (repo root) | Shims; forward to `services/voice` so `python server.py` still works |

## Quick start (local, full stack)

```bash
cd voicebot
cp .env.example .env
# set ANTHROPIC_API_KEY in .env
chmod +x start.sh
./start.sh
```

- **Voice demo UI:** http://localhost:8080  
- **WebSocket:** ws://localhost:8765  
- **Interview API:** http://localhost:8000 (docs: http://localhost:8000/docs)
- **CRM Webapp:** http://localhost:8000/crm

Voice-only: `bash services/voice/start.sh` (from repo root; loads root `.env`).

### Windows (PowerShell)

```powershell
cd voicebot
.\scripts\start_dev.ps1
```

## Docker

Builds and runs full stack: voice + interview API + Postgres + Redis + worker.
Voice static UI is on host port **8081** (avoids clashing with other tools using 8080).

```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build
```

- **Voice UI:** http://localhost:8081  
- **WebSocket:** ws://localhost:8765  
- **Interview API:** http://localhost:8000  
- **CRM Webapp:** http://localhost:8000/crm

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | required (voice) | Anthropic key |
| `PORT` | `8765` | WebSocket (voice) |
| `STATIC_PORT` | `8080` | Static demo (voice) |
| `INTERVIEW_PORT` | `8000` | REST API (interview) |
| `DATABASE_URL` | `postgresql+psycopg://crm_user:crm_pass@localhost:5432/crm_db` | Postgres connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Queue broker/backend |
| `WEBHOOK_SECRET` | `change-this-webhook-secret` | Secret required by `/v1/calls/webhook` |
| `JWT_SECRET` | `change-this-jwt-secret` | JWT signing key |
| `CRM_ADMIN_USERNAME` / `CRM_ADMIN_PASSWORD` | `admin` / `admin123` | Seeded admin account |
| `ENFORCE_MIGRATIONS` | `false` | If `true`, startup requires migrated schema (no auto bootstrap) |
| `RECORDING_ACCESS_ROLES` | `admin,manager,qa` | Roles allowed to fetch recordings |
| `INTERVIEW_CORS_ORIGINS` | `localhost:8080,...` | CORS for interview API |
| `VOICE_WS_PUBLIC_URL` / `VOICE_HTTP_PUBLIC_URL` | see interview `/v1/integrations` | Hints for clients |

Whisper: `WHISPER_MODEL`, `WHISPER_DEVICE` — see [`.env.example`](.env.example). Use **separate comment lines** for values (inline `#` comments in `.env` are unsafe on some loaders).

## CRM API quick flow (Admissions)

The `interview` service now includes a practical CRM ingestion flow:

- `POST /v1/auth/login` → get bearer token for CRM APIs/webapp actions
- `POST /v1/calls/webhook` (requires `x-webhook-secret`) → ingest call, enrich lead, queue automations
- `GET /v1/leads` → list leads with filters (`unit`, `stage`, `lead_band`)
- `GET /v1/leads/{leadId}` → lead detail + timeline + automation job states
- `POST /v1/leads/{leadId}/stage` → move lead through enquiry/demo/counselling/fee stages
- `POST /v1/leads/{leadId}/counselling` → counselling notes and EMI update
- `POST /v1/leads/{leadId}/payments` → fee payment event
- `GET /v1/analytics/admissions-pipeline` → stage-wise pipeline counts
- `GET /v1/leads/{leadId}/conversation` → full conversation replay turns for QA
- `GET /v1/calls/{callId}/recording` → download recorded turn audio for QA
- `GET /v1/automation/jobs` / `POST /v1/automation/jobs/{jobId}/retry` → inspect and retry failed/dead-lettered jobs
- `GET /v1/sla/breaches` → detect callback SLA breaches
- `POST /v1/providers/callback` → ingest delivery callbacks from messaging providers
- `GET /v1/ops/metrics` / `POST /v1/ops/retention-run` → operational metrics + retention cleanup

Example webhook:

```bash
curl -X POST http://localhost:8000/v1/calls/webhook \
  -H "Content-Type: application/json" \
  -H "x-webhook-secret: change-this-webhook-secret" \
  -d '{
    "call_id": "fs-2026-0001",
    "caller_number": "+919840012345",
    "caller_name": "Rahul Kumar",
    "duration_sec": 272,
    "ivr_key": "1",
    "transcript": "Hi I am fresher 2024 passout. I need selenium testing course and EMI option. My friend joined and got placed in TCS.",
    "branch_interest": "BTM Layout",
    "batch_preference": "Weekday morning",
    "ended_at": "2026-05-06T06:20:00Z"
  }'
```

Webhook payload can now optionally include:
- `assistant_reply` (assistant text per turn)
- `recording_url` (audio file URL/path)
- `latency_ms`, `stt_ms`, `llm_ms`, `tts_ms` (quality and performance metrics)

## Worker and providers

- Celery worker queue: `crm_automations`
- Channels implemented: WhatsApp, SMS, Email, Supervisor alert
- Provider selection via env:
  - `WHATSAPP_PROVIDER=meta|twilio|gupshup`
  - `SMS_PROVIDER=twilio|gupshup|meta`
  - `EMAIL_PROVIDER=ses|sendgrid`
- Dead-letter queue behavior:
  - Job retries use exponential backoff
  - When `max_attempts` is reached, job is marked `dead_lettered`
  - Use `/v1/automation/jobs/{jobId}/retry` to retry after fixing provider config

## Migrations (Alembic)

Production should use migration-first schema management:

```bash
cd services/interview
alembic upgrade head
```

Migration files:
- `services/interview/alembic.ini`
- `services/interview/alembic/versions/`

Set `ENFORCE_MIGRATIONS=true` once migration workflow is your default.

## Deploy (VPS)

Use Docker Compose. For HTTPS and mic, put nginx in front; point WebSocket to port 8765 and the voice static UI to the mapped static port. Update `VOICE_*_PUBLIC_URL` in the **interview** service for the URLs your users load.

## Legacy file structure (reference)

- Root `start.sh` starts voice + interview together.  
- Full protocol: [packages/contracts/voice-websocket.md](packages/contracts/voice-websocket.md).
