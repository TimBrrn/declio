"""Telnyx SMS adapter — implements NotificationPort."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import telnyx

if TYPE_CHECKING:
    from backend.src.domain.value_objects.phone_number import PhoneNumber

logger = logging.getLogger(__name__)


class TelnyxSMSAdapter:
    """NotificationPort implementation backed by Telnyx SMS API."""

    def __init__(self, api_key: str, from_number: str) -> None:
        self._api_key = api_key
        self._from_number = from_number

    async def send_sms(self, to: PhoneNumber, message: str) -> bool:
        """Send an SMS via Telnyx. Returns True on success."""
        telnyx.api_key = self._api_key

        try:
            await asyncio.to_thread(
                lambda: telnyx.Message.create(
                    from_=self._from_number,
                    to=to.to_international(),
                    text=message,
                )
            )
            logger.info("SMS sent to %s (%d chars)", to, len(message))
            return True
        except Exception:
            logger.error("Failed to send SMS to %s", to, exc_info=True)
            return False
