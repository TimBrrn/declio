# Scénario : Annulation de rendez-vous

## Objectif
Annuler un rendez-vous existant et proposer un report si possible.

## Étapes

1. **Identifier le patient** : demander le nom du patient
2. **Identifier le RDV** : demander la date approximative du rendez-vous à annuler
3. **Confirmer** : répéter le RDV trouvé et demander confirmation ("Vous souhaitez bien annuler votre rendez-vous de jeudi 14h30 ?")
4. **Annuler** : appeler `cancel_appointment` pour supprimer
5. **Proposer un report** : "Souhaitez-vous reprendre un autre créneau ?"
6. **Si oui** : basculer vers le scénario de prise de RDV (appeler `get_available_slots` puis `confirm_booking`)
7. **Report = annulation + nouvelle réservation** : un report est simplement une annulation suivie d'une prise de RDV. Ne pas proposer de "déplacer" directement — annuler d'abord, puis reproposer des créneaux.

## Gestion des cas particuliers

- **RDV introuvable** : "Je ne trouve pas de rendez-vous à ce nom. Pouvez-vous me donner plus de détails ?"
- **Annulation tardive** : informer si politique d'annulation (24h avant, etc.) — si dans la config cabinet
