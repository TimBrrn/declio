"""Tests for call record persistence and GET /api/calls with filters."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.src.infrastructure.persistence.models import (
    CabinetModel,
    CallRecordModel,
)


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
    from backend.src.api.middleware.auth import get_current_user

    def _override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user] = lambda: {"authenticated": True}
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_cabinet(engine) -> str:
    """Create a cabinet and return its id."""
    with Session(engine) as session:
        cabinet = CabinetModel(nom_cabinet="Test Cab")
        session.add(cabinet)
        session.commit()
        session.refresh(cabinet)
        return cabinet.id


def _seed_calls(engine, cabinet_id: str) -> None:
    """Seed several call records for filter tests."""
    with Session(engine) as session:
        calls = [
            CallRecordModel(
                cabinet_id=cabinet_id,
                caller_number="+33612345678",
                started_at=datetime(2026, 3, 20, 10, 0),
                duration_seconds=45,
                scenario="booking",
                summary="RDV jeudi 14h",
                stt_confidence=0.92,
            ),
            CallRecordModel(
                cabinet_id=cabinet_id,
                caller_number="+33698765432",
                started_at=datetime(2026, 3, 22, 14, 30),
                duration_seconds=30,
                scenario="cancellation",
                summary="Annulation mardi",
                stt_confidence=0.85,
            ),
            CallRecordModel(
                cabinet_id=cabinet_id,
                caller_number="+33611111111",
                started_at=datetime(2026, 3, 25, 9, 0),
                duration_seconds=15,
                scenario="faq_tarifs",
                summary="Tarif seance",
                stt_confidence=0.78,
            ),
        ]
        for c in calls:
            session.add(c)
        session.commit()


class TestCallPersistence:
    def test_list_calls_empty(self, client):
        """GET /api/calls/ with no records returns empty list."""
        resp = client.get("/api/calls/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_calls_returns_records(self, client, test_engine):
        """GET /api/calls/ returns persisted call records."""
        cab_id = _seed_cabinet(test_engine)
        _seed_calls(test_engine, cab_id)

        resp = client.get("/api/calls/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Ordered by started_at desc
        assert data[0]["scenario"] == "faq_tarifs"
        assert data[1]["scenario"] == "cancellation"
        assert data[2]["scenario"] == "booking"

    def test_filter_by_scenario(self, client, test_engine):
        """Filter calls by scenario."""
        cab_id = _seed_cabinet(test_engine)
        _seed_calls(test_engine, cab_id)

        resp = client.get("/api/calls/?scenario=booking")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["scenario"] == "booking"

    def test_filter_by_date_from(self, client, test_engine):
        """Filter calls by date_from."""
        cab_id = _seed_cabinet(test_engine)
        _seed_calls(test_engine, cab_id)

        resp = client.get("/api/calls/?date_from=2026-03-22")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2  # 22 March + 25 March

    def test_filter_by_date_range(self, client, test_engine):
        """Filter calls by date_from + date_to."""
        cab_id = _seed_cabinet(test_engine)
        _seed_calls(test_engine, cab_id)

        resp = client.get("/api/calls/?date_from=2026-03-21&date_to=2026-03-23")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["scenario"] == "cancellation"

    def test_filter_by_cabinet_id(self, client, test_engine):
        """Filter calls by cabinet_id."""
        cab_id = _seed_cabinet(test_engine)
        _seed_calls(test_engine, cab_id)

        # Filter with the real cabinet id
        resp = client.get(f"/api/calls/?cabinet_id={cab_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

        # Filter with a non-existent cabinet id
        resp = client.get("/api/calls/?cabinet_id=nonexistent")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
