from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.src.domain.value_objects.call_summary import CallSummary

if TYPE_CHECKING:
    from backend.src.domain.entities.call_record import CallRecord
    from backend.src.domain.ports.notification_port import NotificationPort
    from backend.src.domain.value_objects.phone_number import PhoneNumber

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 30


async def send_call_summary(
    notification: NotificationPort,
    kine_phone: PhoneNumber,
    call_record: CallRecord,
    patient_name: str | None = None,
) -> bool:
    """Construit le CallSummary et envoie le SMS au kine.

    Retry 1 fois apres 30s si echec (cf. spec gestion des erreurs).
    """
    summary = CallSummary(
        patient_name=patient_name,
        patient_phone=call_record.caller_phone,
        call_type=call_record.scenario,
        action_taken=call_record.summary or "Appel traite",
        is_urgent=False,
    )

    sms_text = summary.to_sms_text()

    # Premiere tentative
    success = await notification.send_sms(to=kine_phone, message=sms_text)
    if success:
        logger.info("SMS resume envoye au kine %s", kine_phone)
        return True

    # Retry apres 30s
    logger.warning("Echec envoi SMS, retry dans %ds...", RETRY_DELAY_SECONDS)
    await asyncio.sleep(RETRY_DELAY_SECONDS)

    success = await notification.send_sms(to=kine_phone, message=sms_text)
    if success:
        logger.info("SMS resume envoye au kine (retry) %s", kine_phone)
        return True

    logger.critical(
        "ECHEC DEFINITIF envoi SMS resume au kine %s — call_record=%s",
        kine_phone,
        call_record.id,
    )
    return False
