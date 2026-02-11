"""GitHub webhook handler."""
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Request, Response

from ..config import CI_EVENT_DIR, WEBHOOK_SECRET_FILE, log

router = APIRouter()

# Workflow names that count as "deploy" (case-insensitive)
DEPLOY_WORKFLOWS = {"deploy", "deployment", "release"}

def _load_secret() -> str:
    """Load webhook secret from file."""
    try:
        if WEBHOOK_SECRET_FILE.exists():
            return WEBHOOK_SECRET_FILE.read_text().strip()
    except Exception as e:
        log.error(f"Failed to load webhook secret: {e}")
    return ""

def _verify_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub HMAC-SHA256 signature."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header[7:]
    computed = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, expected)

def _save_event(message: str, data: dict):
    """Save CI event to file."""
    try:
        CI_EVENT_DIR.mkdir(parents=True, exist_ok=True)
        workflow_run = data.get("workflow_run", {})
        event_data = {
            "message": message,
            "repo": workflow_run.get("repository", {}).get("full_name", ""),
            "workflow": workflow_run.get("name", ""),
            "conclusion": workflow_run.get("conclusion", ""),
            "run_url": workflow_run.get("html_url", ""),
            "branch": workflow_run.get("head_branch", ""),
            "timestamp": time.time(),
        }
        # Use microsecond timestamp to avoid collisions
        filename = f"{int(time.time() * 1000000)}.json"
        event_file = CI_EVENT_DIR / filename
        event_file.write_text(json.dumps(event_data, indent=2))
        log.info(f"CI event saved: {event_file.name}")

        # Trigger OpenClaw wake - using host gateway due to docker isolation
        # We can't easily run 'openclaw' command from inside docker if it's not installed.
        # But Phase 2 architecture implies we just drop the file and Luna picks it up via heartbeat?
        # The original code ran `openclaw cron add --wake now`.
        # Since we are containerized, we might need a different wake mechanism or rely on heartbeat.
        # For now, we just save the file. The prompt says "save event file... for Luna to process".
    except Exception as e:
        log.error(f"Failed to save event: {e}")

def _is_deploy_workflow(name: str) -> bool:
    return name.lower().strip() in DEPLOY_WORKFLOWS

def _format_message(data: dict) -> str | None:
    workflow_run = data.get("workflow_run", {})
    repo = workflow_run.get("repository", {}).get("full_name", "unknown")
    workflow_name = workflow_run.get("name", "unknown")
    conclusion = workflow_run.get("conclusion", "unknown")
    run_url = workflow_run.get("html_url", "")
    branch = workflow_run.get("head_branch", "unknown")

    head_commit = workflow_run.get("head_commit")
    commit_msg = head_commit.get("message", "").split("\n")[0] if head_commit else ""

    pr_info = ""
    pull_requests = workflow_run.get("pull_requests", [])
    if pull_requests:
        pr_number = pull_requests[0].get("number", "")
        pr_info = f"\nPR: #{pr_number}"

    is_deploy = _is_deploy_workflow(workflow_name)

    if conclusion == "success" and is_deploy:
        emoji = "🚀"
        status = "Deploy Succeeded"
    elif conclusion in ("failure", "cancelled", "timed_out"):
        emoji = "❌" if conclusion == "failure" else "⚠️"
        status = f"CI {conclusion.replace('_', ' ').title()}"
    elif conclusion == "success":
        log.info(f"Skipping: {repo} / {workflow_name} succeeded (not deploy)")
        return None
    else:
        log.info(f"Skipping: {repo} / {workflow_name} conclusion={conclusion}")
        return None

    lines = [
        f"{emoji} {status}",
        f"Repo: {repo}",
        f"Workflow: {workflow_name}",
        f"Branch: {branch}",
    ]
    if commit_msg:
        lines.append(f"Commit: {commit_msg}")
    if pr_info:
        lines.append(pr_info)
    lines.append(f"Link: {run_url}")

    return "\n".join(lines)

@router.post("/github")
async def github_webhook(request: Request):
    body = await request.body()
    secret = _load_secret()
    signature = request.headers.get("x-hub-signature-256", "")

    if not _verify_signature(body, signature, secret):
        log.warning("GitHub webhook: invalid signature")
        return Response(content="Invalid signature", status_code=401)

    event_type = request.headers.get("x-github-event", "")
    if event_type == "ping":
        return {"ok": True, "msg": "pong"}

    if event_type != "workflow_run":
        return {"ok": True, "msg": "ignored"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return Response(content="Invalid JSON", status_code=400)

    if data.get("action") != "completed":
        return {"ok": True, "msg": "ignored action"}

    message = _format_message(data)
    if message:
        _save_event(message, data)

    return {"ok": True}
