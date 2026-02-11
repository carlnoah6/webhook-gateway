import json
import os
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Mock environment variables before importing app
os.environ["LARK_APP_ID"] = "test_app_id"
os.environ["LARK_APP_SECRET"] = "test_app_secret"
os.environ["WEBHOOK_SECRET_FILE"] = "tests/test_secret.txt"
os.environ["CI_EVENT_DIR"] = "tests/ci-events"

from src.main import app

client = TestClient(app)

# Helper to sign GitHub requests
def sign_github_request(body: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={signature}"

@pytest.fixture
def secret_file():
    os.makedirs("tests", exist_ok=True)
    with open("tests/test_secret.txt", "w") as f:
        f.write("test_secret")
    yield "test_secret"
    if os.path.exists("tests/test_secret.txt"):
        os.remove("tests/test_secret.txt")
    if os.path.exists("tests/ci-events"):
        import shutil
        shutil.rmtree("tests/ci-events")

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "webhook-gateway"}

def test_github_webhook_ping(secret_file):
    payload = json.dumps({"zen": "Keep it logically awesome."}).encode()
    signature = sign_github_request(payload, secret_file)
    headers = {
        "x-github-event": "ping",
        "x-hub-signature-256": signature,
        "content-type": "application/json"
    }
    response = client.post("/webhook/github", content=payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "msg": "pong"}

def test_github_webhook_invalid_signature(secret_file):
    payload = json.dumps({"foo": "bar"}).encode()
    headers = {
        "x-github-event": "ping",
        "x-hub-signature-256": "sha256=invalid",
        "content-type": "application/json"
    }
    response = client.post("/webhook/github", content=payload, headers=headers)
    assert response.status_code == 401

def test_lark_challenge():
    payload = {"challenge": "test_challenge", "token": "verify_token", "type": "url_verification"}
    response = client.post("/webhook/lark", json=payload)
    assert response.status_code == 200
    assert response.json() == {"challenge": "test_challenge"}

@patch("src.webhook.lark.asyncio.create_subprocess_exec")
def test_lark_dashboard_refresh(mock_subprocess):
    # Mock subprocess
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (b"ok", b"")
    mock_proc.returncode = 0
    
    # Setup async mock
    async def async_mock(*args, **kwargs):
        return mock_proc
    mock_subprocess.side_effect = async_mock

    payload = {
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "action": {
                "value": {"action": "refresh_dashboard"},
                "tag": "button"
            }
        }
    }
    
    # We use TestClient which runs synchronously, but FastAPI handles async endpoints.
    # Background tasks run after the response.
    with TestClient(app) as tc:
        response = tc.post("/webhook/lark", json=payload)
        assert response.status_code == 200
        assert response.json()["toast"]["type"] == "success"
