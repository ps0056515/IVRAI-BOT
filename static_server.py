"""
Shim: run `services/voice/static_server.py` to serve the demo UI from `services/voice/static/`.
"""
import runpy
from pathlib import Path

path = Path(__file__).resolve().parent / "services" / "voice" / "static_server.py"
if not path.is_file():
    raise SystemExit(f"Static server not found: {path}")
runpy.run_path(str(path), run_name="__main__")
