"""InternalCalendarAdapter — implements CalendarPort against local DB.

Replaces GoogleCalendarAdapter. Queries AppointmentModel directly
instead of Google Calendar API. Slot computation from cabinet working hours.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlmodel import Session, select

from backend.src.domain.entities.appointment import (
    Appointment,
    AppointmentStatus,
)
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot
from backend.src.infrastructure.persistence.models import (
    AppointmentModel,
    CabinetModel,
    PatientModel,
)

logger = logging.getLogger(__name__)

# Default working hours (Mon-Fri 9-12, 14-18). Used if cabinet has no horaires.
_DEFAULT_WORKING_HOURS: dict[int, list[tuple[str, str]]] = {
    0: [("09:00", "12:00"), ("14:00", "18:00")],
    1: [("09:00", "12:00"), ("14:00", "18:00")],
    2: [("09:00", "12:00"), ("14:00", "18:00")],
    3: [("09:00", "12:00"), ("14:00", "18:00")],
    4: [("09:00", "12:00"), ("14:00", "18:00")],
}

# Map French day names to weekday index (0=Monday)
_DAY_NAME_TO_WEEKDAY: dict[str, int] = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}

SLOT_DURATION_MINUTES = 30


class InternalCalendarAdapter:
    """CalendarPort backed by local AppointmentModel in DB."""

    def __init__(self, session_factory) -> None:
        """Initialize with a session factory (callable returning Session).

        Args:
            session_factory: A callable that returns a SQLModel Session.
                             Typically a closure over the engine.
        """
        self._session_factory = session_factory

    def _get_session(self) -> Session:
        return self._session_factory()

    def _get_working_hours(self, cabinet_id: str) -> dict[int, list[tuple[str, str]]]:
        """Load working hours from cabinet config, or use defaults."""
        with self._get_session() as session:
            cabinet = session.get(CabinetModel, cabinet_id)
            if not cabinet:
                return _DEFAULT_WORKING_HOURS

            horaires = cabinet.horaires  # dict: {"lundi": ["09:00-12:00", "14:00-18:00"], ...}
            if not horaires:
                return _DEFAULT_WORKING_HOURS

            result: dict[int, list[tuple[str, str]]] = {}
            for day_name, periods in horaires.items():
                weekday = _DAY_NAME_TO_WEEKDAY.get(day_name.lower())
                if weekday is None:
                    continue
                parsed: list[tuple[str, str]] = []
                for period in periods:
                    if "-" in period:
                        start_str, end_str = period.split("-", 1)
                        parsed.append((start_str.strip(), end_str.strip()))
                if parsed:
                    result[weekday] = parsed
            return result or _DEFAULT_WORKING_HOURS

    async def get_available_slots(
        self,
        cabinet_id: str,
        start: datetime,
        end: datetime,
    ) -> list[TimeSlot]:
        working_hours = self._get_working_hours(cabinet_id)
        busy = self._get_busy_slots(cabinet_id, start, end)
        return self._compute_free_slots(start, end, busy, working_hours)

    async def book(
        self,
        cabinet_id: str,
        slot: TimeSlot,
        patient: PatientContact,
    ) -> Appointment:
        patient_name = patient.name or "Patient"
        phone_str = str(patient.phone) if patient.phone else ""

        with self._get_session() as session:
            # Auto-create patient if phone is provided
            patient_id = None
            if phone_str:
                existing = session.exec(
                    select(PatientModel)
                    .where(PatientModel.cabinet_id == cabinet_id)
                    .where(PatientModel.telephone == phone_str)
                ).first()
                if existing:
                    patient_id = existing.id
                    # Update name if we have a better one
                    if patient_name and patient_name != "Patient" and not existing.nom:
                        existing.nom = patient_name
                        session.add(existing)
                else:
                    new_patient = PatientModel(
                        cabinet_id=cabinet_id,
                        nom=patient_name,
                        telephone=phone_str,
                    )
                    session.add(new_patient)
                    session.flush()
                    patient_id = new_patient.id

            appt = AppointmentModel(
                cabinet_id=cabinet_id,
                patient_id=patient_id,
                patient_nom=patient_name,
                patient_telephone=phone_str,
                date_heure=slot.start,
                duree_minutes=slot.duration_minutes,
                status="confirmed",
                source="ai_call",
            )
            session.add(appt)
            session.commit()
            session.refresh(appt)

            logger.info("Appointment booked: %s for %s at %s", appt.id, patient_name, slot.start)

            return Appointment(
                id=appt.id,
                cabinet_id=cabinet_id,
                patient_contact=patient,
                time_slot=slot,
                status=AppointmentStatus.CONFIRMED,
            )

    async def cancel(self, appointment_id: str) -> None:
        with self._get_session() as session:
            appt = session.get(AppointmentModel, appointment_id)
            if not appt:
                logger.warning("Appointment %s not found for cancellation", appointment_id)
                return
            appt.status = "cancelled"
            session.add(appt)
            session.commit()
            logger.info("Appointment cancelled: %s", appointment_id)

    async def find_appointments(
        self,
        cabinet_id: str,
        patient_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Appointment]:
        with self._get_session() as session:
            statement = select(AppointmentModel).where(
                AppointmentModel.cabinet_id == cabinet_id,
                AppointmentModel.status == "confirmed",
            )
            if start:
                statement = statement.where(AppointmentModel.date_heure >= start)
            if end:
                statement = statement.where(AppointmentModel.date_heure <= end)
            if patient_name:
                escaped = patient_name.replace("%", "\\%").replace("_", "\\_")
                statement = statement.where(
                    AppointmentModel.patient_nom.ilike(f"%{escaped}%")
                )

            rows = session.exec(statement.order_by(AppointmentModel.date_heure.asc())).all()

            results: list[Appointment] = []
            for row in rows:
                slot_end = row.date_heure + timedelta(minutes=row.duree_minutes)
                results.append(
                    Appointment(
                        id=row.id,
                        cabinet_id=row.cabinet_id,
                        patient_contact=PatientContact(
                            phone=PhoneNumber(row.patient_telephone or "0600000000"),
                            name=row.patient_nom,
                        ),
                        time_slot=TimeSlot(start=row.date_heure, end=slot_end),
                        status=AppointmentStatus.CONFIRMED
                        if row.status == "confirmed"
                        else AppointmentStatus.CANCELLED,
                    )
                )
            return results

    # ── Private helpers ───────────────────────────────────────

    def _get_busy_slots(
        self, cabinet_id: str, start: datetime, end: datetime
    ) -> list[TimeSlot]:
        """Fetch confirmed appointments as busy TimeSlots."""
        with self._get_session() as session:
            rows = session.exec(
                select(AppointmentModel)
                .where(AppointmentModel.cabinet_id == cabinet_id)
                .where(AppointmentModel.status == "confirmed")
                .where(AppointmentModel.date_heure >= start)
                .where(
                    AppointmentModel.date_heure
                    <= end + timedelta(hours=1)
                )
            ).all()

            return [
                TimeSlot(
                    start=r.date_heure,
                    end=r.date_heure + timedelta(minutes=r.duree_minutes),
                )
                for r in rows
            ]

    def _compute_free_slots(
        self,
        start: datetime,
        end: datetime,
        busy: list[TimeSlot],
        working_hours: dict[int, list[tuple[str, str]]],
    ) -> list[TimeSlot]:
        """Compute free slots from working hours minus busy times."""
        free: list[TimeSlot] = []
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            weekday = current_date.weekday()
            work_periods = working_hours.get(weekday, [])

            for period_start_str, period_end_str in work_periods:
                ph, pm = map(int, period_start_str.split(":"))
                eh, em = map(int, period_end_str.split(":"))

                period_start = datetime(
                    current_date.year, current_date.month, current_date.day, ph, pm
                )
                period_end = datetime(
                    current_date.year, current_date.month, current_date.day, eh, em
                )

                slot_start = period_start
                while slot_start + timedelta(minutes=SLOT_DURATION_MINUTES) <= period_end:
                    slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                    candidate = TimeSlot(start=slot_start, end=slot_end)

                    is_free = not any(candidate.overlaps(b) for b in busy)
                    if is_free and slot_start >= start:
                        free.append(candidate)

                    slot_start = slot_end

            current_date += timedelta(days=1)

        return free
