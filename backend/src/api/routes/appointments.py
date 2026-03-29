from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.src.api.dependencies import get_db_session
from backend.src.api.middleware.auth import get_current_user
from backend.src.infrastructure.persistence.models import AppointmentModel

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class AppointmentCreate(BaseModel):
    cabinet_id: str
    patient_nom: str
    patient_telephone: str = ""
    date_heure: str  # ISO "2026-03-27T09:00:00"
    duree_minutes: int = 30
    status: str = "confirmed"
    repeat_weeks: int = 1  # 1 = single, 2+ = recurrence


class AppointmentUpdate(BaseModel):
    patient_nom: str | None = None
    patient_telephone: str | None = None
    date_heure: str | None = None
    duree_minutes: int | None = None
    status: str | None = None


@router.get("/")
def list_appointments(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    status: str | None = Query(default=None),
    cabinet_id: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    statement = select(AppointmentModel)
    if cabinet_id:
        statement = statement.where(AppointmentModel.cabinet_id == cabinet_id)
    if status:
        statement = statement.where(AppointmentModel.status == status)
    if date_from:
        dt_from = datetime.fromisoformat(date_from)
        statement = statement.where(AppointmentModel.date_heure >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to)
        statement = statement.where(AppointmentModel.date_heure <= dt_to)
    statement = statement.order_by(AppointmentModel.date_heure.asc())
    appointments = session.exec(statement).all()
    return appointments


@router.post("/", status_code=201)
def create_appointment(
    data: AppointmentCreate,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    created = []
    weeks = max(1, min(data.repeat_weeks, 52))
    base_dt = datetime.fromisoformat(data.date_heure)
    for i in range(weeks):
        appt = AppointmentModel(
            cabinet_id=data.cabinet_id,
            patient_nom=data.patient_nom,
            patient_telephone=data.patient_telephone,
            date_heure=base_dt + timedelta(weeks=i),
            duree_minutes=data.duree_minutes,
            status=data.status,
        )
        session.add(appt)
        created.append(appt)
    session.commit()
    for appt in created:
        session.refresh(appt)
    return created


@router.put("/{appointment_id}")
def update_appointment(
    appointment_id: str,
    data: AppointmentUpdate,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    appt = session.get(AppointmentModel, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    update_data = data.model_dump(exclude_unset=True)
    if "date_heure" in update_data:
        update_data["date_heure"] = datetime.fromisoformat(update_data["date_heure"])
    for key, value in update_data.items():
        setattr(appt, key, value)
    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


@router.delete("/{appointment_id}", status_code=204)
def delete_appointment(
    appointment_id: str,
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    appt = session.get(AppointmentModel, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    session.delete(appt)
    session.commit()
