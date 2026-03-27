"""Google Calendar adapter — implements CalendarPort.

Falls back to stub mode when credentials are unavailable,
returning deterministic fake slots for local development.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from backend.src.domain.entities.appointment import Appointment, AppointmentStatus
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot

logger = logging.getLogger(__name__)

# Default working hours by weekday (0=Monday). Weekend = no slots.
_DEFAULT_WORKING_HOURS: dict[int, list[tuple[str, str]]] = {
    0: [("09:00", "12:00"), ("14:00", "18:00")],
    1: [("09:00", "12:00"), ("14:00", "18:00")],
    2: [("09:00", "12:00"), ("14:00", "18:00")],
    3: [("09:00", "12:00"), ("14:00", "18:00")],
    4: [("09:00", "12:00"), ("14:00", "18:00")],
}

SLOT_DURATION_MINUTES = 30


class GoogleCalendarAdapter:
    """CalendarPort implementation backed by Google Calendar API.

    When *service_account_file* or *calendar_id* are empty the adapter
    runs in **stub mode**: every write is a no-op log and reads return
    deterministic fake slots derived from ``_DEFAULT_WORKING_HOURS``.
    """

    def __init__(
        self,
        calendar_id: str = "",
        service_account_file: str = "",
        slot_duration_minutes: int = SLOT_DURATION_MINUTES,
    ) -> None:
        self._calendar_id = calendar_id
        self._slot_duration = slot_duration_minutes
        self._service: Any = None
        self._stub_mode = False

        if service_account_file and calendar_id:
            try:
                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build

                creds = Credentials.from_service_account_file(
                    service_account_file,
                    scopes=["https://www.googleapis.com/auth/calendar"],
                )
                self._service = build("calendar", "v3", credentials=creds)
                logger.info(
                    "Google Calendar adapter initialised (calendar=%s)", calendar_id
                )
            except Exception:
                logger.warning(
                    "Failed to initialise Google Calendar API — stub mode",
                    exc_info=True,
                )
                self._stub_mode = True
        else:
            logger.warning(
                "Google Calendar credentials not provided — running in stub mode"
            )
            self._stub_mode = True

    # ── CalendarPort implementation ───────────────────────────

    async def get_available_slots(
        self,
        cabinet_id: str,
        start: datetime,
        end: datetime,
    ) -> list[TimeSlot]:
        if self._stub_mode:
            return self._compute_free_slots(start, end, busy=[])

        events = await self._list_events(start, end)
        busy = self._parse_busy_times(events)
        return self._compute_free_slots(start, end, busy)

    async def book(
        self,
        cabinet_id: str,
        slot: TimeSlot,
        patient: PatientContact,
    ) -> Appointment:
        patient_name = patient.name or "Patient"
        event_summary = f"RDV Kiné - {patient_name}"

        if self._stub_mode:
            logger.info("STUB: Booking %s at %s", event_summary, slot.start)
            return Appointment(
                id=f"stub-{uuid.uuid4().hex[:8]}",
                cabinet_id=cabinet_id,
                patient_contact=patient,
                time_slot=slot,
                status=AppointmentStatus.CONFIRMED,
            )

        phone_str = str(patient.phone) if patient.phone else "Non renseigné"
        description_lines = [
            f"Patient : {patient_name}",
            f"Téléphone : {phone_str}",
            f"Type : Séance de kinésithérapie",
            f"Durée : 30 minutes",
            "",
            "— Réservé via Declio (assistant vocal)",
        ]

        event_body = {
            "summary": event_summary,
            "description": "\n".join(description_lines),
            "start": {
                "dateTime": slot.start.isoformat(),
                "timeZone": "Europe/Paris",
            },
            "end": {
                "dateTime": slot.end.isoformat(),
                "timeZone": "Europe/Paris",
            },
        }

        created = await asyncio.to_thread(
            lambda: self._service.events()
            .insert(calendarId=self._calendar_id, body=event_body)
            .execute()
        )
        logger.info("Event created: %s", created.get("id"))

        return Appointment(
            id=created["id"],
            cabinet_id=cabinet_id,
            patient_contact=patient,
            time_slot=slot,
            status=AppointmentStatus.CONFIRMED,
        )

    async def cancel(self, appointment_id: str) -> None:
        if self._stub_mode:
            logger.info("STUB: Cancelling event %s", appointment_id)
            return

        await asyncio.to_thread(
            lambda: self._service.events()
            .delete(calendarId=self._calendar_id, eventId=appointment_id)
            .execute()
        )
        logger.info("Event deleted: %s", appointment_id)

    async def find_appointments(
        self,
        cabinet_id: str,
        patient_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Appointment]:
        if self._stub_mode:
            logger.info("STUB: find_appointments patient=%s", patient_name)
            return []

        query_start = start or datetime.now()
        query_end = end or (query_start + timedelta(days=30))
        events = await self._list_events(query_start, query_end)

        results: list[Appointment] = []
        for event in events:
            summary = event.get("summary", "")
            if patient_name and patient_name.lower() not in summary.lower():
                continue

            evt_start = _parse_event_datetime(event.get("start", {}))
            evt_end = _parse_event_datetime(event.get("end", {}))
            if not evt_start or not evt_end:
                continue

            extracted_name = _extract_patient_name(summary)
            results.append(
                Appointment(
                    id=event["id"],
                    cabinet_id=cabinet_id,
                    patient_contact=PatientContact(
                        phone=PhoneNumber("0600000000"),
                        name=extracted_name,
                    ),
                    time_slot=TimeSlot(start=evt_start, end=evt_end),
                )
            )

        return results

    # ── Private helpers ───────────────────────────────────────

    async def _list_events(self, start: datetime, end: datetime) -> list[dict]:
        result = await asyncio.to_thread(
            lambda: self._service.events()
            .list(
                calendarId=self._calendar_id,
                timeMin=start.isoformat() + "Z",
                timeMax=end.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])

    def _parse_busy_times(self, events: list[dict]) -> list[TimeSlot]:
        busy: list[TimeSlot] = []
        for event in events:
            evt_start = _parse_event_datetime(event.get("start", {}))
            evt_end = _parse_event_datetime(event.get("end", {}))
            if evt_start and evt_end:
                busy.append(TimeSlot(start=evt_start, end=evt_end))
        return busy

    def _compute_free_slots(
        self,
        start: datetime,
        end: datetime,
        busy: list[TimeSlot],
    ) -> list[TimeSlot]:
        """Compute free slots from working hours minus busy times."""
        free: list[TimeSlot] = []
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            weekday = current_date.weekday()
            work_periods = _DEFAULT_WORKING_HOURS.get(weekday, [])

            for period_start_str, period_end_str in work_periods:
                ph, pm = map(int, period_start_str.split(":"))
                eh, em = map(int, period_end_str.split(":"))

                period_start = datetime(
                    current_date.year, current_date.month, current_date.day, ph, pm
                )
                period_end = datetime(
                    current_date.year, current_date.month, current_date.day, eh, em
                )

                slot_start = period_start
                while slot_start + timedelta(minutes=self._slot_duration) <= period_end:
                    slot_end = slot_start + timedelta(minutes=self._slot_duration)
                    candidate = TimeSlot(start=slot_start, end=slot_end)

                    is_free = not any(candidate.overlaps(b) for b in busy)
                    if is_free and slot_start >= start:
                        free.append(candidate)

                    slot_start = slot_end

            current_date += timedelta(days=1)

        return free


def _parse_event_datetime(dt_dict: dict) -> datetime | None:
    """Parse a Google Calendar event datetime dict."""
    raw = dt_dict.get("dateTime") or dt_dict.get("date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _extract_patient_name(summary: str) -> str | None:
    """Extract patient name from event summary 'RDV Kiné - PatientName'."""
    if " - " in summary:
        return summary.split(" - ", 1)[1].strip()
    return None
