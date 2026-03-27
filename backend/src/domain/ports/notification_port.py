from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.src.domain.value_objects.phone_number import PhoneNumber


class NotificationPort(Protocol):
    """Contrat notification SMS — implemente par Telnyx SMS adapter."""

    async def send_sms(self, to: PhoneNumber, message: str) -> bool:
        """Envoie un SMS. Retourne True si succes."""
        ...
