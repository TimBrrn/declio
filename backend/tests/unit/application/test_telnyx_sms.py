"""Tests TelnyxSMSAdapter with mocked SDK."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.infrastructure.adapters.telnyx_sms import TelnyxSMSAdapter


def _make_adapter() -> TelnyxSMSAdapter:
    return TelnyxSMSAdapter(api_key="test-key", from_number="+33612345678")


class TestSendSMS:
    @pytest.mark.asyncio
    async def test_send_sms_success(self):
        adapter = _make_adapter()
        phone = PhoneNumber("0678901234")

        with patch("backend.src.infrastructure.adapters.telnyx_sms.telnyx") as mock_telnyx:
            mock_telnyx.Message.create = MagicMock(return_value=MagicMock())

            result = await adapter.send_sms(phone, "Test message")

        assert result is True
        mock_telnyx.Message.create.assert_called_once()
        call_kwargs = mock_telnyx.Message.create.call_args
        assert call_kwargs[1]["to"] == "+33678901234"
        assert call_kwargs[1]["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_send_sms_failure(self):
        adapter = _make_adapter()
        phone = PhoneNumber("0678901234")

        with patch("backend.src.infrastructure.adapters.telnyx_sms.telnyx") as mock_telnyx:
            mock_telnyx.Message.create = MagicMock(
                side_effect=Exception("API error")
            )

            result = await adapter.send_sms(phone, "Test message")

        assert result is False

    @pytest.mark.asyncio
    async def test_api_key_is_set(self):
        adapter = _make_adapter()
        phone = PhoneNumber("0678901234")

        with patch("backend.src.infrastructure.adapters.telnyx_sms.telnyx") as mock_telnyx:
            mock_telnyx.Message.create = MagicMock(return_value=MagicMock())

            await adapter.send_sms(phone, "Hello")

        assert mock_telnyx.api_key == "test-key"
