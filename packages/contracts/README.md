# API contracts (shared)

- **`voice-websocket.md`** — WebSocket message schema for the **voice** service (browser ↔ `services/voice`).
- **`openapi/interview-api.yaml`** — OpenAPI 3.0 for the **interview** REST service (`services/interview`) including auth, admissions CRM, SLA/ops metrics, and automation retry/provider callback endpoints.

The voice layer is transport-specific (WebSocket + binary PCM); the interview control plane is HTTP (FastAPI) and can evolve independently.
