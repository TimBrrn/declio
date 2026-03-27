from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cabinet:
    """Cabinet de kinesitherapie."""

    id: str
    nom_cabinet: str
    nom_praticien: str
    adresse: str
    telephone: str
    horaires: dict[str, list[str]]  # jour → ["09:00-12:00", "14:00-18:00"]
    tarifs: dict[str, float]  # type → montant (ex: {"seance": 50.0})
    google_calendar_id: str
    numero_sms_kine: str
    message_accueil: str = (
        "Cabinet {nom_cabinet}, bonjour ! "
        "Vous êtes en ligne avec l'assistant du cabinet de {nom_praticien}. "
        "Que puis-je faire pour vous ?"
    )
    faq: dict[str, str] = field(default_factory=dict)  # question_key → reponse

    def format_message_accueil(self) -> str:
        return self.message_accueil.format(
            nom_cabinet=self.nom_cabinet,
            nom_praticien=self.nom_praticien,
        )
