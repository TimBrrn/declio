"""Tests send_call_summary use case — SMS with retry logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.src.application.use_cases.send_call_summary import (
    RETRY_DELAY_SECONDS,
    send_call_summary,
)
from backend.src.domain.entities.call_record import CallRecord, ScenarioEnum
from backend.src.domain.value_objects.phone_number import PhoneNumber


def _make_call_record() -> CallRecord:
    return CallRecord(
        id="call-001",
        cabinet_id="cab-1",
        caller_phone="0678901234",
        scenario=ScenarioEnum.BOOKING,
        summary="RDV confirme lundi 10h",
    )


def _make_notification(results: list[bool]):
    """Mock notification port returning successive results."""
    notification = AsyncMock()
    notification.send_sms = AsyncMock(side_effect=results)
    return notification


class TestSendCallSummary:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        notification = _make_notification([True])
        phone = PhoneNumber("0612345678")

        result = await send_call_summary(notification, phone, _make_call_record())

        assert result is True
        assert notification.send_sms.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_first_failure(self):
        notification = _make_notification([False, True])
        phone = PhoneNumber("0612345678")

        with patch(
            "backend.src.application.use_cases.send_call_summary.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            result = await send_call_summary(notification, phone, _make_call_record())

        assert result is True
        assert notification.send_sms.call_count == 2
        mock_sleep.assert_called_once_with(RETRY_DELAY_SECONDS)

    @pytest.mark.asyncio
    async def test_failure_after_retry(self):
        notification = _make_notification([False, False])
        phone = PhoneNumber("0612345678")

        with patch(
            "backend.src.application.use_cases.send_call_summary.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await send_call_summary(notification, phone, _make_call_record())

        assert result is False
        assert notification.send_sms.call_count == 2

    @pytest.mark.asyncio
    async def test_sms_contains_patient_info(self):
        notification = _make_notification([True])
        phone = PhoneNumber("0612345678")

        await send_call_summary(notification, phone, _make_call_record())

        sms_text = notification.send_sms.call_args[1]["message"]
        assert "[Declio]" in sms_text
        assert "0678901234" in sms_text

    @pytest.mark.asyncio
    async def test_sms_contains_action(self):
        notification = _make_notification([True])
        phone = PhoneNumber("0612345678")

        await send_call_summary(notification, phone, _make_call_record())

        sms_text = notification.send_sms.call_args[1]["message"]
        assert "RDV confirme" in sms_text

    @pytest.mark.asyncio
    async def test_patient_name_included_in_sms(self):
        notification = _make_notification([True])
        phone = PhoneNumber("0612345678")

        await send_call_summary(
            notification, phone, _make_call_record(), patient_name="Dupont"
        )

        sms_text = notification.send_sms.call_args[1]["message"]
        assert "Dupont" in sms_text
        assert "Patient inconnu" not in sms_text

    @pytest.mark.asyncio
    async def test_no_patient_name_falls_back(self):
        notification = _make_notification([True])
        phone = PhoneNumber("0612345678")

        await send_call_summary(notification, phone, _make_call_record())

        sms_text = notification.send_sms.call_args[1]["message"]
        assert "Patient inconnu" in sms_text
