"""Tests for InternalCalendarAdapter — CalendarPort backed by local DB."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from backend.src.infrastructure.adapters.internal_calendar import (
    InternalCalendarAdapter,
    SLOT_DURATION_MINUTES,
)
from backend.src.infrastructure.persistence.models import (
    AppointmentModel,
    CabinetModel,
    PatientModel,
)
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot
from backend.src.domain.entities.appointment import AppointmentStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """In-memory SQLite with StaticPool for shared state across sessions."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    """Returns a callable that yields Session instances."""
    def _factory():
        return Session(engine)
    return _factory


@pytest.fixture
def adapter(session_factory):
    return InternalCalendarAdapter(session_factory)


@pytest.fixture
def cabinet(session_factory) -> CabinetModel:
    """Create a test cabinet with Mon-Fri 9-12, 14-18 + Sat 9-12."""
    with session_factory() as session:
        cab = CabinetModel(
            id="cab-001",
            nom_cabinet="Cabinet Test",
            nom_praticien="Dr Test",
        )
        cab.horaires = {
            "lundi": ["09:00-12:00", "14:00-18:00"],
            "mardi": ["09:00-12:00", "14:00-18:00"],
            "mercredi": ["09:00-12:00", "14:00-18:00"],
            "jeudi": ["09:00-12:00", "14:00-18:00"],
            "vendredi": ["09:00-12:00", "14:00-18:00"],
            "samedi": ["09:00-12:00"],
        }
        session.add(cab)
        session.commit()
        session.refresh(cab)
        return cab


# ── get_available_slots ───────────────────────────────────────────────────────

class TestGetAvailableSlots:

    @pytest.mark.asyncio
    async def test_returns_slots_for_working_day(self, adapter, cabinet):
        """Monday should have slots from 9-12 and 14-18."""
        # Monday 2026-03-30
        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 30, 23, 59)

        slots = await adapter.get_available_slots(cabinet.id, start, end)
        assert len(slots) > 0
        # 6 half-hours in 9-12 + 8 half-hours in 14-18 = 14 slots
        assert len(slots) == 14

    @pytest.mark.asyncio
    async def test_no_slots_on_sunday(self, adapter, cabinet):
        """Sunday should have no slots (not in horaires)."""
        # Sunday 2026-03-29
        start = datetime(2026, 3, 29, 0, 0)
        end = datetime(2026, 3, 29, 23, 59)

        slots = await adapter.get_available_slots(cabinet.id, start, end)
        assert len(slots) == 0

    @pytest.mark.asyncio
    async def test_saturday_half_day(self, adapter, cabinet):
        """Saturday should have slots only in the morning."""
        # Saturday 2026-04-04
        start = datetime(2026, 4, 4, 0, 0)
        end = datetime(2026, 4, 4, 23, 59)

        slots = await adapter.get_available_slots(cabinet.id, start, end)
        # 6 half-hours in 9-12
        assert len(slots) == 6

    @pytest.mark.asyncio
    async def test_busy_slot_excluded(self, adapter, cabinet, session_factory):
        """A confirmed appointment blocks its timeslot."""
        # Book 10:00-10:30 on Monday
        with session_factory() as session:
            appt = AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Existing Patient",
                date_heure=datetime(2026, 3, 30, 10, 0),
                duree_minutes=30,
                status="confirmed",
            )
            session.add(appt)
            session.commit()

        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 30, 23, 59)
        slots = await adapter.get_available_slots(cabinet.id, start, end)
        # 14 - 1 = 13
        assert len(slots) == 13
        # Check 10:00 is not in the slots
        slot_starts = [s.start.hour * 60 + s.start.minute for s in slots]
        assert 10 * 60 not in slot_starts

    @pytest.mark.asyncio
    async def test_cancelled_appointment_not_blocking(self, adapter, cabinet, session_factory):
        """Cancelled appointments should not block slots."""
        with session_factory() as session:
            appt = AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Cancelled Patient",
                date_heure=datetime(2026, 3, 30, 10, 0),
                duree_minutes=30,
                status="cancelled",
            )
            session.add(appt)
            session.commit()

        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 30, 23, 59)
        slots = await adapter.get_available_slots(cabinet.id, start, end)
        assert len(slots) == 14  # All slots free

    @pytest.mark.asyncio
    async def test_defaults_when_no_cabinet(self, adapter):
        """Unknown cabinet ID → default working hours (Mon-Fri 9-12, 14-18)."""
        # Monday
        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 30, 23, 59)
        slots = await adapter.get_available_slots("nonexistent", start, end)
        # Default: 9-12 (6 slots) + 14-18 (8 slots) = 14
        assert len(slots) == 14

    @pytest.mark.asyncio
    async def test_multiday_range(self, adapter, cabinet):
        """Query across Mon-Tue should return slots for both days."""
        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 31, 23, 59)
        slots = await adapter.get_available_slots(cabinet.id, start, end)
        assert len(slots) == 28  # 14 * 2

    @pytest.mark.asyncio
    async def test_start_filter_excludes_past_slots(self, adapter, cabinet):
        """start filter should exclude slots before that time."""
        # Start at 14:00 on Monday — should only get afternoon slots
        start = datetime(2026, 3, 30, 14, 0)
        end = datetime(2026, 3, 30, 23, 59)
        slots = await adapter.get_available_slots(cabinet.id, start, end)
        # 14:00-18:00 = 8 slots
        assert len(slots) == 8


# ── book ──────────────────────────────────────────────────────────────────────

class TestBook:

    @pytest.mark.asyncio
    async def test_book_creates_appointment(self, adapter, cabinet):
        slot = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        patient = PatientContact(
            name="Martin Durand",
            phone=PhoneNumber("0612345678"),
        )

        appt = await adapter.book(cabinet.id, slot, patient)

        assert appt.id is not None
        assert appt.cabinet_id == cabinet.id
        assert appt.time_slot.start == slot.start
        assert appt.status == AppointmentStatus.CONFIRMED
        assert appt.patient_contact.name == "Martin Durand"

    @pytest.mark.asyncio
    async def test_book_auto_creates_patient(self, adapter, cabinet, session_factory):
        slot = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        patient = PatientContact(
            name="Nouveau Patient",
            phone=PhoneNumber("0698765432"),
        )

        await adapter.book(cabinet.id, slot, patient)

        # Check patient was created
        with session_factory() as session:
            from sqlmodel import select
            patients = session.exec(
                select(PatientModel).where(PatientModel.telephone == "0698765432")
            ).all()
            assert len(patients) == 1
            assert patients[0].nom == "Nouveau Patient"

    @pytest.mark.asyncio
    async def test_book_reuses_existing_patient(self, adapter, cabinet, session_factory):
        """Second booking with same phone should reuse patient."""
        # Create first booking
        slot1 = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        slot2 = TimeSlot(
            start=datetime(2026, 3, 30, 11, 0),
            end=datetime(2026, 3, 30, 11, 30),
        )
        patient = PatientContact(
            name="Martin Durand",
            phone=PhoneNumber("0612345678"),
        )

        await adapter.book(cabinet.id, slot1, patient)
        await adapter.book(cabinet.id, slot2, patient)

        with session_factory() as session:
            from sqlmodel import select
            patients = session.exec(
                select(PatientModel).where(PatientModel.telephone == "0612345678")
            ).all()
            assert len(patients) == 1

    @pytest.mark.asyncio
    async def test_book_updates_patient_name(self, adapter, cabinet, session_factory):
        """If patient exists without name, booking should update it."""
        # Pre-create patient with no name
        with session_factory() as session:
            p = PatientModel(
                cabinet_id=cabinet.id,
                telephone="0612345678",
                nom="",
            )
            session.add(p)
            session.commit()

        slot = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        patient = PatientContact(
            name="Martin Durand",
            phone=PhoneNumber("0612345678"),
        )

        await adapter.book(cabinet.id, slot, patient)

        with session_factory() as session:
            from sqlmodel import select
            p = session.exec(
                select(PatientModel).where(PatientModel.telephone == "0612345678")
            ).first()
            assert p.nom == "Martin Durand"

    @pytest.mark.asyncio
    async def test_book_sets_source_ai_call(self, adapter, cabinet, session_factory):
        slot = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        patient = PatientContact(
            name="Test",
            phone=PhoneNumber("0612345678"),
        )

        appt = await adapter.book(cabinet.id, slot, patient)

        with session_factory() as session:
            row = session.get(AppointmentModel, appt.id)
            assert row.source == "ai_call"


# ── cancel ────────────────────────────────────────────────────────────────────

class TestCancel:

    @pytest.mark.asyncio
    async def test_cancel_sets_status(self, adapter, cabinet, session_factory):
        # Create an appointment
        with session_factory() as session:
            appt = AppointmentModel(
                id="appt-cancel-1",
                cabinet_id=cabinet.id,
                patient_nom="Patient Cancel",
                date_heure=datetime(2026, 3, 30, 10, 0),
                duree_minutes=30,
                status="confirmed",
            )
            session.add(appt)
            session.commit()

        await adapter.cancel("appt-cancel-1")

        with session_factory() as session:
            row = session.get(AppointmentModel, "appt-cancel-1")
            assert row.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_is_noop(self, adapter):
        """Cancelling a nonexistent appointment should not raise."""
        await adapter.cancel("nonexistent-id")  # Should not raise


# ── find_appointments ─────────────────────────────────────────────────────────

class TestFindAppointments:

    @pytest.mark.asyncio
    async def test_find_by_patient_name(self, adapter, cabinet, session_factory):
        with session_factory() as session:
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Dupont Marie",
                date_heure=datetime(2026, 3, 30, 10, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Martin Jean",
                date_heure=datetime(2026, 3, 30, 11, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.commit()

        results = await adapter.find_appointments(cabinet.id, patient_name="Dupont")
        assert len(results) == 1
        assert results[0].patient_contact.name == "Dupont Marie"

    @pytest.mark.asyncio
    async def test_find_by_date_range(self, adapter, cabinet, session_factory):
        with session_factory() as session:
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Patient A",
                date_heure=datetime(2026, 3, 28, 10, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Patient B",
                date_heure=datetime(2026, 3, 30, 10, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.commit()

        results = await adapter.find_appointments(
            cabinet.id,
            start=datetime(2026, 3, 29, 0, 0),
            end=datetime(2026, 3, 31, 0, 0),
        )
        assert len(results) == 1
        assert results[0].patient_contact.name == "Patient B"

    @pytest.mark.asyncio
    async def test_find_excludes_cancelled(self, adapter, cabinet, session_factory):
        with session_factory() as session:
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Active",
                date_heure=datetime(2026, 3, 30, 10, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Cancelled",
                date_heure=datetime(2026, 3, 30, 11, 0),
                duree_minutes=30,
                status="cancelled",
            ))
            session.commit()

        results = await adapter.find_appointments(cabinet.id)
        assert len(results) == 1
        assert results[0].patient_contact.name == "Active"

    @pytest.mark.asyncio
    async def test_find_returns_sorted(self, adapter, cabinet, session_factory):
        with session_factory() as session:
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Later",
                date_heure=datetime(2026, 3, 30, 14, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.add(AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom="Earlier",
                date_heure=datetime(2026, 3, 30, 9, 0),
                duree_minutes=30,
                status="confirmed",
            ))
            session.commit()

        results = await adapter.find_appointments(cabinet.id)
        assert len(results) == 2
        assert results[0].patient_contact.name == "Earlier"
        assert results[1].patient_contact.name == "Later"


# ── Integration: book then verify slot blocked ────────────────────────────────

class TestBookThenQuery:

    @pytest.mark.asyncio
    async def test_booked_slot_disappears_from_available(self, adapter, cabinet):
        """After booking 10:00-10:30, that slot should not appear in available slots."""
        slot = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        patient = PatientContact(
            name="Test Patient",
            phone=PhoneNumber("0612345678"),
        )

        # All slots available before booking
        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 30, 23, 59)
        before = await adapter.get_available_slots(cabinet.id, start, end)
        assert len(before) == 14

        # Book
        await adapter.book(cabinet.id, slot, patient)

        # One less slot
        after = await adapter.get_available_slots(cabinet.id, start, end)
        assert len(after) == 13

    @pytest.mark.asyncio
    async def test_cancel_then_slot_reappears(self, adapter, cabinet):
        """After cancelling a booking, the slot should reappear."""
        slot = TimeSlot(
            start=datetime(2026, 3, 30, 10, 0),
            end=datetime(2026, 3, 30, 10, 30),
        )
        patient = PatientContact(
            name="Test Patient",
            phone=PhoneNumber("0612345678"),
        )

        start = datetime(2026, 3, 30, 0, 0)
        end = datetime(2026, 3, 30, 23, 59)

        appt = await adapter.book(cabinet.id, slot, patient)
        assert len(await adapter.get_available_slots(cabinet.id, start, end)) == 13

        await adapter.cancel(appt.id)
        assert len(await adapter.get_available_slots(cabinet.id, start, end)) == 14
