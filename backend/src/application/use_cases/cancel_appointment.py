"""Use case: cancel an existing appointment by patient name."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from backend.src.infrastructure.persistence.database import engine
from backend.src.infrastructure.persistence.models import AppointmentModel

if TYPE_CHECKING:
    from backend.src.domain.ports.calendar_port import CalendarPort

logger = logging.getLogger(__name__)


async def cancel_appointment(
    calendar: CalendarPort,
    cabinet_id: str,
    patient_name: str,
    date_hint: str | None = None,
) -> str:
    """Search calendar for matching appointment and cancel it.

    Searches the next 30 days for events matching ``patient_name``.
    If multiple matches exist, cancels the soonest one.
    """
    logger.info(
        "cancel_appointment: patient=%s date_hint=%s cabinet=%s",
        patient_name,
        date_hint,
        cabinet_id,
    )

    start = datetime.now()
    end = start + timedelta(days=30)

    appointments = await calendar.find_appointments(
        cabinet_id=cabinet_id,
        patient_name=patient_name,
        start=start,
        end=end,
    )

    logger.info("cancel_appointment: found %d appointments", len(appointments))

    if not appointments:
        logger.info(
            "No appointment found for patient=%s date_hint=%s",
            patient_name,
            date_hint,
        )
        return (
            f"Je ne trouve pas de rendez-vous pour {patient_name}. "
            "Pourriez-vous me donner plus de details "
            "(nom exact, date approximative) ?"
        )

    # Cancel the first (soonest) match
    appointment = appointments[0]
    try:
        await calendar.cancel(appointment.id)
    except Exception:
        logger.exception("Erreur lors de l'annulation du rendez-vous %s", appointment.id)
        return (
            "Desole, un probleme technique m'empeche d'annuler "
            "le rendez-vous. Souhaitez-vous que je prenne un message "
            "pour que le cabinet vous rappelle ?"
        )

    # Update status in local DB
    try:
        with Session(engine) as session:
            db_appt = session.exec(
                select(AppointmentModel).where(
                    AppointmentModel.google_event_id == appointment.id
                )
            ).first()
            if db_appt:
                db_appt.status = "cancelled"
                session.add(db_appt)
                session.commit()
    except Exception:
        logger.exception("Failed to update appointment status in local DB")

    day = appointment.time_slot.start.strftime("%A %d %B")
    hour = appointment.time_slot.start.strftime("%Hh%M")

    logger.info(
        "Cancelled appointment=%s patient=%s slot=%s",
        appointment.id,
        patient_name,
        appointment.time_slot.start,
    )

    return (
        f"Le rendez-vous de {patient_name} du {day} a {hour} est bien annule. "
        "Souhaitez-vous reprendre un autre creneau ?"
    )
