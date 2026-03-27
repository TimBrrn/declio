from __future__ import annotations

from typing import AsyncIterator, Protocol


class STTPort(Protocol):
    """Contrat speech-to-text — implemente par Deepgram adapter."""

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[tuple[str, float]]:
        """Yield (texte, confidence_score) au fur et a mesure."""
        ...
