"""Tests for the auth middleware — Better Stack token validation.

NOTE: Auth is currently disabled on CRUD routes for PoC development.
The get_current_user dependency is tested in isolation below.
Route-level auth tests are skipped until auth is re-enabled.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from unittest.mock import patch

from backend.src.api.middleware.auth import get_current_user
from backend.src.infrastructure.config.settings import Settings

TEST_TOKEN = "test-betterstack-token"


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_engine):
    from backend.src.api.main import app
    from backend.src.api.dependencies import (
        get_db_session,
        get_conversation,
        get_calendar,
    )
    from unittest.mock import MagicMock

    def _override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_conversation] = lambda: MagicMock()
    app.dependency_overrides[get_calendar] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAuthMiddleware:
    @patch("backend.src.api.middleware.auth.settings")
    def test_get_current_user_no_credentials_raises(self, mock_settings):
        """get_current_user raises 401 when no credentials provided."""
        import asyncio
        from fastapi import HTTPException

        mock_settings.betterstack_api_token = TEST_TOKEN
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(get_current_user(None))
        assert exc_info.value.status_code == 401

    @patch("backend.src.api.middleware.auth.settings")
    def test_get_current_user_invalid_token_raises(self, mock_settings):
        """get_current_user raises 401 when token is wrong."""
        import asyncio
        from unittest.mock import MagicMock
        from fastapi import HTTPException

        mock_settings.betterstack_api_token = TEST_TOKEN
        creds = MagicMock()
        creds.credentials = "wrong-token"
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(get_current_user(creds))
        assert exc_info.value.status_code == 401

    @patch("backend.src.api.middleware.auth.settings")
    def test_get_current_user_valid_token_returns_dict(self, mock_settings):
        """get_current_user returns auth dict when token matches."""
        import asyncio
        from unittest.mock import MagicMock

        mock_settings.betterstack_api_token = TEST_TOKEN
        creds = MagicMock()
        creds.credentials = TEST_TOKEN
        result = asyncio.get_event_loop().run_until_complete(get_current_user(creds))
        assert result["authenticated"] is True

    def test_webhook_public_no_auth(self, client):
        """POST /webhooks/telnyx is public — no auth required."""
        resp = client.post(
            "/webhooks/telnyx",
            json={"data": {"event_type": "call.unknown", "payload": {}}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_public_no_auth(self, client):
        """GET /api/health is public — no auth required."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert "status" in resp.json()
