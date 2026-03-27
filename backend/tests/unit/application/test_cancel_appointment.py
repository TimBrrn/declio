"""Tests cancel_appointment use case with real calendar search."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from backend.src.application.use_cases.cancel_appointment import cancel_appointment
from backend.src.domain.entities.appointment import Appointment, AppointmentStatus
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot


def _make_appointment(
    patient_name: str = "Martin",
    appt_id: str = "evt-001",
) -> Appointment:
    return Appointment(
        id=appt_id,
        cabinet_id="cab-1",
        patient_contact=PatientContact(
            phone=PhoneNumber("0678901234"), name=patient_name
        ),
        time_slot=TimeSlot(
            start=datetime(2025, 1, 10, 14, 0),
            end=datetime(2025, 1, 10, 14, 30),
        ),
        status=AppointmentStatus.CONFIRMED,
    )


def _make_calendar(appointments: list[Appointment] | None = None):
    calendar = AsyncMock()
    calendar.find_appointments = AsyncMock(
        return_value=appointments if appointments is not None else []
    )
    calendar.cancel = AsyncMock(return_value=None)
    return calendar


class TestCancelAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_found_and_cancelled(self):
        appt = _make_appointment("Martin")
        calendar = _make_calendar([appt])

        result = await cancel_appointment(
            calendar=calendar,
            cabinet_id="cab-1",
            patient_name="Martin",
        )

        assert "annule" in result.lower()
        assert "Martin" in result
        calendar.cancel.assert_called_once_with("evt-001")

    @pytest.mark.asyncio
    async def test_not_found_returns_error_message(self):
        calendar = _make_calendar([])

        result = await cancel_appointment(
            calendar=calendar,
            cabinet_id="cab-1",
            patient_name="Inconnu",
        )

        assert "ne trouve pas" in result.lower()
        calendar.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancels_first_match_when_multiple(self):
        appt1 = _make_appointment("Martin", appt_id="evt-001")
        appt2 = _make_appointment("Martin", appt_id="evt-002")
        calendar = _make_calendar([appt1, appt2])

        result = await cancel_appointment(
            calendar=calendar,
            cabinet_id="cab-1",
            patient_name="Martin",
        )

        assert "annule" in result.lower()
        calendar.cancel.assert_called_once_with("evt-001")

    @pytest.mark.asyncio
    async def test_includes_date_in_response(self):
        appt = _make_appointment("Dupont")
        calendar = _make_calendar([appt])

        result = await cancel_appointment(
            calendar=calendar,
            cabinet_id="cab-1",
            patient_name="Dupont",
        )

        # Should mention the time
        assert "14h00" in result

    @pytest.mark.asyncio
    async def test_proposes_rebooking(self):
        appt = _make_appointment("Martin")
        calendar = _make_calendar([appt])

        result = await cancel_appointment(
            calendar=calendar,
            cabinet_id="cab-1",
            patient_name="Martin",
        )

        assert "creneau" in result.lower()

    @pytest.mark.asyncio
    async def test_calendar_cancel_exception_returns_fallback(self):
        appt = _make_appointment("Martin")
        calendar = AsyncMock()
        calendar.find_appointments = AsyncMock(return_value=[appt])
        calendar.cancel = AsyncMock(side_effect=RuntimeError("API error"))

        result = await cancel_appointment(
            calendar=calendar,
            cabinet_id="cab-1",
            patient_name="Martin",
        )

        assert "probleme technique" in result.lower()
        assert "rappelle" in result.lower()
