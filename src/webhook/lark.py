"""Lark webhook handler.

Handles:
  - Challenge verification (initial setup)
  - Card action callbacks:
    - refresh_dashboard → build new card + update via /interactive/v1/card/update
    - Other actions → forward to OpenClaw webhook
"""
import asyncio

import httpx
from fastapi import APIRouter, Request

from ..config import (
    DASHBOARD_REFRESH_SCRIPT,
    LARK_APP_ID,
    LARK_APP_SECRET,
    OPENCLAW_WEBHOOK_URL,
    log,
)

router = APIRouter()

BASE_URL = "https://open.larksuite.com/open-apis"


async def _get_tenant_token() -> str:
    """Get Lark tenant_access_token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET},
            timeout=10,
        )
        return resp.json().get("tenant_access_token", "")


async def _refresh_dashboard(event: dict) -> dict:
    """Build new dashboard card and update via Lark card update API.

    Key technical details (learned through debugging 2026-02-12):
      1. PATCH /im/v1/messages/{id} updates server-side but does NOT
         trigger client-side re-render for interactive cards.
      2. Must use POST /interactive/v1/card/update with:
         - Authorization: Bearer <tenant_access_token>
         - token: the card action token from event.token
         - card: the card JSON with open_ids INSIDE the card object
      3. Callback response must return a toast (not {}), otherwise
         Lark shows error 200341.
    """
    import json as _json

    card_token = event.get("token", "")
    operator_id = event.get("operator", {}).get("open_id", "")

    # 1. Build new card via lark-card-builder.py (stdout = card JSON)
    card_builder = DASHBOARD_REFRESH_SCRIPT.replace(
        "lark-task-dashboard.py", "lark-card-builder.py"
    )
    proc = await asyncio.create_subprocess_exec(
        "python3",
        card_builder,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode()[:200])

    card = _json.loads(stdout.decode())

    # 2. open_ids must be INSIDE card object (not top-level)
    #    Without this: error 300090 "openid empty"
    if operator_id:
        card["open_ids"] = [operator_id]

    # 3. Call card update API with tenant_access_token
    #    Without auth header: error 99991661 "Missing access token"
    tenant_token = await _get_tenant_token()
    update_body = _json.dumps({"token": card_token, "card": card})

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/interactive/v1/card/update",
            content=update_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {tenant_token}",
            },
            timeout=10,
        )

    result = resp.json()
    if result.get("code") != 0:
        log.error(f"Card update failed: {resp.text[:200]}")
    else:
        log.info("Dashboard refreshed successfully")

    return result


@router.post("/lark")
async def lark_webhook(request: Request):
    """Handle Lark events (challenge & card actions)."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "msg": "Invalid JSON"}

    # 1. Challenge verification
    if "challenge" in body:
        log.info("Handling Lark challenge")
        return {"challenge": body["challenge"]}

    # 2. Card action callbacks
    header = body.get("header", {})
    event_type = header.get("event_type", "")

    if event_type == "card.action.trigger":
        event = body.get("event", {})
        action = event.get("action", {})
        action_value = action.get("value", {})

        # Dashboard refresh — handled directly, not forwarded to OpenClaw
        if (
            isinstance(action_value, dict)
            and action_value.get("action") == "refresh_dashboard"
        ):
            try:
                await _refresh_dashboard(event)
                # Return toast (not {}) to avoid Lark error 200341
                return {
                    "toast": {
                        "type": "success",
                        "content": "✅ 已刷新",
                    }
                }
            except Exception as e:
                log.error(f"Dashboard refresh failed: {e}")
                return {
                    "toast": {
                        "type": "error",
                        "content": f"刷新失败: {str(e)[:50]}",
                    }
                }

        # Other card actions — forward to OpenClaw
        try:
            log.info(f"Forwarding card action to OpenClaw: {OPENCLAW_WEBHOOK_URL}")
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
