"""Tests confirm_booking use case."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from backend.src.application.use_cases.confirm_booking import confirm_booking
from backend.src.domain.entities.appointment import Appointment, AppointmentStatus
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot


def _make_cabinet() -> Cabinet:
    return Cabinet(
        id="cab-1",
        nom_cabinet="Kine Dupont",
        nom_praticien="Jean Dupont",
        adresse="12 rue de la Sante, 75013 Paris",
        telephone="0145678900",
        horaires={"lundi": ["09:00-12:00", "14:00-18:00"]},
        tarifs={"seance": 50.0},
        google_calendar_id="cal@group.calendar.google.com",
        numero_sms_kine="0612345678",
    )


def _make_slots(n: int = 3) -> list[TimeSlot]:
    base = datetime.now().replace(hour=9, minute=0, second=0) + timedelta(days=1)
    return [
        TimeSlot(start=base + timedelta(hours=i), end=base + timedelta(hours=i, minutes=30))
        for i in range(n)
    ]


def _make_calendar(slots: list[TimeSlot] | None = None):
    calendar = AsyncMock()
    calendar.get_available_slots = AsyncMock(
        return_value=slots if slots is not None else _make_slots()
    )
    calendar.book = AsyncMock(
        side_effect=lambda cabinet_id, slot, patient: Appointment(
            id="appt-123",
            cabinet_id=cabinet_id,
            patient_contact=patient,
            time_slot=slot,
            status=AppointmentStatus.CONFIRMED,
        )
    )
    return calendar


class TestConfirmBooking:
    @pytest.mark.asyncio
    async def test_happy_path_slot_1(self):
        calendar = _make_calendar()
        result = await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=1,
            patient_name="Martin",
        )

        assert "confirme" in result.lower()
        assert "Martin" in result
        calendar.book.assert_called_once()

    @pytest.mark.asyncio
    async def test_happy_path_slot_3(self):
        calendar = _make_calendar()
        result = await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=3,
            patient_name="Dupont",
        )

        assert "confirme" in result.lower()
        assert "Dupont" in result
        calendar.book.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_slot_index_too_high(self):
        calendar = _make_calendar()
        result = await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=5,
            patient_name="X",
        )

        assert "invalide" in result.lower()
        calendar.book.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_slot_index_zero(self):
        calendar = _make_calendar()
        result = await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=0,
            patient_name="X",
        )

        assert "invalide" in result.lower()
        calendar.book.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_slots_available(self):
        calendar = _make_calendar(slots=[])
        result = await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=1,
            patient_name="X",
        )

        assert "plus disponibles" in result.lower() or "desole" in result.lower()
        calendar.book.assert_not_called()

    @pytest.mark.asyncio
    async def test_books_correct_slot(self):
        slots = _make_slots(3)
        calendar = _make_calendar(slots=slots)

        await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=2,
            patient_name="Test",
        )

        # Verify the second slot was booked
        call_kwargs = calendar.book.call_args
        booked_slot = call_kwargs.kwargs.get("slot") or call_kwargs[1].get("slot")
        assert booked_slot == slots[1]

    @pytest.mark.asyncio
    async def test_uses_real_phone_when_provided(self):
        calendar = _make_calendar()
        await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=1,
            patient_name="Martin",
            patient_phone="0678901234",
        )

        call_kwargs = calendar.book.call_args
        patient = call_kwargs.kwargs.get("patient") or call_kwargs[1].get("patient")
        assert patient.phone.value == "0678901234"

    @pytest.mark.asyncio
    async def test_uses_placeholder_when_no_phone(self):
        calendar = _make_calendar()
        await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=1,
            patient_name="Martin",
        )

        call_kwargs = calendar.book.call_args
        patient = call_kwargs.kwargs.get("patient") or call_kwargs[1].get("patient")
        assert patient.phone.value == "0600000000"

    @pytest.mark.asyncio
    async def test_calendar_book_exception_returns_fallback(self):
        calendar = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=_make_slots())
        calendar.book = AsyncMock(side_effect=RuntimeError("API error"))

        result = await confirm_booking(
            calendar=calendar,
            cabinet=_make_cabinet(),
            slot_index=1,
            patient_name="Martin",
        )

        assert "probleme technique" in result.lower()
        assert "rappelle" in result.lower()
