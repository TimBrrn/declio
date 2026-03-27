from __future__ import annotations

from typing import AsyncIterator, Protocol


class TTSPort(Protocol):
    """Contrat text-to-speech — implemente par ElevenLabs adapter."""

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Yield audio chunks au fur et a mesure de la synthese."""
        ...
