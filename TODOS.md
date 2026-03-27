# TODOS — Declio

## Post-PoC / v1

### Migration SQLite → PostgreSQL
- **What:** Remplacer SQLite par PostgreSQL quand le nombre de cabinets depasse ~10.
- **Why:** SQLite a un verrou en ecriture unique. Avec 50+ cabinets et appels simultanes, ca deviendra un goulet.
- **Pros:** Concurrence native, scalabilite, backup, replication.
- **Cons:** Overhead ops (Docker ou service manage), cout hebergement.
- **Context:** SQLModel rend la migration quasi-transparente — memes modeles, juste changer l'engine URL. Prevoir en post-PoC si validation reussie.
- **Effort:** M (1-2 jours)
- **Priority:** P2
- **Blocked by:** Validation PoC reussie (au moins 2/3 cabinets prets a payer)

### Certification HDS (Hebergeur Donnees de Sante)
- **What:** Migrer l'hebergement vers un provider certifie HDS (OVH Healthcare, Scaleway HDS) avant commercialisation.
- **Why:** Obligation legale francaise. Les conversations telephoniques avec des patients peuvent contenir des donnees de sante. Sans HDS, pas de commercialisation legale.
- **Pros:** Conformite reglementaire, confiance des praticiens, argument commercial.
- **Cons:** Cout hebergement x3-5, contraintes techniques (localisation FR, audits).
- **Context:** Pour le PoC avec 3 cabinets pilotes et DPA signe, c'est acceptable sans HDS. Mais bloquant avant le premier client payant.
- **Effort:** L (1-2 semaines avec migration infra)
- **Priority:** P1 (bloquant commercialisation)
- **Blocked by:** Validation PoC reussie + decision de commercialiser

### Rappels automatiques 48h avant RDV
- **What:** Envoyer un SMS/WhatsApp au patient 48h avant son RDV avec confirmation OUI/NON.
- **Why:** Reduire les no-shows (objectif -50%). Chaque no-show = 30 min perdue pour le kine = ~16-25 EUR perdus.
- **Pros:** ROI direct mesurable, forte valeur percue par les kines, facile a implementer (cron job + SMS).
- **Cons:** Necessite stocker les numeros patients (RGPD), gestion des reponses entrantes.
- **Context:** Etait dans le cahier des charges initial comme feature secondaire. Reporte en CEO review pour garder le focus PoC. Bon candidat pour la semaine 2 du test terrain.
- **Effort:** S (0.5-1 jour)
- **Priority:** P1 (forte valeur, faible effort)
- **Blocked by:** Pipeline SMS fonctionnel (J4 du PoC)

### Audio buffering pendant reconnexion WebSocket
- **What:** Ajouter un ring buffer dans TelnyxTelephonyAdapter qui stocke les derniers 5s d'audio inbound pour les rejouer apres une reconnexion WS.
- **Why:** Pendant les ~5s de reconnexion WS, l'audio du patient est perdu. Le patient doit repeter ce qu'il a dit.
- **Pros:** Experience fluide, pas de repetition necessaire apres une micro-coupure reseau.
- **Cons:** Complexite (ring buffer + replay), necessite que Telnyx supporte le buffering cote cloud ou qu'on le fasse cote serveur.
- **Context:** Depends on la reconnexion silencieuse WS (implementee en J6). Ne peut etre fait que si Telnyx expose un mecanisme de replay audio ou si on buffer localement les derniers chunks recus avant la deconnexion.
- **Effort:** M (1-2 jours de R&D Telnyx API)
- **Priority:** P3
- **Blocked by:** Reconnexion silencieuse WS fonctionnelle

### Test d'integration WebSocket reconnexion
- **What:** Ajouter 1 test d'integration qui utilise TestClient pour simuler un vrai cycle WS connect → disconnect → reconnect, en complement des unit tests mocks.
- **Why:** Les unit tests avec mocks/Events testent la logique mais pas le vrai comportement Starlette/ASGI (headers, close codes, timing).
- **Pros:** Couvre les bugs de plomberie WS, plus de confiance avant deploiement.
- **Cons:** ~2s par test, risque de flakiness sur CI.
- **Context:** Pour le PoC les unit tests suffisent. A ajouter en v1 quand on a un CI stable.
- **Effort:** S (2-3h)
- **Priority:** P3
- **Blocked by:** CI fonctionnel

### Filtrage des appels par patient_name via l'API
- **What:** Ajouter un query param `patient_name` a `GET /api/calls/` pour filtrer les appels par nom de patient.
- **Why:** Le champ `patient_name` est maintenant un champ dedie dans `CallRecordModel`. Le kine peut chercher l'historique d'un patient specifique.
- **Pros:** Feature a forte valeur avec 1 ligne de code (WHERE clause). Suit le pattern existant de `scenario`, `date_from`, `date_to`, `cabinet_id`.
- **Cons:** Quasi-zero. Necessite juste que le champ existe en DB.
- **Context:** Le endpoint `list_calls` dans `backend/src/api/routes/calls.py` supporte deja 4 filtres. Ajouter `patient_name` suit exactement le meme pattern (Query param + WHERE clause).
- **Effort:** XS (10 min)
- **Priority:** P2
- **Blocked by:** Champ `patient_name` en DB (fait)
