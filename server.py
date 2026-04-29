"""
Shim: run the voice service from `services/voice/server.py` (keeps `python server.py` at repo root working).
"""
import runpy
from pathlib import Path

path = Path(__file__).resolve().parent / "services" / "voice" / "server.py"
if not path.is_file():
    raise SystemExit(f"Voice service not found: {path}")
runpy.run_path(str(path), run_name="__main__")
