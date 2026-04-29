#!/usr/bin/env bash
# Used inside the voice container (env from docker-compose, no .env file required)
set -e
cd "$(dirname "$0")"
python server.py &
WS_PID=$!
python static_server.py &
HTTP_PID=$!
trap "kill $WS_PID $HTTP_PID 2>/dev/null; exit" INT TERM
wait
