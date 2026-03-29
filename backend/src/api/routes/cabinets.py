from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.src.api.dependencies import get_db_session
from backend.src.api.middleware.auth import get_current_user
from backend.src.infrastructure.persistence.models import CabinetModel

router = APIRouter(prefix="/api/cabinets", tags=["cabinets"])


class CabinetCreate(BaseModel):
    nom_cabinet: str
    nom_praticien: str = ""
    adresse: str = ""
    telephone: str = ""
    horaires: dict[str, list[str]] = {}
    tarifs: dict[str, float] = {}
    google_calendar_id: str = ""
    numero_sms_kine: str = ""
    message_accueil: str = ""
    faq: dict[str, str] = {}


class CabinetUpdate(BaseModel):
    nom_cabinet: str | None = None
    nom_praticien: str | None = None
    adresse: str | None = None
    telephone: str | None = None
    horaires: dict[str, list[str]] | None = None
    tarifs: dict[str, float] | None = None
    google_calendar_id: str | None = None
    numero_sms_kine: str | None = None
    message_accueil: str | None = None
    faq: dict[str, str] | None = None


class CabinetResponse(BaseModel):
    id: str
    nom_cabinet: str
    nom_praticien: str
    adresse: str
    telephone: str
    horaires: dict[str, list[str]]
    tarifs: dict[str, float]
    google_calendar_id: str
    numero_sms_kine: str
    message_accueil: str
    faq: dict[str, str]

    model_config = {"from_attributes": True}


def _cabinet_to_response(cabinet: CabinetModel) -> dict:
    return cabinet.to_domain_dict()


@router.get("/current")
def get_current_cabinet(
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    """Return the first (and only for PoC) cabinet. 404 if none exists."""
    cabinet = session.exec(select(CabinetModel)).first()
    if not cabinet:
        raise HTTPException(status_code=404, detail="No cabinet configured")
    return _cabinet_to_response(cabinet)


@router.get("/")
def list_cabinets(
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    cabinets = session.exec(select(CabinetModel)).all()
    return [_cabinet_to_response(c) for c in cabinets]


@router.get("/{cabinet_id}")
def get_cabinet(
    cabinet_id: str,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    cabinet = session.get(CabinetModel, cabinet_id)
    if not cabinet:
        raise HTTPException(status_code=404, detail="Cabinet not found")
    return _cabinet_to_response(cabinet)


@router.post("/", status_code=201)
def create_cabinet(
    data: CabinetCreate,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    # Separate JSON fields from scalar fields
    dump = data.model_dump()
    horaires = dump.pop("horaires")
    tarifs = dump.pop("tarifs")
    faq = dump.pop("faq")

    cabinet = CabinetModel(**dump)
    cabinet.horaires = horaires
    cabinet.tarifs = tarifs
    cabinet.faq = faq

    session.add(cabinet)
    session.commit()
    session.refresh(cabinet)
    return _cabinet_to_response(cabinet)


@router.put("/{cabinet_id}")
def update_cabinet(
    cabinet_id: str,
    data: CabinetUpdate,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    cabinet = session.get(CabinetModel, cabinet_id)
    if not cabinet:
        raise HTTPException(status_code=404, detail="Cabinet not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle JSON-backed fields via their property setters
    for json_field in ("horaires", "tarifs", "faq"):
        if json_field in update_data:
            setattr(cabinet, json_field, update_data.pop(json_field))

    for key, value in update_data.items():
        setattr(cabinet, key, value)

    cabinet.updated_at = datetime.now(UTC)
    session.add(cabinet)
    session.commit()
    session.refresh(cabinet)
    return _cabinet_to_response(cabinet)
