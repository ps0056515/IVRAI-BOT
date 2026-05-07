#!/usr/bin/env bash
# Full stack: voice (WebSocket + static demo) + interview API
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
  echo "[start] Loaded $ROOT/.env"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[error] ANTHROPIC_API_KEY not set. Copy .env.example to .env and set your key (voice service requires it)."
  exit 1
fi
echo "[start] Installing dependencies (voice + interview)…"
pip install -r requirements.txt -q
echo "[start] WebSocket (voice) :${PORT:-8765}  |  static UI :${STATIC_PORT:-8080}  |  interview API :${INTERVIEW_PORT:-8000}"
echo "[start] Note: for full CRM queue + Postgres, use docker compose (includes postgres, redis, worker)."
( cd "$ROOT/services/voice" && python server.py ) &
WS_PID=$!
( cd "$ROOT/services/voice" && python static_server.py ) &
HTTP_PID=$!
( cd "$ROOT/services/interview" && python -m uvicorn app.main:app --host 0.0.0.0 --port "${INTERVIEW_PORT:-8000}" ) &
API_PID=$!
( cd "$ROOT/services/interview" && celery -A app.worker.celery_app.celery_app worker -Q crm_automations --loglevel=info ) &
WORKER_PID=$!
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Voice service UI:  http://localhost:${STATIC_PORT:-8080}"
echo "  WebSocket:         ws://localhost:${PORT:-8765}"
echo "  Interview API:     http://localhost:${INTERVIEW_PORT:-8000}"
echo "  CRM Webapp:        http://localhost:${INTERVIEW_PORT:-8000}/crm"
echo "  API docs:          http://localhost:${INTERVIEW_PORT:-8000}/docs"
echo "  Press Ctrl+C to stop all."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
trap "kill $WS_PID $HTTP_PID $API_PID $WORKER_PID 2>/dev/null; echo 'Stopped.'; exit" INT TERM
wait
