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
import uuid
import urllib.request
import wave
from pathlib import Path
from urllib.parse import quote
import numpy as np
import websockets
from websockets.server import WebSocketServerProtocol

# Load .env from repo root (override so .env always wins)
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_file = Path(__file__).resolve().parents[2] / ".env"
    if _env_file.is_file():
        _load_dotenv(_env_file, override=True)
except ImportError:
    pass

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


def emit_interview_webhook(
    call_id: str,
    transcript: str,
    assistant_reply: str,
    duration_sec: int,
    caller_number: str,
    caller_name: str,
    unit: str | None = None,
    branch_interest: str | None = None,
    batch_preference: str | None = None,
    course_interest: str | None = None,
    recording_url: str | None = None,
    user_recording_url: str | None = None,
    assistant_recording_url: str | None = None,
    latency_ms: int | None = None,
    stt_ms: int | None = None,
    llm_ms: int | None = None,
    tts_ms: int | None = None,
    source: str = "voice_ws",
) -> None:
    webhook_url = os.getenv("INTERVIEW_WEBHOOK_URL")
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if not webhook_url or not webhook_secret:
        return
    payload = {
        "call_id": call_id,
        "caller_number": caller_number,
        "caller_name": caller_name,
        "duration_sec": max(1, duration_sec),
        "unit": unit,
        "branch_interest": branch_interest,
        "batch_preference": batch_preference,
        "course_interest": course_interest,
        "transcript": transcript,
        "assistant_reply": assistant_reply,
        "recording_url": recording_url,
        "user_recording_url": user_recording_url,
        "assistant_recording_url": assistant_recording_url,
        "latency_ms": latency_ms,
        "stt_ms": stt_ms,
        "llm_ms": llm_ms,
        "tts_ms": tts_ms,
        "consent_played": True,
        "source": source,
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-webhook-secret": webhook_secret,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status >= 300:
                log.warning("Interview webhook returned status %s", resp.status)
    except Exception as exc:
        log.warning("Interview webhook emit failed: %s", exc)


def save_turn_audio(call_id: str, audio_bytes: bytes) -> str | None:
    if not audio_bytes:
        return None
    rec_dir = os.getenv("VOICE_RECORDINGS_DIR")
    if not rec_dir:
        rec_dir = str((Path(__file__).resolve().parent / "recordings").resolve())
    try:
        Path(rec_dir).mkdir(parents=True, exist_ok=True)
        out = Path(rec_dir) / f"{call_id}.mp3"
        out.write_bytes(audio_bytes)
        return "file:///" + quote(str(out).replace("\\", "/"), safe="/:.")
    except Exception as exc:
        log.warning("Failed to save recording: %s", exc)
        return None


def extract_enquiry_form(conversation: "Conversation", caller_name: str, caller_number: str) -> dict:
    """Use Claude to extract structured enquiry form data from the full conversation."""
    client = get_anthropic()
    # Build a readable transcript
    lines = []
    for m in conversation.messages:
        speaker = "STUDENT" if m["role"] == "user" else "ARIA"
        lines.append(f"{speaker}: {m['content']}")
    transcript_text = "\n".join(lines)

    extraction_prompt = f"""You are extracting structured data from an admissions call transcript.
The caller's known phone number is: {caller_number}
The caller's known name is: {caller_name}

Read the transcript carefully and extract every piece of information the student mentioned — even if they answered briefly or indirectly.
Be generous: if the student says "evening" infer class_timing="Evening". If they say "BTM" infer branch_interest="BTM Layout". If they say "Java" infer course_interest="Java".
For boolean fields: default to false unless clearly stated as true.

Return ONLY a valid JSON object. No explanation, no markdown fences.

JSON fields:
{{
  "enquiry_for_someone_else": false,   // true only if they say it's for a sibling/friend/child
  "experienced_enquiry": false,        // true if they mention work experience or currently working
  "name": null,                        // full name stated by student
  "phone": "{caller_number}",          // use provided phone; update only if student gives a different number
  "email": null,                       // email address
  "highest_degree": null,              // e.g. "B.E", "B.Sc", "MCA", "BCA", "12th", "Diploma"
  "year_of_passing": null,             // e.g. "2023", "2024"
  "course_interest": null,             // e.g. "Java", "Python", "Selenium", "Manual Testing", "Software Testing", "DevOps"
  "branch_interest": null,             // e.g. "BTM Layout", "Jayanagar", "HSR Layout", "Marathahalli"
  "mode_of_class": null,               // one of: "Classroom", "Online", "Hybrid"
  "class_timing": null,                // one of: "Morning", "Afternoon", "Evening", "Weekend"
  "time_slot": null,                   // e.g. "7am-9am", "9am-11am", "5pm-7pm", "7pm-9pm"
  "special_course": null,              // e.g. "ISTQB", "OCJP", "AWS", "DevOps"
  "other_course": null,
  "special_mode_of_class": null,
  "referral_name": null,               // name of person who referred them
  "referral_mobile": null,             // referrer's mobile number
  "enquiry_comments": null             // any questions, concerns, or extra info the student mentioned
}}

TRANSCRIPT:
{transcript_text}
"""
    try:
        resp = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-haiku-4-5"),
            max_tokens=800,
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        form_data = json.loads(raw)
        # Ensure caller_name / phone defaults
        if not form_data.get("name"):
            form_data["name"] = caller_name
        if not form_data.get("phone"):
            form_data["phone"] = caller_number
        log.info("Enquiry form extracted: %s", json.dumps(form_data, ensure_ascii=False)[:300])
        return form_data
    except Exception as exc:
        log.warning("Form extraction failed: %s", exc)
        return {"name": caller_name, "phone": caller_number}


def emit_form_webhook(
    session_call_id: str,
    caller_number: str,
    caller_name: str,
    full_transcript: str,
    duration_sec: int,
    unit: str | None,
    form_data: dict,
    recording_url: str | None = None,
) -> None:
    """Fire a session-end webhook carrying the full transcript and extracted form fields."""
    webhook_url = os.getenv("INTERVIEW_WEBHOOK_URL")
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if not webhook_url or not webhook_secret:
        return
    payload = {
        "call_id": session_call_id,
        "caller_number": caller_number,
        "caller_name": form_data.get("name") or caller_name,
        "duration_sec": max(1, duration_sec),
        "unit": unit,
        "transcript": full_transcript,
        "assistant_reply": "",
        "recording_url": recording_url,
        "consent_played": True,
        "source": "voice_ws_end",
        # Core fields already on Lead
        "course_interest": form_data.get("course_interest"),
        "branch_interest": form_data.get("branch_interest"),
        "batch_preference": form_data.get("time_slot"),
        # Enquiry form fields
        "enquiry_for_someone_else": form_data.get("enquiry_for_someone_else", False),
        "experienced_enquiry": form_data.get("experienced_enquiry", False),
        "email": form_data.get("email"),
        "class_timing": form_data.get("class_timing"),
        "time_slot": form_data.get("time_slot"),
        "highest_degree": form_data.get("highest_degree"),
        "year_of_passing": form_data.get("year_of_passing"),
        "mode_of_class": form_data.get("mode_of_class"),
        "special_course": form_data.get("special_course"),
        "other_course": form_data.get("other_course"),
        "special_mode_of_class": form_data.get("special_mode_of_class"),
        "referral_name": form_data.get("referral_name"),
        "referral_mobile": form_data.get("referral_mobile"),
        "enquiry_comments": form_data.get("enquiry_comments"),
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-webhook-secret": webhook_secret,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 300:
                log.warning("Form webhook returned status %s", resp.status)
            else:
                log.info("Session-end form webhook sent for %s", session_call_id)
    except Exception as exc:
        log.warning("Form webhook emit failed: %s", exc)


def save_user_pcm_audio(call_id: str, pcm_bytes: bytes, sample_rate: int = 16000) -> str | None:
    if not pcm_bytes:
        return None
    rec_dir = os.getenv("VOICE_RECORDINGS_DIR")
    if not rec_dir:
        rec_dir = str((Path(__file__).resolve().parent / "recordings").resolve())
    try:
        Path(rec_dir).mkdir(parents=True, exist_ok=True)
        out = Path(rec_dir) / f"{call_id}-user.wav"
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 PCM
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return "file:///" + quote(str(out).replace("\\", "/"), safe="/:.")
    except Exception as exc:
        log.warning("Failed to save user recording: %s", exc)
        return None

# ── WebSocket handler ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = os.getenv(
    "BOT_SYSTEM_PROMPT",
    """You are Aria, the AI admissions assistant for QSpiders, JSpiders, and PySiders — the leading software testing and programming training institutes in Bengaluru, India.

Your job is to warmly greet every caller and collect their enquiry details through a natural, friendly conversation. Ask ONE question at a time, confirm the answer briefly, then move to the next. Keep each response short — one or two sentences at most — because your words are spoken aloud.

Collect the following details in this order:
1. Is this enquiry for themselves or for someone else?
2. Are they a fresher or do they have work experience? (this is called Experienced Enquiry)
3. Their full name.
4. Their email address.
5. Their highest educational qualification (degree) and year of passing.
6. Which course they are interested in — for example: Java, Python, Selenium, Software Testing, Manual Testing, Automation Testing, DevOps, or any other.
7. Preferred branch or location — BTM Layout, Jayanagar, HSR Layout, Marathahalli, Rajajinagar, Electronic City, or any other.
8. Preferred mode of learning — Classroom, Online, or Hybrid.
9. Preferred class timing — Morning, Afternoon, Evening, or Weekend — and which time slot suits them.
10. Any interest in special certifications or courses such as ISTQB, OCJP, AWS, or any other.
11. Were they referred by anyone? If yes, get the referrer's name and mobile number.
12. Any other questions or comments they have.

After collecting all details, warmly thank the caller, confirm a counsellor will reach out soon, and wish them a great day.

Rules:
- Never use bullet points, numbered lists, markdown, or asterisks in your replies.
- Speak only in plain, natural sentences.
- If a caller skips a question or says they don't know, acknowledge politely and move on.
- If the caller asks about fees, batches, or course content, give a brief friendly answer and then continue collecting the remaining details.
- Always be patient, warm, and professional."""
)


async def handle_client(ws: WebSocketServerProtocol):
    remote = ws.remote_address
    log.info(f"Client connected: {remote}")

    conversation = Conversation(system_prompt=SYSTEM_PROMPT)
    session_id = uuid.uuid4().hex[:10]
    session_call_id = f"voicews-{session_id}"
    session_start = time.time()
    turn_no = 0
    session_transcripts: list[str] = []   # accumulate all user turns
    session_recording_url: str | None = None
    lead_context = {
        "caller_number": f"websocket-{session_id}",
        "caller_name": "Voice UI User",
        "unit": None,
        "branch_interest": None,
        "batch_preference": None,
        "course_interest": None,
    }

    await ws.send(json.dumps({
        "type": "connected",
        "message": "Voice service ready. Waiting for session start.",
    }))
    session_started = False

    try:
        async for message in ws:
            t_start = time.time()
            stt_ms: int = 0
            user_pcm_bytes: bytes | None = None

            if isinstance(message, bytes):
                user_pcm_bytes = message
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
                    session_transcripts.append(transcript)

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

                    if msg_type == "context":
                        lead_context["caller_number"] = (payload.get("caller_number") or "websocket-user").strip()
                        lead_context["caller_name"] = (payload.get("caller_name") or "Voice UI User").strip()
                        lead_context["unit"] = (payload.get("unit") or None)
                        lead_context["branch_interest"] = (payload.get("branch_interest") or None)
                        lead_context["batch_preference"] = (payload.get("batch_preference") or None)
                        lead_context["course_interest"] = (payload.get("course_interest") or None)
                        await ws.send(json.dumps({"type": "context_ack"}))
                        continue

                    if msg_type == "start":
                        session_started = True
                        session_start = time.time()
                        loop = asyncio.get_event_loop()
                        phone_hint = ""
                        if lead_context["caller_number"].startswith("websocket-"):
                            phone_hint = " Also ask for their mobile number early in the conversation."
                        try:
                            opening_reply, _ = await loop.run_in_executor(
                                None, chat, conversation,
                                f"[SYSTEM: The student has just started the enquiry call. Greet them warmly as Aria from QSpiders/JSpiders/PySiders, mention the call may be recorded for quality, then immediately ask question 1: whether this enquiry is for themselves or someone else.{phone_hint}]"
                            )
                            await ws.send(json.dumps({"type": "reply", "text": opening_reply}))
                            await ws.send(json.dumps({"type": "status", "status": "speaking"}))
                            try:
                                opening_audio, _ = await loop.run_in_executor(None, synthesize, opening_reply)
                                await ws.send(json.dumps({
                                    "type": "audio", "encoding": "mp3",
                                    "data": base64.b64encode(opening_audio).decode(),
                                }))
                            except Exception as e:
                                log.warning("Opening TTS failed: %s", e)
                            await ws.send(json.dumps({"type": "status", "status": "idle", "latency_ms": 0}))
                        except Exception as e:
                            log.warning("Opening greeting failed: %s", e)
                        continue

                    if msg_type == "stop":
                        await ws.send(json.dumps({"type": "session_ended"}))
                        await ws.close()
                        break

                    if msg_type == "reset":
                        conversation = Conversation(system_prompt=SYSTEM_PROMPT)
                        session_started = False
                        await ws.send(json.dumps({"type": "reset_ack"}))
                        continue

                    transcript = payload.get("text", "").strip()
                    if not transcript:
                        continue

                except json.JSONDecodeError:
                    transcript = message.strip()

            else:
                continue

            if not session_started:
                await ws.send(json.dumps({"type": "error", "message": "Session not started. Press Start first."}))
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
            audio_bytes = b""
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
            turn_no += 1
            call_id = f"voicews-{session_id}-{turn_no:03d}"
            loop = asyncio.get_event_loop()
            recording_url = None
            user_recording_url = None
            assistant_recording_url = None
            if user_pcm_bytes:
                user_recording_url = await loop.run_in_executor(None, save_user_pcm_audio, call_id, user_pcm_bytes, 16000)
            if audio_bytes:
                assistant_recording_url = await loop.run_in_executor(None, save_turn_audio, call_id, audio_bytes)
            recording_url = assistant_recording_url or user_recording_url
            if recording_url:
                session_recording_url = recording_url
            await loop.run_in_executor(
                None,
                emit_interview_webhook,
                call_id,
                transcript,
                reply,
                int(elapsed / 1000),
                lead_context["caller_number"],
                lead_context["caller_name"],
                lead_context["unit"],
                lead_context["branch_interest"],
                lead_context["batch_preference"],
                lead_context["course_interest"],
                recording_url,
                user_recording_url,
                assistant_recording_url,
                round(elapsed),
                stt_ms,
                llm_ms,
                tts_ms,
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
    finally:
        # ── Session-end: extract form data and fire final webhook ──
        if turn_no > 0 and os.getenv("INTERVIEW_WEBHOOK_URL"):
            try:
                duration_sec = int(time.time() - session_start)
                loop = asyncio.get_event_loop()
                form_data = await loop.run_in_executor(
                    None,
                    extract_enquiry_form,
                    conversation,
                    lead_context["caller_name"],
                    lead_context["caller_number"],
                )
                full_transcript = " | ".join(session_transcripts)
                await loop.run_in_executor(
                    None,
                    emit_form_webhook,
                    session_call_id,
                    lead_context["caller_number"],
                    lead_context["caller_name"],
                    full_transcript,
                    duration_sec,
                    lead_context.get("unit"),
                    form_data,
                    session_recording_url,
                )
            except Exception as exc:
                log.warning("Session-end form processing failed: %s", exc)


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
