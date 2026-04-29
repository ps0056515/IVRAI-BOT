# Voice service: Whisper + Claude + gTTS, WebSocket + static demo
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/voice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/voice/ /app/

ARG WHISPER_MODEL=base
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" || true

EXPOSE 8765 8080

ENV HOST=0.0.0.0
ENV PORT=8765
ENV STATIC_PORT=8080
ENV WHISPER_MODEL=base
ENV WHISPER_DEVICE=cpu

RUN chmod +x /app/start-docker.sh
CMD ["/app/start-docker.sh"]
