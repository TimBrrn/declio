from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.src.api.dependencies import get_db_session
from backend.src.api.middleware.auth import get_current_user
from backend.src.infrastructure.persistence.models import PatientModel

router = APIRouter(prefix="/api/patients", tags=["patients"])


class PatientCreate(BaseModel):
    cabinet_id: str
    nom: str
    telephone: str = ""
    email: str = ""


class PatientUpdate(BaseModel):
    nom: str | None = None
    telephone: str | None = None
    email: str | None = None


@router.get("/")
def list_patients(
    cabinet_id: str | None = Query(default=None),
    telephone: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    statement = select(PatientModel)
    if cabinet_id:
        statement = statement.where(PatientModel.cabinet_id == cabinet_id)
    if telephone:
        statement = statement.where(PatientModel.telephone == telephone)
    statement = statement.order_by(PatientModel.nom.asc())
    return session.exec(statement).all()


@router.get("/{patient_id}")
def get_patient(
    patient_id: str,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    patient = session.get(PatientModel, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.post("/", status_code=201)
def create_patient(
    data: PatientCreate,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    patient = PatientModel(**data.model_dump())
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.put("/{patient_id}")
def update_patient(
    patient_id: str,
    data: PatientUpdate,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    patient = session.get(PatientModel, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=204)
def delete_patient(
    patient_id: str,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    patient = session.get(PatientModel, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    session.delete(patient)
    session.commit()
