"""
Voice service — STT (Whisper) → LLM (Claude) → TTS (gTTS).
WebSocket server for the reusable voice layer (see packages/contracts).
"""

import asyncio
import json
import logging
import os
import io
import base64
import tempfile
import time
import numpy as np
import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("voicebot")

# ── Lazy-loaded heavy models ──────────────────────────────────────────────────

_whisper_model = None
_anthropic_client = None

def _env_clean(key: str, default: str) -> str:
    """Strip accidental inline # comments from .env (e.g. 'base  # note')."""
    raw = os.getenv(key)
    if not raw:
        return default
    s = raw.split("#", 1)[0].strip()
    if not s:
        return default
    return s.split()[0]


def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = _env_clean("WHISPER_MODEL", "base")
        device = _env_clean("WHISPER_DEVICE", "cpu")
        log.info(f"Loading Whisper model '{model_size}' on {device}…")
        _whisper_model = WhisperModel(model_size, device=device, compute_type="int8")
        log.info("Whisper ready.")
    return _whisper_model

def get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client

# ── Conversation memory ───────────────────────────────────────────────────────

class Conversation:
    def __init__(self, system_prompt: str):
        self.system = system_prompt
        self.messages: list[dict] = []

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > 40:
            self.messages = self.messages[-40:]

    def get_messages(self):
        return self.messages

# ── Core pipeline functions ───────────────────────────────────────────────────

def pcm_bytes_to_float32(raw: bytes, sample_rate: int = 16000) -> np.ndarray:
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def transcribe(audio_np: np.ndarray, language: str = "en") -> tuple[str, int]:
    model = get_whisper()
    beam = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
    t0 = time.time()
    segments, info = model.transcribe(
        audio_np,
        language=language,
        beam_size=max(1, beam),
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    stt_ms = int((time.time() - t0) * 1000)
    log.info(f"STT {stt_ms}ms (beam={beam}): '{text[:120]}{'…' if len(text) > 120 else ''}'")
    return text, stt_ms


def chat(conversation: Conversation, user_text: str) -> tuple[str, int]:
    client = get_anthropic()
    conversation.add("user", user_text)
    t0 = time.time()
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-haiku-4-5"),
        max_tokens=512,
        system=conversation.system,
        messages=conversation.get_messages(),
    )
    reply = resp.content[0].text.strip()
    conversation.add("assistant", reply)
    llm_ms = int((time.time() - t0) * 1000)
    log.info(f"LLM {llm_ms}ms: '{reply[:80]}{'…' if len(reply) > 80 else ''}'")
    return reply, llm_ms


def synthesize(text: str, lang: str = "en") -> tuple[bytes, int]:
    from gtts import gTTS
    t0 = time.time()
    buf = io.BytesIO()
    gTTS(text=text, lang=lang, slow=False).write_to_fp(buf)
    buf.seek(0)
    audio_bytes = buf.read()
    tts_ms = int((time.time() - t0) * 1000)
    log.info(f"TTS {tts_ms}ms, {len(audio_bytes)} bytes mp3")
    return audio_bytes, tts_ms

# ── WebSocket handler ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = os.getenv(
    "BOT_SYSTEM_PROMPT",
    (
        "You are a helpful, concise voice assistant. "
        "Keep replies short and natural — they will be spoken aloud. "
        "Avoid markdown, bullet points, or long lists. "
        "Speak in plain conversational sentences."
    ),
)


async def handle_client(ws: WebSocketServerProtocol):
    remote = ws.remote_address
    log.info(f"Client connected: {remote}")

    conversation = Conversation(system_prompt=SYSTEM_PROMPT)

    await ws.send(json.dumps({
        "type": "connected",
        "message": "Voice service ready. Send audio bytes or a text message.",
    }))

    try:
        async for message in ws:
            t_start = time.time()
            stt_ms: int = 0

            if isinstance(message, bytes):
                await ws.send(json.dumps({"type": "status", "status": "transcribing"}))

                try:
                    audio_np = pcm_bytes_to_float32(message)
                    if audio_np.shape[0] < 1600:
                        await ws.send(json.dumps({"type": "error", "message": "Audio too short"}))
                        continue

                    loop = asyncio.get_event_loop()
                    transcript, stt_ms = await loop.run_in_executor(None, transcribe, audio_np)

                    if not transcript:
                        await ws.send(json.dumps({"type": "error", "message": "No speech detected"}))
                        continue

                    await ws.send(json.dumps({"type": "transcript", "text": transcript}))

                except Exception as e:
                    log.exception("STT error")
                    await ws.send(json.dumps({"type": "error", "message": f"STT failed: {e}"}))
                    continue

            elif isinstance(message, str):
                try:
                    payload = json.loads(message)
                    msg_type = payload.get("type", "text")

                    if msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue

                    if msg_type == "reset":
                        conversation = Conversation(system_prompt=SYSTEM_PROMPT)
                        await ws.send(json.dumps({"type": "reset_ack"}))
                        continue

                    transcript = payload.get("text", "").strip()
                    if not transcript:
                        continue

                except json.JSONDecodeError:
                    transcript = message.strip()

            else:
                continue

            await ws.send(json.dumps({"type": "status", "status": "thinking"}))
            try:
                loop = asyncio.get_event_loop()
                reply, llm_ms = await loop.run_in_executor(None, chat, conversation, transcript)
            except Exception as e:
                log.exception("LLM error")
                await ws.send(json.dumps({"type": "error", "message": f"LLM failed: {e}"}))
                continue

            await ws.send(json.dumps({"type": "reply", "text": reply}))

            await ws.send(json.dumps({"type": "status", "status": "speaking"}))
            tts_ms = 0
            try:
                audio_bytes, tts_ms = await loop.run_in_executor(None, synthesize, reply)
                await ws.send(json.dumps({
                    "type": "audio",
                    "encoding": "mp3",
                    "data": base64.b64encode(audio_bytes).decode(),
                }))
            except Exception as e:
                log.warning(f"TTS failed (non-fatal): {e}")

            elapsed = (time.time() - t_start) * 1000
            log.info(
                f"▸ Round total {elapsed:.0f}ms  (stt={stt_ms}  llm={llm_ms}  tts={tts_ms})"
            )
            await ws.send(json.dumps({
                "type": "status",
                "status": "idle",
                "latency_ms": round(elapsed),
                "stt_ms": stt_ms,
                "llm_ms": llm_ms,
                "tts_ms": tts_ms,
            }))

    except websockets.exceptions.ConnectionClosedOK:
        log.info(f"Client disconnected: {remote}")
    except websockets.exceptions.ConnectionClosedError as e:
        log.warning(f"Connection error ({remote}): {e}")
    except Exception:
        log.exception(f"Unhandled error for {remote}")


async def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8765"))

    log.info("Pre-loading Whisper model…")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_whisper)

    log.info(f"Voice service WebSocket on ws://{host}:{port}")
    async with websockets.serve(handle_client, host, port, max_size=100 * 1024 * 1024):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
