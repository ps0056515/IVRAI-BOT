# API contracts (shared)

- **`voice-websocket.md`** — WebSocket message schema for the **voice** service (browser ↔ `services/voice`).
- **`openapi/interview-api.yaml`** — OpenAPI 3.0 for the **interview** REST service (`services/interview`).

The voice layer is transport-specific (WebSocket + binary PCM); the interview control plane is HTTP (FastAPI) and can evolve independently.
