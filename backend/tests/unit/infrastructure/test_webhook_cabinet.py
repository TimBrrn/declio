"""Tests that the webhook converts cabinet DB model to domain Cabinet entity."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.domain.entities.cabinet import Cabinet
from backend.src.infrastructure.persistence.models import CabinetModel


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
def seeded_engine(test_engine):
    """Engine with a cabinet already inserted."""
    with Session(test_engine) as session:
        cabinet = CabinetModel(
            nom_cabinet="Cabinet Test",
            nom_praticien="Dr Dupont",
            adresse="10 rue Test",
            telephone="0612345678",
            google_calendar_id="cal@test.com",
            numero_sms_kine="0698765432",
            message_accueil="Bienvenue",
        )
        cabinet.horaires = {"lundi": ["09:00-12:00"]}
        cabinet.tarifs = {"seance_kine": 16.13}
        cabinet.faq = {"parking": "Gratuit"}
        session.add(cabinet)
        session.commit()
    return test_engine


def _mock_telephony():
    """Create a mock telephony adapter."""
    mock = MagicMock()
    mock.answer_call = AsyncMock()
    mock.start_audio_stream = AsyncMock()
    mock.end_audio = MagicMock()
    mock.get_send_queue = MagicMock()
    return mock


@pytest.fixture
def client(seeded_engine):
    from backend.src.api.main import app
    from backend.src.api.dependencies import get_db_session, get_telephony

    def _override_session():
        with Session(seeded_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_telephony] = _mock_telephony
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestWebhookCabinetEntity:
    @patch("backend.src.api.webhooks.telnyx_webhook._build_adapters")
    @patch("backend.src.api.webhooks.telnyx_webhook.AudioPipeline")
    def test_call_answered_passes_cabinet_entity(
        self, mock_pipeline_cls, mock_build_adapters, client
    ):
        """call.answered creates a Cabinet entity (not dict) in initial_state."""
        mock_build_adapters.return_value = (MagicMock(), MagicMock())

        mock_pipeline = MagicMock()
        mock_pipeline.start = AsyncMock()
        mock_pipeline_cls.return_value = mock_pipeline

        # First simulate call.initiated to register caller
        client.post(
            "/webhooks/telnyx",
            json={
                "data": {
                    "event_type": "call.initiated",
                    "payload": {
                        "call_control_id": "call-123",
                        "direction": "incoming",
                        "from": "+33612345678",
                    },
                }
            },
        )

        # Then simulate call.answered
        resp = client.post(
            "/webhooks/telnyx",
            json={
                "data": {
                    "event_type": "call.answered",
                    "payload": {"call_control_id": "call-123"},
                }
            },
        )
        assert resp.status_code == 200

        # Verify AudioPipeline was created with a Cabinet entity
        mock_pipeline_cls.assert_called_once()
        call_kwargs = mock_pipeline_cls.call_args
        initial_state = call_kwargs.kwargs.get(
            "initial_state", call_kwargs[1].get("initial_state")
        )
        cabinet = initial_state["cabinet"]
        assert isinstance(cabinet, Cabinet), (
            f"Expected Cabinet entity, got {type(cabinet).__name__}"
        )
        assert cabinet.nom_cabinet == "Cabinet Test"
        assert cabinet.nom_praticien == "Dr Dupont"
        assert cabinet.horaires == {"lundi": ["09:00-12:00"]}
        assert cabinet.tarifs == {"seance_kine": 16.13}

    @patch("backend.src.api.webhooks.telnyx_webhook._build_adapters")
    @patch("backend.src.api.webhooks.telnyx_webhook.AudioPipeline")
    def test_call_answered_no_cabinet_passes_none(
        self, mock_pipeline_cls, mock_build_adapters
    ):
        """call.answered with no cabinet in DB passes None."""
        # Use an empty DB (no seeded cabinet)
        empty_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(empty_engine)

        from backend.src.api.main import app
        from backend.src.api.dependencies import get_db_session, get_telephony

        def _override_session():
            with Session(empty_engine) as session:
                yield session

        app.dependency_overrides[get_db_session] = _override_session
        app.dependency_overrides[get_telephony] = _mock_telephony

        empty_client = TestClient(app)

        mock_build_adapters.return_value = (MagicMock(), MagicMock())

        mock_pipeline = MagicMock()
        mock_pipeline.start = AsyncMock()
        mock_pipeline_cls.return_value = mock_pipeline

        resp = empty_client.post(
            "/webhooks/telnyx",
            json={
                "data": {
                    "event_type": "call.answered",
                    "payload": {"call_control_id": "call-456"},
                }
            },
        )
        assert resp.status_code == 200

        call_kwargs = mock_pipeline_cls.call_args
        initial_state = call_kwargs.kwargs.get(
            "initial_state", call_kwargs[1].get("initial_state")
        )
        assert initial_state["cabinet"] is None

        app.dependency_overrides.clear()
