"""Tests for API usage persistence and usage endpoints."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.src.infrastructure.persistence.models import (
    ApiUsageModel,
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

    def _override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_cabinet(engine) -> str:
    with Session(engine) as session:
        cabinet = CabinetModel(nom_cabinet="Test Cab")
        session.add(cabinet)
        session.commit()
        session.refresh(cabinet)
        return cabinet.id


def _seed_call_with_usage(engine, cabinet_id: str) -> str:
    """Create a call record with cost data and api_usage rows. Return call id."""
    with Session(engine) as session:
        call = CallRecordModel(
            cabinet_id=cabinet_id,
            caller_number="+33612345678",
            started_at=datetime(2026, 3, 25, 10, 0),
            duration_seconds=120,
            scenario="booking",
            total_cost_usd=0.186,
            total_cost_eur=0.171,
            llm_cost_usd=0.027,
            stt_cost_usd=0.0086,
            tts_cost_usd=0.15,
            tts_chars_total=500,
            total_prompt_tokens=6000,
            total_completion_tokens=1200,
            total_tokens=7200,
        )
        session.add(call)
        session.flush()

        # LLM turns
        session.add(ApiUsageModel(
            call_record_id=call.id,
            service="llm",
            turn_index=0,
            prompt_tokens=3000,
            completion_tokens=600,
            total_tokens=3600,
            cost_usd=0.0135,
            model="gpt-4o",
            tool_name="get_available_slots",
        ))
        session.add(ApiUsageModel(
            call_record_id=call.id,
            service="llm",
            turn_index=1,
            prompt_tokens=3000,
            completion_tokens=600,
            total_tokens=3600,
            cost_usd=0.0135,
            model="gpt-4o",
        ))

        # STT
        session.add(ApiUsageModel(
            call_record_id=call.id,
            service="stt",
            turn_index=0,
            cost_usd=0.0086,
            model="nova-2",
            duration_seconds=120.0,
        ))

        # TTS
        session.add(ApiUsageModel(
            call_record_id=call.id,
            service="tts",
            turn_index=0,
            cost_usd=0.15,
            model="eleven_multilingual_v2",
            chars=500,
        ))

        session.commit()
        session.refresh(call)
        return call.id


# ── GET /api/usage/summary ──────────────────────────────────


class TestUsageSummary:
    def test_empty_db_returns_zeros(self, client, test_engine):
        resp = client.get("/api/usage/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 0
        assert data["total_cost_eur"] == 0.0
        assert data["avg_cost_per_call_eur"] == 0.0

    def test_summary_with_data(self, client, test_engine):
        cab_id = _seed_cabinet(test_engine)
        _seed_call_with_usage(test_engine, cab_id)

        resp = client.get("/api/usage/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 1
        assert data["total_cost_eur"] > 0
        assert data["llm_cost_total_eur"] > 0
        assert data["stt_cost_total_eur"] > 0
        assert data["tts_cost_total_eur"] > 0
        assert data["total_tokens"] == 7200

    def test_summary_date_filter_excludes(self, client, test_engine):
        cab_id = _seed_cabinet(test_engine)
        _seed_call_with_usage(test_engine, cab_id)

        # Filter to a date range that excludes the call
        resp = client.get("/api/usage/summary?date_from=2026-04-01&date_to=2026-04-30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 0

    def test_summary_date_filter_includes(self, client, test_engine):
        cab_id = _seed_cabinet(test_engine)
        _seed_call_with_usage(test_engine, cab_id)

        resp = client.get("/api/usage/summary?date_from=2026-03-20&date_to=2026-03-30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 1


# ── GET /api/calls/{id}/usage ───────────────────────────────


class TestCallUsage:
    def test_call_usage_returns_rows(self, client, test_engine):
        cab_id = _seed_cabinet(test_engine)
        call_id = _seed_call_with_usage(test_engine, cab_id)

        resp = client.get(f"/api/calls/{call_id}/usage")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 4  # 2 LLM + 1 STT + 1 TTS

        services = [r["service"] for r in rows]
        assert "llm" in services
        assert "stt" in services
        assert "tts" in services

    def test_call_usage_unknown_id_returns_empty(self, client, test_engine):
        resp = client.get("/api/calls/nonexistent-id/usage")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_call_usage_ordered_by_service_and_turn(self, client, test_engine):
        cab_id = _seed_cabinet(test_engine)
        call_id = _seed_call_with_usage(test_engine, cab_id)

        resp = client.get(f"/api/calls/{call_id}/usage")
        rows = resp.json()
        # Should be ordered: llm (turn 0, 1), stt (turn 0), tts (turn 0)
        llm_rows = [r for r in rows if r["service"] == "llm"]
        assert llm_rows[0]["turn_index"] == 0
        assert llm_rows[1]["turn_index"] == 1


# ── ApiUsageModel persistence ───────────────────────────────


class TestApiUsagePersistence:
    def test_llm_rows_have_tokens(self, test_engine):
        cab_id = _seed_cabinet(test_engine)
        call_id = _seed_call_with_usage(test_engine, cab_id)

        with Session(test_engine) as session:
            from sqlmodel import select
            rows = session.exec(
                select(ApiUsageModel)
                .where(ApiUsageModel.call_record_id == call_id)
                .where(ApiUsageModel.service == "llm")
            ).all()
            assert len(rows) == 2
            assert all(r.total_tokens > 0 for r in rows)

    def test_stt_row_has_duration(self, test_engine):
        cab_id = _seed_cabinet(test_engine)
        call_id = _seed_call_with_usage(test_engine, cab_id)

        with Session(test_engine) as session:
            from sqlmodel import select
            rows = session.exec(
                select(ApiUsageModel)
                .where(ApiUsageModel.call_record_id == call_id)
                .where(ApiUsageModel.service == "stt")
            ).all()
            assert len(rows) == 1
            assert rows[0].duration_seconds == 120.0

    def test_tts_row_has_chars(self, test_engine):
        cab_id = _seed_cabinet(test_engine)
        call_id = _seed_call_with_usage(test_engine, cab_id)

        with Session(test_engine) as session:
            from sqlmodel import select
            rows = session.exec(
                select(ApiUsageModel)
                .where(ApiUsageModel.call_record_id == call_id)
                .where(ApiUsageModel.service == "tts")
            ).all()
            assert len(rows) == 1
            assert rows[0].chars == 500

    def test_call_record_has_cost_fields(self, test_engine):
        cab_id = _seed_cabinet(test_engine)
        call_id = _seed_call_with_usage(test_engine, cab_id)

        with Session(test_engine) as session:
            from sqlmodel import select
            call = session.exec(
                select(CallRecordModel).where(CallRecordModel.id == call_id)
            ).one()
            assert call.total_cost_usd > 0
            assert call.total_cost_eur > 0
            assert call.llm_cost_usd > 0
            assert call.total_tokens == 7200

    def test_zero_turns_call(self, test_engine):
        """Call with 0 LLM turns should have 0 LLM cost."""
        cab_id = _seed_cabinet(test_engine)
        with Session(test_engine) as session:
            call = CallRecordModel(
                cabinet_id=cab_id,
                duration_seconds=5,
                scenario="error",
                total_cost_usd=0.0,
                total_cost_eur=0.0,
                llm_cost_usd=0.0,
                stt_cost_usd=0.0004,
                tts_cost_usd=0.0,
            )
            session.add(call)
            session.commit()
            session.refresh(call)
            assert call.total_tokens == 0
            assert call.llm_cost_usd == 0.0
