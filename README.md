# VoiceBot

Monorepo with two deployable services: a **voice** media pipeline and an **interview** control API (scaffold for the full assessment platform).

**Voice (real time):** Whisper (STT) → Claude Haiku (LLM) → gTTS (TTS)

```
Browser mic → raw PCM → WebSocket → Whisper → Claude → gTTS → MP3 → browser
```

## Layout

| Path | Role |
|------|------|
| `services/voice/` | WebSocket STT/LLM/TTS + static demo UI in `static/` |
| `services/interview/` | FastAPI app ( health, integration hints, future JD/interview flow ) |
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

Voice-only: `bash services/voice/start.sh` (from repo root; loads root `.env`).

### Windows (PowerShell)

```powershell
cd voicebot
.\scripts\start_dev.ps1
```

## Docker

Builds and runs both services. Voice static UI is on host port **8081** (avoids clashing with other tools using 8080).

```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build
```

- **Voice UI:** http://localhost:8081  
- **WebSocket:** ws://localhost:8765  
- **Interview API:** http://localhost:8000  

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | required (voice) | Anthropic key |
| `PORT` | `8765` | WebSocket (voice) |
| `STATIC_PORT` | `8080` | Static demo (voice) |
| `INTERVIEW_PORT` | `8000` | REST API (interview) |
| `INTERVIEW_CORS_ORIGINS` | `localhost:8080,...` | CORS for interview API |
| `VOICE_WS_PUBLIC_URL` / `VOICE_HTTP_PUBLIC_URL` | see interview `/v1/integrations` | Hints for clients |

Whisper: `WHISPER_MODEL`, `WHISPER_DEVICE` — see [`.env.example`](.env.example). Use **separate comment lines** for values (inline `#` comments in `.env` are unsafe on some loaders).

## Deploy (VPS)

Use Docker Compose. For HTTPS and mic, put nginx in front; point WebSocket to port 8765 and the voice static UI to the mapped static port. Update `VOICE_*_PUBLIC_URL` in the **interview** service for the URLs your users load.

## Legacy file structure (reference)

- Root `start.sh` starts voice + interview together.  
- Full protocol: [packages/contracts/voice-websocket.md](packages/contracts/voice-websocket.md).
