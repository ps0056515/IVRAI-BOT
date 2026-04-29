# Voice service WebSocket contract

**Endpoint:** `ws://<host>:<PORT>` (default `PORT=8765`).  
**Binary frames:** raw 16-bit little-endian PCM, mono, **16 kHz** (same as `server.py`).

**Server → client (JSON, text frames)**

| `type` | Notes |
|--------|--------|
| `connected` | Handshake: `{ "type":"connected", "message": string }` |
| `status` | `{ "type":"status", "status": "transcribing" \| "thinking" \| "speaking" \| "idle", "latency_ms"?: number }` |
| `transcript` | STT: `{ "type":"transcript", "text": string }` |
| `reply` | LLM: `{ "type":"reply", "text": string }` |
| `audio` | TTS: `{ "type":"audio", "encoding": "mp3", "data": "<base64>" }` |
| `error` | `{ "type":"error", "message": string }` |
| `reset_ack` | After `reset` |
| `pong` | After `ping` |

**Client → server**

| Payload | Description |
|--------|-------------|
| Binary | One utterance of PCM; server runs STT → LLM → TTS. |
| `{ "type":"text", "text":"..." }` | Skip STT; use as transcript. |
| `{ "type":"reset" }` | Clear in-memory dialog. |
| `{ "type":"ping" }` | Keepalive. |

Future: optional `type` to supply **per-turn `system` prompt** (for the interview app) can be added without breaking the above.
