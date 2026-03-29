"""PCM 24kHz 16-bit → G.711 μ-law 8kHz converter.

Pure Python — replaces audioop (removed in Python 3.13).
Used to convert OpenAI TTS output to telephony format.
"""

from __future__ import annotations

import struct

# G.711 μ-law constants
_BIAS = 0x84
_CLIP = 32635


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
_ULAW_TABLE = bytes(_linear_to_ulaw(s) for s in range(-32768, 32768))


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
    # Ensure we have complete samples (2 bytes each)
    n_bytes = len(pcm_data) - (len(pcm_data) % 2)
    if n_bytes == 0:
        return b""

    # Decode all 16-bit samples
    n_samples = n_bytes // 2
    samples = struct.unpack(f"<{n_samples}h", pcm_data[:n_bytes])

    # Downsample 3:1 and convert via lookup table
    return bytes(
        _ULAW_TABLE[sample + 32768]
        for i, sample in enumerate(samples)
        if i % 3 == 0
    )
