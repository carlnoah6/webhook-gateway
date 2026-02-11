"""Lark webhook handler."""
import asyncio
import httpx
import json
import os
from fastapi import APIRouter, Request, BackgroundTasks
from ..config import (
    log, 
    LARK_APP_ID, 
    LARK_APP_SECRET, 
    OPENCLAW_WEBHOOK_URL,
    DASHBOARD_REFRESH_SCRIPT
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
            background_tasks.add_task(run_refresh_script)
            return {"toast": {"type": "success", "content": "Refreshing dashboard..."}}
        
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
            except:
                return {"status": "ok", "forwarded": True}
        except Exception as e:
            log.error(f"Failed to forward to OpenClaw: {e}")
            return {"toast": {"type": "error", "content": "Failed to forward action"}}

    return {"status": "ok"}
