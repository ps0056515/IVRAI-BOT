"""
Interview & Assessment Platform — REST control plane (scaffold).
The voice media pipeline is a separate service (services/voice).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

# Monorepo: app/main -> repo root is four parents. Docker: /app/app/main -> use /app/.env
_f = Path(__file__).resolve()
for _cand in (
    _f.parents[3] / ".env" if len(_f.parents) > 3 else None,
    _f.parents[1] / ".env",
):
    if _cand is not None and _cand.is_file():
        load_dotenv(_cand)
        break
else:
    load_dotenv()

APP_VERSION = "0.1.0"
DEFAULT_INTERVIEW_CORS = os.getenv("INTERVIEW_CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000")


def _cors_list() -> list[str]:
    return [o.strip() for o in DEFAULT_INTERVIEW_CORS.split(",") if o.strip()]


app = FastAPI(
    title="Interview & Assessment Platform",
    version=APP_VERSION,
    description="Control-plane API. Voice STT/LLM/TTS lives in the `voice` service — see /v1/integrations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list() or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ServiceInfo(BaseModel):
    """`http://localhost:8000` is this API. The voice (student) page is a different port — see `student_voice_ui`."""
    service: str = "interview-platform"
    version: str = APP_VERSION
    message: str = (
        "You are on the interview REST API. For the browser voice UI (students), open `student_voice_ui` "
        "(usually http://localhost:8080), not this port."
    )
    student_voice_ui: str = Field(
        description="URL students open in the browser to speak with the voice bot (static server + WebSocket).",
    )
    voice_websocket: str = Field(
        description="WebSocket the voice page connects to; use wss:// in production.",
    )
    api_docs: str = Field(description="Swagger UI for this API.")


class PublicIntegrationInfo(BaseModel):
    """How clients connect to the separate voice service (dev defaults)."""
    voice_websocket_url: str = Field(description="wss:// or ws:// URL for the voice WebSocket")
    voice_demo_ui_url: str = Field(description="Static demo for the raw voice service")


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/integrations", response_model=PublicIntegrationInfo, tags=["integrations"])
def integrations() -> PublicIntegrationInfo:
    """
    Hints for wiring the browser or other UIs to the voice service.
    In production, set VOICE_*_PUBLIC_URL to the URLs clients should use.
    """
    return PublicIntegrationInfo(
        voice_websocket_url=os.getenv("VOICE_WS_PUBLIC_URL", "ws://localhost:8765"),
        voice_demo_ui_url=os.getenv("VOICE_HTTP_PUBLIC_URL", "http://localhost:8080"),
    )


@app.get("/", response_model=ServiceInfo, tags=["ops"])
def root(request: Request) -> ServiceInfo:
    base = str(request.base_url).rstrip("/")
    return ServiceInfo(
        student_voice_ui=os.getenv("VOICE_HTTP_PUBLIC_URL", "http://localhost:8080"),
        voice_websocket=os.getenv("VOICE_WS_PUBLIC_URL", "ws://localhost:8765"),
        api_docs=f"{base}/docs",
    )


@app.get("/go/voice", tags=["ops"])
def go_voice() -> RedirectResponse:
    """Browser shortcut: redirect to the voice (student) demo page."""
    url = os.getenv("VOICE_HTTP_PUBLIC_URL", "http://localhost:8080")
    return RedirectResponse(url, status_code=302)


# --- Placeholder for upcoming PRD resources ---


@app.post(
    "/v1/interview-sessions",
    tags=["interview"],
    summary="(Planned) Create an interview session",
)
def create_interview_session_stub() -> None:
    raise HTTPException(
        status_code=501,
        detail="Not implemented. Interview orchestration will be added in a follow-up.",
    )
