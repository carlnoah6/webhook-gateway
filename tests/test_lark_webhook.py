"""Tests for Lark webhook handler."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app)


class TestChallengeVerification:
    """Test Lark challenge verification."""

    def test_challenge_echoed(self):
        resp = client.post(
            "/webhook/lark",
            json={"challenge": "test-challenge-token-abc123"},
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "test-challenge-token-abc123"

    def test_challenge_with_extra_fields(self):
        resp = client.post(
            "/webhook/lark",
            json={
                "challenge": "another-token",
                "token": "verification-token",
                "type": "url_verification",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "another-token"


class TestCardAction:
    """Test Lark card action callbacks."""

    def test_refresh_dashboard_action(self):
        body = {
            "header": {"event_type": "card.action.trigger"},
            "event": {
                "action": {"value": {"action": "refresh_dashboard"}},
            },
        }
        with patch(
            "src.lark_webhook.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
        ) as mock_proc:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.return_value = mock_process
            resp = client.post("/webhook/lark", json=body)
        assert resp.status_code == 200
        assert resp.json()["toast"]["type"] == "success"

    def test_unknown_card_action_forwarded(self):
        body = {
            "header": {"event_type": "card.action.trigger"},
            "event": {
                "action": {"value": {"action": "some_other_action"}},
            },
        }
        with patch("src.lark_webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json.return_value = {"status": "ok"}
            mock_resp.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client
            resp = client.post("/webhook/lark", json=body)
        assert resp.status_code == 200

    def test_non_card_event_returns_ok(self):
        body = {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {},
        }
        resp = client.post("/webhook/lark", json=body)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestOAuthCallback:
    """Test Lark OAuth GET callback."""

    def test_no_code_returns_ok(self):
        resp = client.get("/webhook/lark")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestHealth:
    """Test health endpoint."""

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
