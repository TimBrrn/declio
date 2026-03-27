"""Tests for GET /api/cabinets/current endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
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
def client(test_engine):
    from backend.src.api.main import app
    from backend.src.api.dependencies import get_db_session

    def _override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestGetCurrentCabinet:
    def test_no_cabinet_returns_404(self, client):
        """GET /api/cabinets/current returns 404 when no cabinet exists."""
        response = client.get("/api/cabinets/current")
        assert response.status_code == 404
        assert "No cabinet configured" in response.json()["detail"]

    def test_returns_first_cabinet(self, client, test_engine):
        """GET /api/cabinets/current returns the first cabinet."""
        with Session(test_engine) as session:
            cabinet = CabinetModel(
                nom_cabinet="Cabinet Test",
                nom_praticien="Dr Test",
                adresse="1 rue Test",
                telephone="0612345678",
                google_calendar_id="cal@test.com",
                numero_sms_kine="0698765432",
                message_accueil="Bonjour, bienvenue !",
            )
            cabinet.horaires = {"lundi": ["09:00-12:00", "14:00-18:00"]}
            cabinet.tarifs = {"seance": 50.0}
            cabinet.faq = {"parking": "Parking gratuit devant le cabinet"}
            session.add(cabinet)
            session.commit()

        response = client.get("/api/cabinets/current")
        assert response.status_code == 200

        data = response.json()
        assert data["nom_cabinet"] == "Cabinet Test"
        assert data["nom_praticien"] == "Dr Test"
        assert data["adresse"] == "1 rue Test"
        assert data["telephone"] == "0612345678"
        assert data["horaires"] == {"lundi": ["09:00-12:00", "14:00-18:00"]}
        assert data["tarifs"] == {"seance": 50.0}
        assert data["faq"] == {"parking": "Parking gratuit devant le cabinet"}
        assert data["google_calendar_id"] == "cal@test.com"
        assert data["numero_sms_kine"] == "0698765432"
        assert data["message_accueil"] == "Bonjour, bienvenue !"

    def test_create_and_get_current(self, client):
        """POST a cabinet then GET /current returns it."""
        create_data = {
            "nom_cabinet": "Cabinet Cree",
            "nom_praticien": "Jean Cree",
            "adresse": "5 avenue Cree",
            "telephone": "0611223344",
            "horaires": {"mardi": ["10:00-17:00"]},
            "tarifs": {"seance": 45.0, "domicile": 55.0},
            "faq": {},
        }
        resp = client.post("/api/cabinets/", json=create_data)
        assert resp.status_code == 201

        current = client.get("/api/cabinets/current")
        assert current.status_code == 200
        assert current.json()["nom_cabinet"] == "Cabinet Cree"
        assert current.json()["tarifs"] == {"seance": 45.0, "domicile": 55.0}
