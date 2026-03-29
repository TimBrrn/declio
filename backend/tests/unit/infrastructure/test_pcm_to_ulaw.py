"""Tests for PCM 24kHz → G.711 μ-law 8kHz converter."""

import struct

from backend.src.infrastructure.audio.pcm_to_ulaw import pcm24k_to_ulaw8k


class TestPcmToUlaw:
    def test_empty_input(self):
        assert pcm24k_to_ulaw8k(b"") == b""

    def test_single_byte_ignored(self):
        """Odd byte count: last byte is dropped (incomplete sample)."""
        assert pcm24k_to_ulaw8k(b"\x00") == b""

    def test_silence(self):
        """Zero samples → ulaw silence (0xFF)."""
        # 6 bytes = 3 samples at 16-bit → 1 sample after 3:1 downsample
        pcm = struct.pack("<3h", 0, 0, 0)
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 1
        assert result[0] == 0xFF  # μ-law silence

    def test_downsample_ratio(self):
        """24kHz → 8kHz: 3:1 downsample ratio."""
        # 30 samples (60 bytes) → 10 output samples
        pcm = struct.pack("<30h", *range(30))
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 10

    def test_output_is_bytes(self):
        pcm = struct.pack("<6h", 1000, 2000, 3000, 4000, 5000, 6000)
        result = pcm24k_to_ulaw8k(pcm)
        assert isinstance(result, bytes)
        assert len(result) == 2  # 6 samples / 3 = 2

    def test_loud_signal(self):
        """Max positive → valid ulaw byte (not silence)."""
        pcm = struct.pack("<3h", 32767, 0, 0)
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 1
        assert result[0] != 0xFF  # not silence

    def test_negative_signal(self):
        """Negative samples produce different output from positive."""
        pcm_neg = struct.pack("<3h", -16000, 0, 0)
        pcm_pos = struct.pack("<3h", 16000, 0, 0)
        result_neg = pcm24k_to_ulaw8k(pcm_neg)
        result_pos = pcm24k_to_ulaw8k(pcm_pos)
        assert len(result_neg) == 1
        assert result_neg != result_pos  # different encoding for neg vs pos

    def test_realistic_chunk_size(self):
        """4800 bytes (standard chunk) → 800 ulaw bytes."""
        pcm = b"\x00" * 4800  # 2400 samples
        result = pcm24k_to_ulaw8k(pcm)
        assert len(result) == 800
