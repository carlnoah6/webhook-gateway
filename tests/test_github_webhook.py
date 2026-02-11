"""Tests for GitHub webhook handler."""
import hashlib
import hmac
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app)

SECRET = "test-webhook-secret-123"


def _sign(payload: bytes, secret: str = SECRET) -> str:
    """Create a valid HMAC-SHA256 signature."""
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _workflow_run_payload(
    conclusion: str = "success",
    workflow_name: str = "Deploy",
    repo: str = "carlnoah6/test-repo",
    branch: str = "main",
    action: str = "completed",
) -> dict:
    """Build a minimal workflow_run event payload."""
    return {
        "action": action,
        "workflow_run": {
            "name": workflow_name,
            "conclusion": conclusion,
            "html_url": f"https://github.com/{repo}/actions/runs/12345",
            "head_branch": branch,
            "head_commit": {"message": "feat: test commit"},
            "pull_requests": [],
            "repository": {"full_name": repo},
        },
    }


class TestSignatureVerification:
    """Test HMAC-SHA256 signature verification."""

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    @patch("src.github_webhook._save_event")
    def test_valid_signature_accepted(self, mock_save, mock_secret):
        payload = json.dumps(_workflow_run_payload()).encode()
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 200

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    def test_invalid_signature_rejected(self, mock_secret):
        payload = json.dumps(_workflow_run_payload()).encode()
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": "sha256=invalid",
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "Invalid signature"

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    def test_missing_signature_rejected(self, mock_secret):
        payload = json.dumps(_workflow_run_payload()).encode()
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 401

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    def test_wrong_secret_rejected(self, mock_secret):
        payload = json.dumps(_workflow_run_payload()).encode()
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload, "wrong-secret"),
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 401


class TestEventFiltering:
    """Test which events generate notifications."""

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    @patch("src.github_webhook._save_event")
    def test_deploy_success_saved(self, mock_save, mock_secret):
        payload = json.dumps(
            _workflow_run_payload(conclusion="success", workflow_name="Deploy")
        ).encode()
        client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        mock_save.assert_called_once()
        msg = mock_save.call_args[0][0]
        assert "Deploy Succeeded" in msg

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    @patch("src.github_webhook._save_event")
    def test_ci_success_skipped(self, mock_save, mock_secret):
        """Regular CI success should not generate a notification."""
        payload = json.dumps(
            _workflow_run_payload(conclusion="success", workflow_name="CI")
        ).encode()
        client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        mock_save.assert_not_called()

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    @patch("src.github_webhook._save_event")
    def test_failure_saved(self, mock_save, mock_secret):
        payload = json.dumps(
            _workflow_run_payload(conclusion="failure", workflow_name="CI")
        ).encode()
        client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        mock_save.assert_called_once()
        msg = mock_save.call_args[0][0]
        assert "Failure" in msg

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    @patch("src.github_webhook._save_event")
    def test_non_completed_action_ignored(self, mock_save, mock_secret):
        payload = json.dumps(
            _workflow_run_payload(action="requested")
        ).encode()
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "workflow_run",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 200
        mock_save.assert_not_called()

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    def test_ping_event(self, mock_secret):
        payload = b'{"zen": "test"}'
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "ping",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["msg"] == "pong"

    @patch("src.github_webhook._load_secret", return_value=SECRET)
    def test_non_workflow_event_ignored(self, mock_secret):
        payload = b'{"action": "opened"}'
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "x-hub-signature-256": _sign(payload),
                "x-github-event": "pull_request",
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert "ignored" in resp.json()["msg"]
