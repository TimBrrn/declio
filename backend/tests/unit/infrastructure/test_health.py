"""Tests for GET /api/health endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


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
    from backend.src.api.dependencies import get_db_session

    def _override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """GET /api/health returns 200 with services."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "services" in data
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_health_has_core_services(self, client):
        """Health response includes core services (database, telnyx, mistral)."""
        resp = client.get("/api/health")
        services = resp.json()["services"]
        assert "database" in services
        assert "telnyx" in services
        assert "mistral" in services

    def test_health_database_ok(self, client):
        """Database check works with in-memory test DB."""
        resp = client.get("/api/health")
        assert resp.json()["services"]["database"] == "ok"

    def test_health_no_auth_required(self, client):
        """Health endpoint is public — no auth token needed."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
