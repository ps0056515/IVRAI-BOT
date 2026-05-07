from __future__ import annotations

import json
import os
import sys

import httpx


BASE = os.getenv("CRM_BASE_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-this-webhook-secret")
ADMIN_USER = os.getenv("CRM_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("CRM_ADMIN_PASSWORD", "admin123")


def must(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(msg)


def main() -> None:
    with httpx.Client(timeout=15) as client:
        login = client.post(
            f"{BASE}/v1/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        must(login.status_code == 200, f"login failed: {login.status_code} {login.text}")
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        hook = client.post(
            f"{BASE}/v1/calls/webhook",
            headers={"x-webhook-secret": WEBHOOK_SECRET},
            json={
                "call_id": "ci-e2e-001",
                "caller_number": "+919000000001",
                "caller_name": "CI User",
                "duration_sec": 120,
                "unit": "qspiders",
                "transcript": "Need selenium course and EMI support",
                "assistant_reply": "Sure, EMI options are available.",
                "branch_interest": "BTM Layout",
                "latency_ms": 900,
                "stt_ms": 120,
                "llm_ms": 320,
                "tts_ms": 240,
            },
        )
        must(hook.status_code == 200, f"webhook failed: {hook.status_code} {hook.text}")
        lead_id = hook.json()["lead"]["lead_id"]

        stage = client.post(
            f"{BASE}/v1/leads/{lead_id}/stage",
            headers={**auth, "Content-Type": "application/json"},
            data=json.dumps({"stage": "counselling", "note": "CI transition"}),
        )
        must(stage.status_code == 200, f"stage update failed: {stage.status_code} {stage.text}")

        pay = client.post(
            f"{BASE}/v1/leads/{lead_id}/payments",
            headers={**auth, "Content-Type": "application/json"},
            data=json.dumps({"amount_inr": 5000, "payment_mode": "upi", "emi_part": 1}),
        )
        must(pay.status_code == 200, f"payment failed: {pay.status_code} {pay.text}")

        conv = client.get(f"{BASE}/v1/leads/{lead_id}/conversation", headers=auth)
        must(conv.status_code == 200, f"conversation fetch failed: {conv.status_code} {conv.text}")
        turns = conv.json().get("turns", [])
        must(len(turns) >= 2, "conversation turns not captured")

        metrics = client.get(f"{BASE}/v1/ops/metrics", headers=auth)
        must(metrics.status_code == 200, f"metrics failed: {metrics.status_code} {metrics.text}")
    print("CRM E2E PASS", {"lead_id": lead_id, "turns": len(turns)})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print("CRM E2E FAIL", exc)
        sys.exit(1)
