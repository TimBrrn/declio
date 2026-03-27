"""Tests CallProcessor — detection de scenario."""

from backend.src.domain.entities.call_record import ScenarioEnum
from backend.src.domain.services.call_processor import CallProcessor


class TestDetectScenario:
    def setup_method(self):
        self.processor = CallProcessor()

    # ── Booking ──

    def test_detect_rdv(self):
        assert (
            self.processor.detect_scenario("Je voudrais prendre un rdv")
            == ScenarioEnum.BOOKING
        )

    def test_detect_rendez_vous(self):
        assert (
            self.processor.detect_scenario("Je souhaite prendre un rendez-vous")
            == ScenarioEnum.BOOKING
        )

    def test_detect_creneau(self):
        assert (
            self.processor.detect_scenario("Vous avez un creneau cette semaine ?")
            == ScenarioEnum.BOOKING
        )

    # ── Cancellation ──

    def test_detect_annuler(self):
        assert (
            self.processor.detect_scenario("Je voudrais annuler mon rendez-vous")
            == ScenarioEnum.CANCELLATION
        )

    def test_detect_annulation(self):
        assert (
            self.processor.detect_scenario("C'est pour une annulation")
            == ScenarioEnum.CANCELLATION
        )

    def test_cancellation_priority_over_booking(self):
        """Si le patient dit 'annuler mon rdv', c'est une annulation."""
        assert (
            self.processor.detect_scenario("Je veux annuler mon rdv de lundi")
            == ScenarioEnum.CANCELLATION
        )

    # ── FAQ ──

    def test_detect_tarif(self):
        assert (
            self.processor.detect_scenario("C'est combien une seance ?")
            == ScenarioEnum.FAQ
        )

    def test_detect_horaire(self):
        assert (
            self.processor.detect_scenario("Quels sont vos horaires ?")
            == ScenarioEnum.FAQ
        )

    def test_detect_adresse(self):
        assert (
            self.processor.detect_scenario("Quelle est votre adresse ?")
            == ScenarioEnum.FAQ
        )

    # ── Out of scope ──

    def test_detect_out_of_scope(self):
        assert (
            self.processor.detect_scenario("J'ai mal au dos depuis 3 jours")
            == ScenarioEnum.OUT_OF_SCOPE
        )

    def test_empty_transcript(self):
        assert (
            self.processor.detect_scenario("")
            == ScenarioEnum.OUT_OF_SCOPE
        )
