"""Tests value objects — pur Python, zero mock."""

from datetime import datetime

import pytest

from backend.src.domain.entities.call_record import ScenarioEnum
from backend.src.domain.value_objects.call_summary import CallSummary
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot


# ── PhoneNumber ──────────────────────────────────────────────


class TestPhoneNumber:
    def test_valid_06(self):
        p = PhoneNumber("0612345678")
        assert p.value == "0612345678"

    def test_valid_07(self):
        p = PhoneNumber("0712345678")
        assert p.value == "0712345678"

    def test_valid_international(self):
        p = PhoneNumber("+33612345678")
        assert p.value == "+33612345678"

    def test_valid_with_spaces(self):
        p = PhoneNumber("06 12 34 56 78")
        assert p.value == "0612345678"

    def test_valid_with_dots(self):
        p = PhoneNumber("06.12.34.56.78")
        assert p.value == "0612345678"

    def test_invalid_01(self):
        with pytest.raises(ValueError):
            PhoneNumber("0112345678")

    def test_invalid_short(self):
        with pytest.raises(ValueError):
            PhoneNumber("061234")

    def test_invalid_empty(self):
        with pytest.raises(ValueError):
            PhoneNumber("")

    def test_to_international(self):
        p = PhoneNumber("0612345678")
        assert p.to_international() == "+33612345678"

    def test_to_international_already(self):
        p = PhoneNumber("+33612345678")
        assert p.to_international() == "+33612345678"


# ── TimeSlot ─────────────────────────────────────────────────


class TestTimeSlot:
    def test_duration(self):
        slot = TimeSlot(
            start=datetime(2025, 1, 1, 9, 0),
            end=datetime(2025, 1, 1, 9, 30),
        )
        assert slot.duration_minutes == 30

    def test_invalid_end_before_start(self):
        with pytest.raises(ValueError):
            TimeSlot(
                start=datetime(2025, 1, 1, 10, 0),
                end=datetime(2025, 1, 1, 9, 0),
            )

    def test_overlaps_true(self):
        a = TimeSlot(
            start=datetime(2025, 1, 1, 9, 0),
            end=datetime(2025, 1, 1, 10, 0),
        )
        b = TimeSlot(
            start=datetime(2025, 1, 1, 9, 30),
            end=datetime(2025, 1, 1, 10, 30),
        )
        assert a.overlaps(b) is True

    def test_overlaps_false(self):
        a = TimeSlot(
            start=datetime(2025, 1, 1, 9, 0),
            end=datetime(2025, 1, 1, 10, 0),
        )
        b = TimeSlot(
            start=datetime(2025, 1, 1, 10, 0),
            end=datetime(2025, 1, 1, 11, 0),
        )
        assert a.overlaps(b) is False

    def test_overlaps_contained(self):
        a = TimeSlot(
            start=datetime(2025, 1, 1, 9, 0),
            end=datetime(2025, 1, 1, 12, 0),
        )
        b = TimeSlot(
            start=datetime(2025, 1, 1, 10, 0),
            end=datetime(2025, 1, 1, 11, 0),
        )
        assert a.overlaps(b) is True

    def test_frozen(self):
        slot = TimeSlot(
            start=datetime(2025, 1, 1, 9, 0),
            end=datetime(2025, 1, 1, 10, 0),
        )
        with pytest.raises(AttributeError):
            slot.start = datetime(2025, 1, 1, 8, 0)  # type: ignore[misc]


# ── CallSummary ──────────────────────────────────────────────


class TestCallSummary:
    def test_to_sms_text_with_name(self):
        s = CallSummary(
            patient_name="Dupont",
            patient_phone="0612345678",
            call_type=ScenarioEnum.BOOKING,
            action_taken="RDV confirme lundi 10h",
        )
        text = s.to_sms_text()
        assert "[Declio]" in text
        assert "Dupont" in text
        assert "0612345678" in text
        assert "RDV confirme lundi 10h" in text

    def test_to_sms_text_without_name(self):
        s = CallSummary(
            patient_name=None,
            patient_phone="0612345678",
            call_type=ScenarioEnum.FAQ,
            action_taken="Question tarifs",
        )
        text = s.to_sms_text()
        assert "Patient inconnu" in text

    def test_to_sms_text_urgent(self):
        s = CallSummary(
            patient_name="Martin",
            patient_phone="0712345678",
            call_type=ScenarioEnum.ERROR,
            action_taken="Erreur technique",
            is_urgent=True,
        )
        text = s.to_sms_text()
        assert "[URGENT]" in text
