"""Environment-based configuration for webhook-gateway."""
import logging
import os
from pathlib import Path

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("webhook-gateway")

# ── Server ──
PORT = int(os.environ.get("PORT", "8280"))

# ── GitHub Webhook ──
WEBHOOK_SECRET_FILE = Path(
    os.environ.get("WEBHOOK_SECRET_FILE", "/app/webhook_secret.txt")
)
CI_EVENT_DIR = Path(
    os.environ.get("CI_EVENT_DIR", "/app/ci-events")
)

# ── Lark ──
LARK_APP_ID = os.environ.get("LARK_APP_ID", "")
LARK_APP_SECRET = os.environ.get("LARK_APP_SECRET", "")
LARK_TOKEN_FILE = os.environ.get(
    "LARK_TOKEN_FILE", "/app/data/lark-user-token.json"
)
OPENCLAW_WEBHOOK_URL = os.environ.get(
    "OPENCLAW_WEBHOOK_URL", "http://localhost:18789/webhook/lark"
)
DASHBOARD_REFRESH_SCRIPT = os.environ.get(
    "DASHBOARD_REFRESH_SCRIPT",
    "/home/ubuntu/.openclaw/workspace/scripts/lark-task-dashboard.py",
)
