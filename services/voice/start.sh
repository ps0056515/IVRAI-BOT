#!/usr/bin/env bash
# Voice service only: WebSocket + static demo (run from repo root: bash services/voice/start.sh)
set -e
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../.. && pwd)"
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.env"
  set +a
  echo "[voice] Loaded $REPO_ROOT/.env"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[error] ANTHROPIC_API_KEY not set. Set it in $REPO_ROOT/.env"
  exit 1
fi
echo "[voice] WebSocket :${PORT:-8765}  static :${STATIC_PORT:-8080}"
python server.py &
WS_PID=$!
python static_server.py &
HTTP_PID=$!
trap "kill $WS_PID $HTTP_PID 2>/dev/null; echo '[voice] Stopped.'; exit" INT TERM
wait
