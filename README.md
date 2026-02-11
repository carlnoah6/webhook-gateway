# Webhook Gateway

A dedicated gateway for handling GitHub webhooks (CI/CD notifications) and Lark/Feishu card callbacks.

## Features

- **GitHub Webhook**: Receives `workflow_run` events, verifies signatures, and saves event data for Luna to process.
- **Lark Webhook**: Handles Lark card interactions (buttons) and challenges.
- **Dashboard Refresh**: Triggers local scripts to refresh the Luna task dashboard.

## Architecture

- **Port**: 8280
- **Container**: Dockerized Python (FastAPI) application.
- **Data Persistence**: Mounts host directories to save events and access shared scripts.

## Deployment

### Prerequisites

- Docker & Docker Compose
- Environment variables configured (see below)
- `webhook_secret.txt` present for GitHub signature verification.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/carlnoah6/webhook-gateway.git
   cd webhook-gateway
   ```

2. Configure environment (`.env` or via docker-compose):
   - `LARK_APP_ID`
   - `LARK_APP_SECRET`

3. Ensure secrets exist:
   - `webhook_secret.txt` (GitHub webhook secret)

4. Run:
   ```bash
   docker compose up -d
   ```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `8280` |
| `LARK_APP_ID` | Lark App ID | Required |
| `LARK_APP_SECRET` | Lark App Secret | Required |
| `OPENCLAW_WEBHOOK_URL` | Upstream OpenClaw webhook URL | `http://host.docker.internal:18789/webhook/lark` |
| `WEBHOOK_SECRET_FILE` | Path to GitHub secret file | `/app/webhook_secret.txt` |
| `CI_EVENT_DIR` | Directory to save CI events | `/app/ci-events` |
| `DASHBOARD_REFRESH_SCRIPT` | Path to dashboard script | (mounted path) |

## Development

- **Linting**: `ruff check .`
- **Testing**: `pytest`
- **Security**: `gitleaks detect`

## License

MIT
