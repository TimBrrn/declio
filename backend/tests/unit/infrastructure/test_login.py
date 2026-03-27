"""Tests for POST /api/auth/login endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from backend.src.api.main import app

    yield TestClient(app)


class TestLoginEndpoint:
    @patch("backend.src.api.routes.auth.settings")
    def test_valid_credentials_returns_200(self, mock_settings, client):
        """POST /api/auth/login with correct creds returns 200 + token."""
        mock_settings.admin_email = "admin@test.com"
        mock_settings.admin_password = "secret123"
        mock_settings.betterstack_api_token = "tok-abc"

        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "secret123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "tok-abc"
        assert data["email"] == "admin@test.com"
        assert data["name"] == "admin"

    @patch("backend.src.api.routes.auth.settings")
    def test_wrong_password_returns_401(self, mock_settings, client):
        """POST /api/auth/login with wrong password returns 401."""
        mock_settings.admin_email = "admin@test.com"
        mock_settings.admin_password = "secret123"

        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert "incorrect" in resp.json()["detail"]

    @patch("backend.src.api.routes.auth.settings")
    def test_wrong_email_returns_401(self, mock_settings, client):
        """POST /api/auth/login with wrong email returns 401."""
        mock_settings.admin_email = "admin@test.com"
        mock_settings.admin_password = "secret123"

        resp = client.post(
            "/api/auth/login",
            json={"email": "hacker@evil.com", "password": "secret123"},
        )
        assert resp.status_code == 401

    def test_login_is_public(self, client):
        """POST /api/auth/login does not require auth header."""
        resp = client.post(
            "/api/auth/login",
            json={"email": "anyone@test.com", "password": "any"},
        )
        # Should get 401 (wrong creds), NOT 403 (auth required)
        assert resp.status_code == 401
