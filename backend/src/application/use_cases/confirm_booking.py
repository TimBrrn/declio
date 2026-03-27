"""Use case: confirm and book a specific slot chosen by the patient."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlmodel import Session

from backend.src.domain.services.appointment_scheduler import AppointmentScheduler
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.infrastructure.persistence.database import engine
from backend.src.infrastructure.persistence.models import AppointmentModel

if TYPE_CHECKING:
    from backend.src.domain.entities.cabinet import Cabinet
    from backend.src.domain.ports.calendar_port import CalendarPort

logger = logging.getLogger(__name__)

_scheduler = AppointmentScheduler()


async def confirm_booking(
    calendar: CalendarPort,
    cabinet: Cabinet,
    slot_index: int,
    patient_name: str,
    patient_phone: str | None = None,
) -> str:
    """Re-query available slots, pick the Nth, and book it.

    The re-query guarantees the slot is still free at confirmation time
    (avoids race conditions between proposal and confirmation).
    """
    logger.info(
        "confirm_booking: slot_index=%d patient=%s phone=%s",
        slot_index,
        patient_name,
        patient_phone,
    )

    start = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    end = start + timedelta(days=7)

    available = await calendar.get_available_slots(
        cabinet_id=cabinet.id,
        start=start,
        end=end,
    )
    best = _scheduler.propose_best_slots(available, max_proposals=3)
    logger.info("confirm_booking: re-queried %d available, %d best", len(available), len(best))

    if not best:
        return (
            "Desole, les creneaux ne sont plus disponibles. "
            "Souhaitez-vous que je cherche d'autres dates ?"
        )

    if slot_index < 1 or slot_index > len(best):
        return (
            f"Numero de creneau invalide. "
            f"Veuillez choisir entre 1 et {len(best)}."
        )

    slot = best[slot_index - 1]

    # Use caller's real phone if available, else placeholder
    phone = PhoneNumber(patient_phone) if patient_phone else PhoneNumber("0600000000")
    patient = PatientContact(
        phone=phone,
        name=patient_name,
    )

    try:
        appointment = await calendar.book(
            cabinet_id=cabinet.id,
            slot=slot,
            patient=patient,
        )
    except Exception:
        logger.exception(
            "Erreur lors de la reservation: patient=%s slot_index=%d slot=%s",
            patient_name,
            slot_index,
            slot.start,
        )
        return (
            "Desole, un probleme technique m'empeche de finaliser "
            "la reservation. Souhaitez-vous que je prenne vos coordonnees "
            "pour que le cabinet vous rappelle ?"
        )

    # Persist in local DB
    try:
        duration = int((slot.end - slot.start).total_seconds() / 60)
        with Session(engine) as session:
            db_appt = AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom=patient_name,
                patient_telephone=patient_phone or "",
                date_heure=slot.start,
                duree_minutes=duration,
                status="confirmed",
                google_event_id=appointment.id if appointment.id else "",
            )
            session.add(db_appt)
            session.commit()
    except Exception:
        logger.exception("Failed to persist appointment in local DB")

    day = slot.start.strftime("%A %d %B")
    hour = slot.start.strftime("%Hh%M")

    logger.info(
        "Booking confirmed: appointment=%s patient=%s slot=%s",
        appointment.id,
        patient_name,
        slot.start,
    )

    return (
        f"Parfait ! Votre rendez-vous est confirme le {day} a {hour}. "
        f"A bientot, {patient_name} !"
    )
