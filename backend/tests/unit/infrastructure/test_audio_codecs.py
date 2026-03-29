"""Tests for audio codec conversions (PCM ↔ G.711 μ-law)."""

import struct

from backend.src.infrastructure.audio.audio_codecs import (
    pcm24k_to_ulaw8k,
    ulaw8k_to_pcm16k,
    ulaw8k_to_pcm8k,
)


# ── pcm24k_to_ulaw8k (existing tests, updated import) ───────


class TestPcmToUlaw:
    def test_empty_input(self):
        assert pcm24k_to_ulaw8k(b"") == b""

    def test_single_byte_ignored(self):
        """Odd byte count: last byte is dropped (incomplete sample)."""
        assert pcm24k_to_ulaw8k(b"\x00") == b""

    def test_silence(self):
        """Zero samples → ulaw silence (0xFF)."""
        pcm = struct.pack("<3h", 0, 0, 0)
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 1
        assert result[0] == 0xFF  # μ-law silence

    def test_downsample_ratio(self):
        """24kHz → 8kHz: 3:1 downsample ratio."""
        pcm = struct.pack("<30h", *range(30))
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 10

    def test_output_is_bytes(self):
        pcm = struct.pack("<6h", 1000, 2000, 3000, 4000, 5000, 6000)
        result = pcm24k_to_ulaw8k(pcm)
        assert isinstance(result, bytes)
        assert len(result) == 2

    def test_loud_signal(self):
        """Max positive → valid ulaw byte (not silence)."""
        pcm = struct.pack("<3h", 32767, 0, 0)
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 1
        assert result[0] != 0xFF

    def test_negative_signal(self):
        """Negative samples produce different output from positive."""
        pcm_neg = struct.pack("<3h", -16000, 0, 0)
        pcm_pos = struct.pack("<3h", 16000, 0, 0)
        assert pcm24k_to_ulaw8k(pcm_neg) != pcm24k_to_ulaw8k(pcm_pos)

    def test_realistic_chunk_size(self):
        """4800 bytes (standard chunk) → 800 ulaw bytes."""
        pcm = b"\x00" * 4800
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 800


# ── ulaw8k_to_pcm16k (new: decode + 2x upsample) ───────────


class TestUlawToPcm16k:
    def test_empty_input(self):
        assert ulaw8k_to_pcm16k(b"") == b""

    def test_silence_byte(self):
        """μ-law silence (0xFF) → near-zero PCM sample, duplicated 2x."""
        result = ulaw8k_to_pcm16k(bytes([0xFF]))
        assert len(result) == 4  # 1 ulaw → 2 PCM samples × 2 bytes
        samples = struct.unpack("<2h", result)
        assert samples[0] == samples[1]  # duplicated
        assert abs(samples[0]) < 10  # near silence

    def test_upsample_ratio(self):
        """8kHz → 16kHz: 1:2 upsample ratio."""
        ulaw = bytes([0xFF] * 100)
        result = ulaw8k_to_pcm16k(ulaw)
        # 100 ulaw bytes → 200 PCM samples → 400 bytes
        assert len(result) == 400

    def test_non_silence(self):
        """Non-silence μ-law byte decodes to non-zero PCM."""
        result = ulaw8k_to_pcm16k(bytes([0x00]))
        samples = struct.unpack("<2h", result)
        assert abs(samples[0]) > 100  # clearly not silence

    def test_output_is_little_endian_16bit(self):
        """Output format is 16-bit signed little-endian."""
        ulaw = bytes([0x80, 0xFF, 0x00])
        result = ulaw8k_to_pcm16k(ulaw)
        assert len(result) == 12  # 3 × 2 samples × 2 bytes
        # Should be parseable as signed shorts
        samples = struct.unpack(f"<{len(result)//2}h", result)
        assert len(samples) == 6


# ── ulaw8k_to_pcm8k (decode, no resampling) ─────────────────


class TestUlawToPcm8k:
    def test_empty_input(self):
        assert ulaw8k_to_pcm8k(b"") == b""

    def test_no_upsample(self):
        """8kHz → 8kHz: 1:1 ratio (no duplication)."""
        ulaw = bytes([0xFF] * 100)
        result = ulaw8k_to_pcm8k(ulaw)
        # 100 ulaw bytes → 100 PCM samples → 200 bytes
        assert len(result) == 200

    def test_silence_byte(self):
        """μ-law silence → near-zero PCM."""
        result = ulaw8k_to_pcm8k(bytes([0xFF]))
        sample = struct.unpack("<h", result)[0]
        assert abs(sample) < 10


# ── Round-trip fidelity ──────────────────────────────────────


class TestRoundTrip:
    def test_encode_decode_preserves_shape(self):
        """PCM → ulaw → PCM should roughly preserve signal shape.

        Note: ulaw is lossy (8-bit → 16-bit), so exact values differ,
        but the sign and relative magnitude should be preserved.
        """
        # Create a signal with a few known values at 24kHz
        # After 3:1 downsample, only every 3rd sample survives
        original_samples = [0, 0, 0, 8000, 0, 0, -8000, 0, 0]
        pcm_24k = struct.pack(f"<{len(original_samples)}h", *original_samples)

        # Encode to ulaw (3:1 downsample → 3 ulaw bytes)
        ulaw = pcm24k_to_ulaw8k(pcm_24k)
        assert len(ulaw) == 3

        # Decode back to PCM 8k (no upsample — match ulaw sample count)
        pcm_back = ulaw8k_to_pcm8k(ulaw)
        decoded = struct.unpack(f"<{len(ulaw)}h", pcm_back)

        # Check sign/shape: silence, positive, negative
        assert abs(decoded[0]) < 100  # near silence
        assert decoded[1] > 1000  # positive signal
        assert decoded[2] < -1000  # negative signal
