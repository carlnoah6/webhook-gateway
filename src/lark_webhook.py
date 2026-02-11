"""Lark webhook handler for card callbacks and OAuth.

Handles:
- Lark challenge verification
- Card action callbacks (refresh dashboard, forward to OpenClaw)
- OAuth callback for Lark login
"""
import asyncio
import json
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .config import (
    DASHBOARD_REFRESH_SCRIPT,
    LARK_APP_ID,
    LARK_APP_SECRET,
    LARK_TOKEN_FILE,
    OPENCLAW_WEBHOOK_URL,
    log,
)

router = APIRouter()


@router.post("/webhook/lark")
async def lark_webhook_post(request: Request):
    """Handle Lark challenge verification and card action callbacks."""
    body = await request.json()

    # Challenge verification
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    # Detect event type
    event_type = ""
    if isinstance(body.get("header"), dict):
        event_type = body["header"].get("event_type", "")

    if event_type.startswith("card.action.trigger"):
        return await _handle_card_action(request, body)

    return {"status": "ok"}


async def _handle_card_action(request: Request, body: dict) -> JSONResponse | dict:
    """Handle Lark card action trigger events."""
    event = body.get("event") or {}
    action = event.get("action") if isinstance(event, dict) else {}
    action_value = action.get("value", {}) if isinstance(action, dict) else {}

    # Special handling: refresh dashboard (bypass LLM)
    if (
        isinstance(action_value, dict)
        and action_value.get("action") == "refresh_dashboard"
    ):
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                DASHBOARD_REFRESH_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=15)
            return JSONResponse(
                content={"toast": {"type": "success", "content": "Refreshed"}}
            )
        except Exception as e:
            return JSONResponse(
                content={
                    "toast": {
                        "type": "error",
                        "content": f"Refresh failed: {str(e)[:50]}",
                    }
                }
            )

    # Other card actions: forward to OpenClaw webhook
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                OPENCLAW_WEBHOOK_URL,
                json=body,
                timeout=5,
            )
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        log.error(f"Failed to forward card action to OpenClaw: {e}")
        return {"status": "error", "detail": str(e)}


@router.get("/webhook/lark")
async def lark_webhook_get(code: str = None, state: str = None):
    """Handle OAuth callback from Lark."""
    if not code:
        return {"status": "ok"}

    try:
        async with httpx.AsyncClient() as client:
            # Get app_access_token
            token_resp = await client.post(
                "https://open.larksuite.com/open-apis/auth/v3/app_access_token/internal",
                json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET},
                timeout=10,
            )
            app_token = token_resp.json().get("app_access_token", "")

            # Exchange code for user_access_token
            user_resp = await client.post(
                "https://open.larksuite.com/open-apis/authen/v1/oidc/access_token",
                json={"grant_type": "authorization_code", "code": code},
                headers={"Authorization": f"Bearer {app_token}"},
                timeout=10,
            )
            token_data = user_resp.json()

        if token_data.get("code") == 0:
            os.makedirs(os.path.dirname(LARK_TOKEN_FILE), exist_ok=True)
            with open(LARK_TOKEN_FILE, "w") as f:
                json.dump(token_data.get("data", {}), f, indent=2)
            return HTMLResponse(
                "✅ Authorization successful! Calendar access has been granted. "
                "You can close this page now."
            )
        else:
            return HTMLResponse(
                f"❌ Authorization failed: {json.dumps(token_data, ensure_ascii=False)}"
            )
    except Exception as e:
        log.error(f"OAuth callback failed: {e}")
        return HTMLResponse(f"❌ OAuth error: {e}")
