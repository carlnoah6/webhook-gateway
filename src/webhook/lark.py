"""Lark webhook handler."""
import asyncio

import httpx
from fastapi import APIRouter, Request

from ..config import (
    DASHBOARD_REFRESH_SCRIPT,
    OPENCLAW_WEBHOOK_URL,
    log,
)

router = APIRouter()


@router.post("/lark")
async def lark_webhook(request: Request):
    """Handle Lark events (challenge & card actions)."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "msg": "Invalid JSON"}

    # 1. Handle Challenge (for initial configuration)
    if "challenge" in body:
        log.info("Handling Lark challenge")
        return {"challenge": body["challenge"]}

    # 2. Handle Card Actions
    header = body.get("header", {})
    event_type = header.get("event_type", "")

    if event_type == "card.action.trigger":
        event = body.get("event", {})
        action = event.get("action", {})
        action_value = action.get("value", {})

        # Refresh dashboard: run lark-task-dashboard.py synchronously
        # (builds card + PATCHes via Lark API), then return empty 200.
        if (
            isinstance(action_value, dict)
            and action_value.get("action") == "refresh_dashboard"
        ):
            log.info("Received refresh_dashboard action")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    DASHBOARD_REFRESH_SCRIPT,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=15
                )
                if proc.returncode != 0:
                    raise RuntimeError(stderr.decode()[:100])
                log.info(
                    f"Dashboard refreshed: {stdout.decode().strip()}"
                )
                return {}
            except Exception as e:
                log.error(f"Dashboard refresh failed: {e}")
                return {
                    "toast": {
                        "type": "error",
                        "content": f"Refresh failed: {str(e)[:50]}",
                    }
                }

        # Forward other card actions to OpenClaw
        try:
            log.info(f"Forwarding action to OpenClaw: {OPENCLAW_WEBHOOK_URL}")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    OPENCLAW_WEBHOOK_URL,
                    json=body,
                    timeout=5,
                )
            try:
                return resp.json()
            except Exception:
                return {"status": "ok", "forwarded": True}
        except Exception as e:
            log.error(f"Failed to forward to OpenClaw: {e}")
            return {
                "toast": {
                    "type": "error",
                    "content": "Failed to forward action",
                }
            }

    return {"status": "ok"}
