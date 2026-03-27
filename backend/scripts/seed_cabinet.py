#!/usr/bin/env python3
"""Seed the Declio database with a realistic kine cabinet.

Usage:
    python -m backend.scripts.seed_cabinet

Wipes all existing data (cabinets, appointments, call_records) and creates
a single fully-populated cabinet ready for end-to-end testing.
"""

import os
import sys

from sqlalchemy import delete
from sqlmodel import Session

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.src.infrastructure.persistence.database import engine, init_db
from backend.src.infrastructure.persistence.models import (
    AppointmentModel,
    CallRecordModel,
    CabinetModel,
)


def seed_cabinet() -> None:
    init_db()

    with Session(engine) as session:
        # Clean all tables
        session.exec(delete(CallRecordModel))
        session.exec(delete(AppointmentModel))
        session.exec(delete(CabinetModel))
        session.commit()
        print("Base nettoyée.")

        cabinet = CabinetModel(
            nom_cabinet="Cabinet Dupont Kinésithérapie",
            nom_praticien="Jean Dupont",
            adresse="12 rue de la Santé, 75013 Paris",
            telephone="01 45 87 12 34",
            google_calendar_id=os.environ.get("GOOGLE_CALENDAR_ID", ""),
            numero_sms_kine=os.environ.get("NUMERO_SMS_KINE", ""),
            message_accueil="Bonjour, vous êtes bien au cabinet de {nom_praticien}, kinésithérapeute. Je suis l'assistant vocal du cabinet. Je peux vous aider à prendre un rendez-vous, annuler ou reporter un rendez-vous, ou répondre à vos questions sur le cabinet. Comment puis-je vous aider ?",
        )
        cabinet.horaires = {
            "lundi": ["09:00-12:00", "14:00-19:00"],
            "mardi": ["09:00-12:00", "14:00-19:00"],
            "mercredi": ["09:00-12:00", "14:00-19:00"],
            "jeudi": ["09:00-12:00", "14:00-19:00"],
            "vendredi": ["09:00-12:00", "14:00-19:00"],
            "samedi": ["09:00-12:00"],
        }
        cabinet.tarifs = {
            "séance_kiné": 16.13,
            "bilan_initial": 25.00,
            "séance_domicile": 23.00,
        }
        cabinet.faq = {
            "ordonnance": "Oui, une prescription médicale de votre médecin est nécessaire pour consulter le kinésithérapeute.",
            "carte_vitale": "Oui, le cabinet accepte la carte Vitale. Pensez à l'apporter avec votre ordonnance.",
            "nombre_séances": "C'est le kinésithérapeute qui détermine le nombre de séances lors du bilan initial, en fonction de votre pathologie.",
            "première_visite": "Pour votre première visite, apportez votre ordonnance, votre carte Vitale et votre carte de mutuelle.",
            "parking": "Il y a un parking gratuit à 50 mètres du cabinet, rue du Docteur Leroy.",
            "accès": "Le cabinet est accessible aux personnes à mobilité réduite. Ascenseur disponible.",
            "mutuelle": "Le cabinet pratique le tiers payant avec la Sécurité sociale. Pour la part mutuelle, une facture vous sera remise.",
            "retard": "En cas de retard de plus de 15 minutes, le rendez-vous peut être reporté. Merci de prévenir le cabinet.",
            "annulation": "Merci de prévenir au moins 24 heures à l'avance en cas d'annulation.",
        }

        session.add(cabinet)
        session.commit()
        session.refresh(cabinet)
        print(f"Cabinet '{cabinet.nom_cabinet}' créé (id={cabinet.id}).")
        print(f"  Praticien: {cabinet.nom_praticien}")
        print(f"  Adresse: {cabinet.adresse}")
        print(f"  Horaires: lun-ven 9h-12h + 14h-19h, sam 9h-12h")
        print(f"  Tarifs: séance={cabinet.tarifs['séance_kiné']}€, bilan={cabinet.tarifs['bilan_initial']}€, domicile={cabinet.tarifs['séance_domicile']}€")
        print(f"  FAQ: {len(cabinet.faq)} entrées")


if __name__ == "__main__":
    seed_cabinet()
