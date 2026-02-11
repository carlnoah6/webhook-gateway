import logging
import os
from pathlib import Path

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("webhook-gateway")

# Environment Variables
PORT = int(os.getenv("PORT", 8280))

# Lark
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_ENCRYPT_KEY = os.getenv("LARK_ENCRYPT_KEY")  # Optional: if encryption is used
OPENCLAW_WEBHOOK_URL = os.getenv("OPENCLAW_WEBHOOK_URL", "http://host.docker.internal:18789/webhook/lark")
DASHBOARD_REFRESH_SCRIPT = os.getenv(
    "DASHBOARD_REFRESH_SCRIPT",
    "/home/ubuntu/.openclaw/workspace/scripts/lark-task-dashboard.py"
)

# GitHub
WEBHOOK_SECRET_FILE = Path(os.getenv(
    "WEBHOOK_SECRET_FILE",
    "/app/webhook_secret.txt"
))
CI_EVENT_DIR = Path(os.getenv(
    "CI_EVENT_DIR",
    "/app/ci-events"
))

# Validation
if not LARK_APP_ID or not LARK_APP_SECRET:
    log.warning("LARK_APP_ID or LARK_APP_SECRET not set. Lark functionality may fail.")
