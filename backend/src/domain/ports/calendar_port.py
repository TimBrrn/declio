from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.src.domain.entities.appointment import Appointment
    from backend.src.domain.value_objects.patient_contact import PatientContact
    from backend.src.domain.value_objects.time_slot import TimeSlot


class CalendarPort(Protocol):
    """Contrat agenda — implemente par Google Calendar adapter."""

    async def get_available_slots(
        self,
        cabinet_id: str,
        start: datetime,
        end: datetime,
    ) -> list[TimeSlot]: ...

    async def book(
        self,
        cabinet_id: str,
        slot: TimeSlot,
        patient: PatientContact,
    ) -> Appointment: ...

    async def cancel(self, appointment_id: str) -> None: ...

    async def find_appointments(
        self,
        cabinet_id: str,
        patient_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Appointment]: ...
