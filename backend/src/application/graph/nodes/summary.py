from __future__ import annotations

import logging

from backend.src.application.graph.state import CallState
from backend.src.application.use_cases.send_call_summary import send_call_summary
from backend.src.domain.ports.notification_port import NotificationPort
from backend.src.domain.value_objects.phone_number import PhoneNumber

logger = logging.getLogger(__name__)


async def summary_node(
    state: CallState,
    notification: NotificationPort,
) -> dict:
    """Construit le resume d'appel et l'envoie par SMS au kine."""
    cabinet = state["cabinet"]
    call_record = state.get("call_record")

    if call_record is None:
        logger.warning("Pas de call_record, skip summary SMS")
        return {}

    scenario = state.get("scenario")
    patient_name = state.get("patient_name")
    kine_phone = PhoneNumber(cabinet.numero_sms_kine)

    logger.info(
        "Summary node: scenario=%s patient_name=%s kine_phone=%s",
        scenario,
        patient_name,
        kine_phone,
    )

    success = await send_call_summary(
        notification=notification,
        kine_phone=kine_phone,
        call_record=call_record,
        patient_name=patient_name,
    )

    if success:
        logger.info("Summary SMS sent successfully")
    else:
        logger.error("Summary SMS failed after retries")

    return {}
