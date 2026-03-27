from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.src.domain.entities.cabinet import Cabinet

logger = logging.getLogger(__name__)


def answer_faq(cabinet: Cabinet, question: str) -> str:
    """Repond a une question FAQ depuis la config du cabinet.

    Cherche d'abord dans cabinet.faq, puis dans les tarifs/horaires.
    """
    logger.info("answer_faq: question=%r", question[:200])
    q = question.lower().strip()

    # Chercher dans le dictionnaire FAQ
    if cabinet.faq:
        for key, answer in cabinet.faq.items():
            if key.lower() in q or q in key.lower():
                logger.info("answer_faq: matched FAQ key=%r", key)
                return answer

    # Tarifs
    if any(kw in q for kw in ("tarif", "prix", "combien", "cout")):
        logger.info("answer_faq: matched category=tarifs")
        if cabinet.tarifs:
            lines = ["Nos tarifs :"]
            for type_soin, montant in cabinet.tarifs.items():
                lines.append(f"- {type_soin} : {montant:.0f} euros")
            return "\n".join(lines)
        return "Je n'ai pas les informations tarifaires. Le cabinet pourra vous renseigner."

    # Horaires
    if any(kw in q for kw in ("horaire", "heure", "ouvert")):
        logger.info("answer_faq: matched category=horaires")
        if cabinet.horaires:
            lines = ["Nos horaires :"]
            for jour, plages in cabinet.horaires.items():
                lines.append(f"- {jour} : {', '.join(plages)}")
            return "\n".join(lines)

    # Adresse
    if any(kw in q for kw in ("adresse", "ou", "localisation", "parking")):
        logger.info("answer_faq: matched category=adresse")
        return f"Le cabinet se trouve au {cabinet.adresse}."

    logger.warning("answer_faq: no match found for question=%r", question[:200])
    return (
        "Je n'ai pas la reponse a cette question. "
        "Souhaitez-vous que le cabinet vous rappelle ?"
    )
