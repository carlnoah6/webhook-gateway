# webhook-gateway

Webhook gateway service for CI/CD notifications and Lark card callbacks.

## Overview

This service consolidates webhook handling into a single lightweight gateway:

- **`/webhook/github`** — Receives GitHub `workflow_run` events, verifies HMAC-SHA256 signatures, and saves event files for downstream processing.
- **`/webhook/lark`** — Handles Lark challenge verification, card action callbacks (e.g. dashboard refresh), and OAuth login flow.
- **`/health`** — Health check endpoint.

## Quick Start

### Local Development

```bash
pip install -r requirements.txt
pip install ruff pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Run server
python -m uvicorn src.app:app --host 0.0.0.0 --port 8280
```

### Docker

```bash
docker compose up -d
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8280` | Server listen port |
| `WEBHOOK_SECRET_FILE` | `/app/webhook_secret.txt` | Path to GitHub webhook HMAC secret file |
| `CI_EVENT_DIR` | `/app/ci-events` | Directory to save CI event JSON files |
| `LARK_APP_ID` | (empty) | Lark application ID |
| `LARK_APP_SECRET` | (empty) | Lark application secret |
| `LARK_TOKEN_FILE` | `/app/data/lark-user-token.json` | Path to store Lark user access token |
| `OPENCLAW_WEBHOOK_URL` | `http://localhost:18789/webhook/lark` | URL to forward non-dashboard card actions |
| `DASHBOARD_REFRESH_SCRIPT` | (see config.py) | Path to dashboard refresh script |

## Deployment

### Docker Compose (Production)

1. Copy `webhook_secret.txt` to the deployment directory.
2. Set environment variables (e.g. via `.env` file):
   ```
   LARK_APP_ID=your_app_id
   LARK_APP_SECRET=your_app_secret
   ```
3. Start the service:
   ```bash
   docker compose up -d
   ```

### CI/CD

- **CI** (`ci.yml`): Runs lint (ruff) and tests (pytest) on every PR.
- **Deploy** (`deploy.yml`): On push to main, builds Docker image, pushes to `ghcr.io/carlnoah6/webhook-gateway`, and deploys via self-hosted runner.

## Architecture

```
GitHub ──webhook──> /webhook/github ──> CI event files (JSON)
                                           └──> OpenClaw wake trigger

Lark   ──callback──> /webhook/lark
                       ├── challenge ──> echo challenge token
                       ├── refresh_dashboard ──> run script
                       ├── other card action ──> forward to OpenClaw
                       └── OAuth GET ──> exchange code for token
```

## License

MIT
