#!/usr/bin/env python3
"""Seed the Declio database with realistic demo appointments.

Usage:
    python -m backend.scripts.seed_appointments

Clears existing appointments and creates 12 demo RDVs spread across
the current and next week.  Requires a cabinet to exist (run seed_cabinet first).
"""

import os
import sys
from datetime import datetime, timedelta, UTC

from sqlalchemy import delete
from sqlmodel import Session, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.src.infrastructure.persistence.database import engine, init_db
from backend.src.infrastructure.persistence.models import AppointmentModel, CabinetModel

PATIENTS = [
    ("Martin Durand", "0612345678"),
    ("Sophie Lefebvre", "0698765432"),
    ("Pierre Moreau", "0654321987"),
    ("Marie Laurent", "0687654321"),
    ("Jean-Paul Roux", "0643218765"),
    ("Isabelle Bernard", "0676543210"),
    ("Nicolas Petit", "0665432109"),
    ("Claire Dubois", "0632109876"),
    ("Antoine Simon", "0621098765"),
    ("Camille Fontaine", "0610987654"),
    ("Luc Girard", "0609876543"),
    ("Emma Leroy", "0645678901"),
]


def seed_appointments() -> None:
    init_db()

    with Session(engine) as session:
        cabinet = session.exec(select(CabinetModel)).first()
        if not cabinet:
            print("Aucun cabinet trouve. Lancez d'abord: python -m backend.scripts.seed_cabinet")
            sys.exit(1)

        # Clear existing appointments
        session.exec(delete(AppointmentModel))
        session.commit()
        print("Appointments nettoyes.")

        # Start from Monday of the current week
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Slots spread across 2 weeks (lun-sam), realistic hours
        slot_offsets = [
            # Week 1
            (0, 9, 0),    # Lundi 9h00
            (0, 10, 30),  # Lundi 10h30
            (0, 15, 0),   # Lundi 15h00
            (1, 9, 30),   # Mardi 9h30
            (1, 14, 0),   # Mardi 14h00
            (2, 11, 0),   # Mercredi 11h00
            (2, 16, 0),   # Mercredi 16h00
            (3, 10, 0),   # Jeudi 10h00
            (3, 15, 30),  # Jeudi 15h30
            (4, 9, 0),    # Vendredi 9h00
            (4, 17, 0),   # Vendredi 17h00
            (5, 10, 0),   # Samedi 10h00
        ]

        count = 0
        for i, (day_offset, hour, minute) in enumerate(slot_offsets):
            patient_name, patient_phone = PATIENTS[i % len(PATIENTS)]
            dt = monday + timedelta(days=day_offset)
            dt = dt.replace(hour=hour, minute=minute)

            # Mark 2 appointments as cancelled for visual variety
            status = "cancelled" if i in (4, 8) else "confirmed"

            appt = AppointmentModel(
                cabinet_id=cabinet.id,
                patient_nom=patient_name,
                patient_telephone=patient_phone,
                date_heure=dt,
                duree_minutes=30,
                status=status,
                google_event_id=f"demo-event-{i+1}",
            )
            session.add(appt)
            count += 1

        session.commit()
        print(f"{count} rendez-vous de demo crees (semaine du {monday.strftime('%d/%m/%Y')}).")
        print(f"  Cabinet: {cabinet.nom_cabinet}")
        print(f"  Dont 2 annules (mardi 14h, jeudi 15h30)")


if __name__ == "__main__":
    seed_appointments()
