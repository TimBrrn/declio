from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from backend.src.domain.services.appointment_scheduler import AppointmentScheduler

if TYPE_CHECKING:
    from backend.src.domain.entities.cabinet import Cabinet
    from backend.src.domain.ports.calendar_port import CalendarPort

logger = logging.getLogger(__name__)

_scheduler = AppointmentScheduler()


async def get_available_slots(
    calendar: CalendarPort,
    cabinet: Cabinet,
    date_hint: str,
) -> str:
    """Consulte les creneaux disponibles sans reserver.

    Separee de book_appointment pour la clarte. En J3,
    book_appointment ajoutera confirm_booking() par-dessus.
    """
    logger.info("get_available_slots: date_hint=%r cabinet=%s", date_hint, cabinet.id)

    start = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    end = start + timedelta(days=7)

    available = await calendar.get_available_slots(
        cabinet_id=cabinet.id,
        start=start,
        end=end,
    )

    logger.info("get_available_slots: %d slots available", len(available))

    if not available:
        logger.warning("get_available_slots: no slots found for date_hint=%r", date_hint)
        return (
            "Je suis desole, je ne trouve aucun creneau disponible "
            "dans les 7 prochains jours. Souhaitez-vous que je prenne "
            "votre nom et numero pour que le cabinet vous rappelle ?"
        )

    best = _scheduler.propose_best_slots(available, max_proposals=3)
    logger.info("get_available_slots: proposing %d best slots", len(best))

    lines = ["Voici les creneaux disponibles :"]
    for i, slot in enumerate(best, 1):
        day = slot.start.strftime("%A %d %B")
        hour = slot.start.strftime("%Hh%M")
        lines.append(f"{i}. {day} a {hour}")

    lines.append("Lequel vous conviendrait ?")
    return "\n".join(lines)
