"""Tests AppointmentScheduler — logique pure, zero IO."""

from datetime import datetime

from backend.src.domain.services.appointment_scheduler import AppointmentScheduler
from backend.src.domain.value_objects.time_slot import TimeSlot


def _slot(day: int, start_h: int, end_h: int) -> TimeSlot:
    """Helper pour creer des creneaux rapidement."""
    return TimeSlot(
        start=datetime(2025, 1, day, start_h, 0),
        end=datetime(2025, 1, day, end_h, 0),
    )


class TestFindAvailableSlots:
    def setup_method(self):
        self.scheduler = AppointmentScheduler()

    def test_all_free(self):
        all_slots = [_slot(1, 9, 10), _slot(1, 10, 11), _slot(1, 14, 15)]
        result = self.scheduler.find_available_slots(all_slots, [])
        assert len(result) == 3

    def test_one_conflict(self):
        all_slots = [_slot(1, 9, 10), _slot(1, 10, 11)]
        existing = [_slot(1, 9, 10)]
        result = self.scheduler.find_available_slots(all_slots, existing)
        assert len(result) == 1
        assert result[0].start.hour == 10

    def test_all_taken(self):
        all_slots = [_slot(1, 9, 10), _slot(1, 10, 11)]
        existing = [_slot(1, 8, 12)]
        result = self.scheduler.find_available_slots(all_slots, existing)
        assert len(result) == 0

    def test_filters_short_slots(self):
        short = TimeSlot(
            start=datetime(2025, 1, 1, 9, 0),
            end=datetime(2025, 1, 1, 9, 15),
        )
        result = self.scheduler.find_available_slots(
            [short], [], duration_minutes=30
        )
        assert len(result) == 0


class TestProposeBestSlots:
    def setup_method(self):
        self.scheduler = AppointmentScheduler()

    def test_returns_max_proposals(self):
        slots = [_slot(3, 9, 10), _slot(1, 9, 10), _slot(2, 9, 10), _slot(4, 9, 10)]
        result = self.scheduler.propose_best_slots(slots, max_proposals=3)
        assert len(result) == 3
        # Trie par date
        assert result[0].start.day == 1
        assert result[1].start.day == 2
        assert result[2].start.day == 3

    def test_returns_all_if_fewer(self):
        slots = [_slot(1, 9, 10)]
        result = self.scheduler.propose_best_slots(slots, max_proposals=3)
        assert len(result) == 1


class TestCheckConflict:
    def setup_method(self):
        self.scheduler = AppointmentScheduler()

    def test_conflict(self):
        assert self.scheduler.check_conflict(
            _slot(1, 9, 10), [_slot(1, 9, 10)]
        ) is True

    def test_no_conflict(self):
        assert self.scheduler.check_conflict(
            _slot(1, 9, 10), [_slot(1, 10, 11)]
        ) is False

    def test_partial_overlap(self):
        assert self.scheduler.check_conflict(
            _slot(1, 9, 10), [_slot(1, 9, 11)]
        ) is True
