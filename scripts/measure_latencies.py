"""
Offline-ish benchmark: time STT, LLM, and TTS separately (same code paths as the voice server).
Usage from repo root:  python scripts/measure_latencies.py
Requires: .env with ANTHROPIC_API_KEY for LLM; otherwise STT+TTS only.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "voice"))


def main() -> None:
    os.chdir(ROOT)
    for env_path in (ROOT / ".env",):
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"')
                    # Drop inline comments (e.g. WHISPER_MODEL=base  # note)
                    if "#" in v and not (v.startswith('"') and v.count('"') >= 2):
                        v = v.split("#", 1)[0].strip().rstrip('"').strip()
                    # Always apply from .env (override broken shell/env values)
                    os.environ[k] = v
            break

    # Import after env
    import server  # type: ignore

    # --- STT: ~1.0s of float32 (speech-like length); pure noise decodes to empty often — still times inference
    import numpy as np

    t0 = time.time()
    server.get_whisper()
    load_s = time.time() - t0
    print(f"Whisper model load: {load_s:.1f}s (first time only)")

    audio_s = 1.0
    n = int(16000 * audio_s)
    # Soft noise + weak tone so VAD/Whisper have something to chew on
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(n).astype(np.float32) * 0.02 + np.sin(2 * np.pi * 440 * np.arange(n) / 16000.0) * 0.01).astype(
        np.float32
    )
    t1 = time.time()
    text, stt_ms = server.transcribe(x)
    t_wall = (time.time() - t1) * 1000
    print(f"STT wall {t_wall:.0f}ms (reported {stt_ms}ms)  text={text!r}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY missing — skip LLM/TTS (set .env to benchmark).")
        return

    server.get_anthropic()  # warm TLS/import so LLM wall matches internal timing

    conv = server.Conversation(
        "You are a test harness. Reply with exactly: OK"
    )
    t2 = time.time()
    reply, llm_ms = server.chat(conv, "Say the word OK only.")
    t_wall = (time.time() - t2) * 1000
    print(f"LLM wall {t_wall:.0f}ms (reported {llm_ms}ms)  reply={repr(reply)[:80]}")

    short = "This is a short TTS test."
    t3 = time.time()
    _mp3, tts_ms = server.synthesize(short)
    t_wall = (time.time() - t3) * 1000
    print(f"TTS  wall {t_wall:.0f}ms (reported {tts_ms}ms)  mp3 bytes={len(_mp3)}")

    print("\nTypical live round ~= stt + llm + tts (sequential), plus your recording length and network.")


if __name__ == "__main__":
    main()
