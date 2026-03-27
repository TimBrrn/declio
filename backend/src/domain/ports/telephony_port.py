from __future__ import annotations

from typing import AsyncIterator, Protocol


class TelephonyPort(Protocol):
    """Contrat telephonie — implemente par l'agent backend (Telnyx)."""

    async def answer_call(self, call_control_id: str) -> None: ...

    async def stream_audio(
        self, call_control_id: str
    ) -> AsyncIterator[bytes]: ...

    async def send_audio(
        self, call_control_id: str, audio_data: bytes
    ) -> None: ...

    async def hangup(self, call_control_id: str) -> None: ...
