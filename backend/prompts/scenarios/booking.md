# Scénario : Prise de rendez-vous

## Objectif
Aider le patient à trouver et confirmer un créneau de kinésithérapie.

## Étapes

1. **Identifier le besoin** : demander quand le patient souhaite venir (jour, matin/après-midi)
2. **Consulter les créneaux** : appeler `get_available_slots` avec le date_hint du patient
3. **Vérifier les horaires** : ne proposer que des créneaux dans les horaires du cabinet. Si le patient demande un créneau en dehors (ex: "samedi" alors que le cabinet est fermé), l'informer poliment et proposer des alternatives.
4. **Proposer** : présenter 2-3 créneaux disponibles de manière naturelle et orale
   - Exemple : "J'ai un créneau lundi à dix heures et un autre mardi à quatorze heures trente. Lequel vous conviendrait ?"
5. **Confirmer** : une fois le choix fait, demander le nom du patient si pas encore connu
6. **Enregistrer** : appeler `confirm_booking` avec le slot_index et le patient_name pour finaliser
7. **Récapituler** : confirmer le rendez-vous avec date, heure et adresse du cabinet

Les séances de kinésithérapie durent 30 minutes par défaut. Si le patient demande la durée, l'indiquer.

## Gestion des cas particuliers

- **Aucun créneau** : s'excuser, proposer une autre semaine ou laisser un message
- **Patient hésite** : proposer de rappeler quand il aura vérifié ses disponibilités
- **Patient change d'avis** : ne pas finaliser, demander ce qu'il souhaite à la place
- **Première visite** : préciser les documents à apporter si l'info est dans la FAQ du cabinet
