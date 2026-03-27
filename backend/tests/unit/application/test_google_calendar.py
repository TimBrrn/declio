"""Tests GoogleCalendarAdapter — stub mode, slot computation, book/cancel."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot
from backend.src.infrastructure.adapters.google_calendar import (
    GoogleCalendarAdapter,
    _extract_patient_name,
    _parse_event_datetime,
)


def _make_adapter() -> GoogleCalendarAdapter:
    """Adapter in stub mode (no credentials)."""
    return GoogleCalendarAdapter()


# ── Stub mode ─────────────────────────────────────────────


class TestStubMode:
    def test_adapter_starts_in_stub_mode_without_credentials(self):
        adapter = _make_adapter()
        assert adapter._stub_mode is True

    @pytest.mark.asyncio
    async def test_get_available_slots_returns_slots_in_stub_mode(self):
        adapter = _make_adapter()
        # Next Monday
        start = datetime(2025, 1, 6, 0, 0)  # Monday
        end = datetime(2025, 1, 7, 23, 59)  # Tuesday end

        slots = await adapter.get_available_slots("cab-1", start, end)
        assert len(slots) > 0
        assert all(isinstance(s, TimeSlot) for s in slots)

    @pytest.mark.asyncio
    async def test_stub_slots_respect_working_hours(self):
        adapter = _make_adapter()
        # A single Monday
        start = datetime(2025, 1, 6, 0, 0)
        end = datetime(2025, 1, 6, 23, 59)

        slots = await adapter.get_available_slots("cab-1", start, end)

        for slot in slots:
            hour = slot.start.hour
            # Should be in 9-12 or 14-18
            assert (9 <= hour < 12) or (14 <= hour < 18), f"Unexpected hour: {hour}"

    @pytest.mark.asyncio
    async def test_stub_no_slots_on_weekend(self):
        adapter = _make_adapter()
        # Saturday + Sunday
        start = datetime(2025, 1, 4, 0, 0)  # Saturday
        end = datetime(2025, 1, 5, 23, 59)  # Sunday

        slots = await adapter.get_available_slots("cab-1", start, end)
        assert slots == []

    @pytest.mark.asyncio
    async def test_book_returns_appointment_in_stub_mode(self):
        adapter = _make_adapter()
        slot = TimeSlot(
            start=datetime(2025, 1, 6, 9, 0),
            end=datetime(2025, 1, 6, 9, 30),
        )
        patient = PatientContact(
            phone=PhoneNumber("0612345678"), name="Dupont"
        )

        appointment = await adapter.book("cab-1", slot, patient)

        assert appointment.id.startswith("stub-")
        assert appointment.patient_contact.name == "Dupont"
        assert appointment.time_slot == slot

    @pytest.mark.asyncio
    async def test_cancel_noop_in_stub_mode(self):
        adapter = _make_adapter()
        # Should not raise
        await adapter.cancel("stub-12345678")

    @pytest.mark.asyncio
    async def test_find_appointments_empty_in_stub_mode(self):
        adapter = _make_adapter()
        results = await adapter.find_appointments("cab-1", patient_name="X")
        assert results == []


# ── Slot computation ──────────────────────────────────────


class TestSlotComputation:
    def test_free_slots_minus_busy(self):
        adapter = _make_adapter()
        start = datetime(2025, 1, 6, 0, 0)  # Monday
        end = datetime(2025, 1, 6, 23, 59)

        # Block the 9:00-10:00 slot
        busy = [
            TimeSlot(
                start=datetime(2025, 1, 6, 9, 0),
                end=datetime(2025, 1, 6, 10, 0),
            )
        ]

        free = adapter._compute_free_slots(start, end, busy)

        # No slot should overlap with the busy period
        for slot in free:
            assert not slot.overlaps(busy[0]), f"Slot {slot.start} overlaps busy"

    def test_slot_duration_30_minutes(self):
        adapter = _make_adapter()
        start = datetime(2025, 1, 6, 0, 0)
        end = datetime(2025, 1, 6, 23, 59)

        free = adapter._compute_free_slots(start, end, busy=[])

        for slot in free:
            assert slot.duration_minutes == 30

    def test_custom_slot_duration(self):
        adapter = GoogleCalendarAdapter(slot_duration_minutes=45)
        start = datetime(2025, 1, 6, 0, 0)
        end = datetime(2025, 1, 6, 23, 59)

        free = adapter._compute_free_slots(start, end, busy=[])

        for slot in free:
            assert slot.duration_minutes == 45

    def test_multiple_busy_slots_reduce_availability(self):
        adapter = _make_adapter()
        start = datetime(2025, 1, 6, 0, 0)
        end = datetime(2025, 1, 6, 23, 59)

        all_free = adapter._compute_free_slots(start, end, busy=[])

        busy = [
            TimeSlot(start=datetime(2025, 1, 6, 9, 0), end=datetime(2025, 1, 6, 10, 0)),
            TimeSlot(start=datetime(2025, 1, 6, 14, 0), end=datetime(2025, 1, 6, 15, 0)),
        ]
        partial_free = adapter._compute_free_slots(start, end, busy)

        assert len(partial_free) < len(all_free)


# ── Helper functions ──────────────────────────────────────


class TestHelpers:
    def test_parse_event_datetime_iso(self):
        dt = _parse_event_datetime({"dateTime": "2025-01-06T09:00:00+01:00"})
        assert dt is not None
        assert dt.hour == 9  # after stripping tz, it's local interpretation
        assert dt.tzinfo is None

    def test_parse_event_datetime_zulu(self):
        dt = _parse_event_datetime({"dateTime": "2025-01-06T09:00:00Z"})
        assert dt is not None
        assert dt.tzinfo is None

    def test_parse_event_datetime_empty(self):
        assert _parse_event_datetime({}) is None

    def test_extract_patient_name_from_summary(self):
        assert _extract_patient_name("RDV Kiné - Dupont") == "Dupont"
        assert _extract_patient_name("RDV Kiné - Martin Jean") == "Martin Jean"

    def test_extract_patient_name_no_separator(self):
        assert _extract_patient_name("Reunion equipe") is None
