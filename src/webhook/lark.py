"""Lark webhook handler."""
import asyncio
import json
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, Request

from ..config import (
    DASHBOARD_REFRESH_SCRIPT,
    OPENCLAW_WEBHOOK_URL,
    log,
)

router = APIRouter()

async def run_refresh_script():
    """Run the dashboard refresh script in the background."""
    try:
        log.info(f"Triggering dashboard refresh: {DASHBOARD_REFRESH_SCRIPT}")

        # Pass environment variables to the script
        env = os.environ.copy()

        proc = await asyncio.create_subprocess_exec(
            "python3",
            DASHBOARD_REFRESH_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            log.info(f"Dashboard refreshed successfully: {stdout.decode().strip()}")
        else:
            log.error(f"Dashboard refresh failed: {stderr.decode().strip()}")

    except Exception as e:
        log.error(f"Error running refresh script: {e}")

@router.post("/lark")
async def lark_webhook(request: Request, background_tasks: BackgroundTasks):
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
    # Lark v2 event format or v1?
    # Usually card actions come in specific format.
    # The existing code checks for 'header' -> 'event_type'

    header = body.get("header", {})
    event_type = header.get("event_type", "")

    if event_type == "card.action.trigger":
        event = body.get("event", {})
        action = event.get("action", {})
        # Lark action value is usually a dict if defined in card as value={}
        action_value = action.get("value", {})

        # Check for specific 'refresh_dashboard' action
        if isinstance(action_value, dict) and action_value.get("action") == "refresh_dashboard":
            log.info("Received refresh_dashboard action")
            try:
                # Build fresh card JSON via card-builder (reads workspace/data/)
                card_builder = os.path.join(
                    os.path.dirname(DASHBOARD_REFRESH_SCRIPT),
                    "lark-card-builder.py",
                )
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    card_builder,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=15
                )
                if proc.returncode != 0:
                    raise RuntimeError(stderr.decode()[:100])

                # Return card JSON directly in callback response.
                # Lark updates the card in-place from the response content.
                card = json.loads(stdout.decode())
                log.info("Dashboard card rebuilt, returning inline")
                return card
            except Exception as e:
                log.error(f"Dashboard refresh failed: {e}")
                return {"toast": {"type": "error", "content": f"Refresh failed: {str(e)[:50]}"}}

        # Forward other actions to OpenClaw
        try:
            log.info(f"Forwarding action to OpenClaw: {OPENCLAW_WEBHOOK_URL}")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    OPENCLAW_WEBHOOK_URL,
                    json=body,
                    timeout=5
                )
            # Return OpenClaw's response directly to Lark (important for toasts etc)
            try:
                return resp.json()
            except Exception:
                return {"status": "ok", "forwarded": True}
        except Exception as e:
            log.error(f"Failed to forward to OpenClaw: {e}")
            return {"toast": {"type": "error", "content": "Failed to forward action"}}

    return {"status": "ok"}
