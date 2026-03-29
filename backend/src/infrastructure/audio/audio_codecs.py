"""Audio codec conversions for telephony ↔ AI pipeline.

Pure Python — replaces audioop (removed in Python 3.13).

Conversions:
  - pcm24k_to_ulaw8k: TTS output (PCM 24kHz) → Telnyx (G.711 μ-law 8kHz)
  - ulaw8k_to_pcm16k: Telnyx (G.711 μ-law 8kHz) → STT input (PCM 16kHz)
"""

from __future__ import annotations

import struct

# ── G.711 μ-law constants ────────────────────────────────────

_BIAS = 0x84
_CLIP = 32635


# ── PCM → μ-law (encoding) ──────────────────────────────────


def _linear_to_ulaw(sample: int) -> int:
    """Convert one 16-bit signed linear PCM sample to 8-bit μ-law."""
    sign = 0
    if sample < 0:
        sign = 0x80
        sample = -sample
    if sample > _CLIP:
        sample = _CLIP
    sample += _BIAS

    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


# Pre-compute lookup table for speed (65536 entries, ~64KB)
_ULAW_ENCODE_TABLE = bytes(_linear_to_ulaw(s) for s in range(-32768, 32768))


def pcm24k_to_ulaw8k(pcm_data: bytes) -> bytes:
    """Convert PCM 24kHz 16-bit LE mono → G.711 μ-law 8kHz.

    Downsamples by factor 3 (24000 → 8000 Hz) via simple decimation.
    Suitable for telephony (G.711 PCMU codec).

    Args:
        pcm_data: Raw PCM bytes (little-endian, 16-bit signed, 24kHz mono).
                  Length should be divisible by 6 for clean sample boundaries.

    Returns:
        μ-law encoded bytes at 8kHz.
    """
    n_bytes = len(pcm_data) - (len(pcm_data) % 2)
    if n_bytes == 0:
        return b""

    n_samples = n_bytes // 2
    samples = struct.unpack(f"<{n_samples}h", pcm_data[:n_bytes])

    return bytes(
        _ULAW_ENCODE_TABLE[sample + 32768]
        for i, sample in enumerate(samples)
        if i % 3 == 0
    )


# ── μ-law → PCM (decoding) ──────────────────────────────────


def _ulaw_to_linear(ulaw_byte: int) -> int:
    """Convert one 8-bit μ-law sample to 16-bit signed linear PCM."""
    ulaw_byte = ~ulaw_byte & 0xFF
    sign = ulaw_byte & 0x80
    exponent = (ulaw_byte >> 4) & 0x07
    mantissa = ulaw_byte & 0x0F
    sample = ((mantissa << 3) + _BIAS) << exponent
    sample -= _BIAS
    return -sample if sign else sample


# Pre-compute decode lookup table (256 entries)
_ULAW_DECODE_TABLE = tuple(_ulaw_to_linear(b) for b in range(256))


def ulaw8k_to_pcm16k(ulaw_data: bytes) -> bytes:
    """Convert G.711 μ-law 8kHz → PCM 16kHz 16-bit LE mono.

    Upsamples by factor 2 (8000 → 16000 Hz) via sample duplication.
    Suitable for Voxtral STT input (accepts 8kHz+ PCM S16LE).

    Args:
        ulaw_data: μ-law encoded bytes at 8kHz (1 byte per sample).

    Returns:
        Raw PCM bytes (little-endian, 16-bit signed, 16kHz mono).
    """
    if not ulaw_data:
        return b""

    # Decode and upsample 2x (duplicate each sample)
    samples = []
    for b in ulaw_data:
        pcm = _ULAW_DECODE_TABLE[b]
        samples.append(pcm)
        samples.append(pcm)  # duplicate for 2x upsample

    return struct.pack(f"<{len(samples)}h", *samples)


def ulaw8k_to_pcm8k(ulaw_data: bytes) -> bytes:
    """Convert G.711 μ-law 8kHz → PCM 8kHz 16-bit LE mono (no resampling).

    Args:
        ulaw_data: μ-law encoded bytes at 8kHz (1 byte per sample).

    Returns:
        Raw PCM bytes (little-endian, 16-bit signed, 8kHz mono).
    """
    if not ulaw_data:
        return b""

    samples = [_ULAW_DECODE_TABLE[b] for b in ulaw_data]
    return struct.pack(f"<{len(samples)}h", *samples)
