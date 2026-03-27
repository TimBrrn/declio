from __future__ import annotations

from backend.src.domain.value_objects.time_slot import TimeSlot


class AppointmentScheduler:
    """Logique pure pour la gestion des creneaux — aucun IO."""

    def find_available_slots(
        self,
        all_slots: list[TimeSlot],
        existing_appointments: list[TimeSlot],
        duration_minutes: int = 30,
    ) -> list[TimeSlot]:
        """Retourne les creneaux libres (pas de conflit avec les existants)."""
        available: list[TimeSlot] = []
        for slot in all_slots:
            if slot.duration_minutes < duration_minutes:
                continue
            if not self.check_conflict(slot, existing_appointments):
                available.append(slot)
        return available

    def propose_best_slots(
        self,
        available: list[TimeSlot],
        max_proposals: int = 3,
    ) -> list[TimeSlot]:
        """Retourne les N premiers creneaux disponibles (les plus proches)."""
        sorted_slots = sorted(available, key=lambda s: s.start)
        return sorted_slots[:max_proposals]

    def check_conflict(
        self,
        slot: TimeSlot,
        existing: list[TimeSlot],
    ) -> bool:
        """Retourne True si le creneau est en conflit avec un existant."""
        return any(slot.overlaps(e) for e in existing)
