from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.src.domain.value_objects.patient_contact import PatientContact
    from backend.src.domain.value_objects.time_slot import TimeSlot


class AppointmentStatus(Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class Appointment:
    """Rendez-vous dans un cabinet."""

    id: str
    cabinet_id: str
    patient_contact: PatientContact
    time_slot: TimeSlot
    status: AppointmentStatus = AppointmentStatus.CONFIRMED
    created_at: datetime = field(default_factory=datetime.now)
