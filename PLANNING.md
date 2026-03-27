# Declio — Planning detaille par jour et par agent

## J1 — Scaffolding (EN COURS)

### Criteres de succes
- [ ] `uvicorn backend.src.api.main:app --reload` demarre sans erreur sur :8000
- [ ] GET /api/cabinets retourne une liste vide (200 OK)
- [ ] POST /api/cabinets cree un cabinet en base SQLite
- [ ] `pytest backend/tests/unit/` — tous les tests domain passent au vert
- [ ] Les 6 ports (Protocol) sont definis dans domain/ports/
- [ ] Le graphe LangGraph est assemble dans application/graph/call_graph.py
- [ ] `npm run dev` dans frontend/ affiche l'app sur :5173
- [ ] Les 2 pages (config cabinet, historique appels) sont navigables

### Missions par agent
Voir les instructions deja lancees.

---

## J2 — Pipeline audio streaming + conversation

C'est le jour le plus critique. L'objectif est d'avoir un appel telephonique fonctionnel de bout en bout : le patient appelle, l'agent repond vocalement en francais, et on peut avoir un echange basique.

### Criteres de succes
- [ ] Un appel entrant sur le numero Telnyx est decroche automatiquement
- [ ] Le patient entend le message d'accueil en voix naturelle francaise (ElevenLabs)
- [ ] Le patient parle et sa voix est transcrite en temps reel (Deepgram)
- [ ] L'agent repond vocalement avec une reponse coherente (OpenAI → ElevenLabs)
- [ ] La latence entre fin de phrase patient et debut de reponse agent est < 3s (objectif < 2s)
- [ ] Le barge-in fonctionne : si le patient parle pendant que l'agent parle, l'agent s'arrete et ecoute
- [ ] Un echange de 3-4 tours de parole fonctionne sans crash
- [ ] Les logs affichent : latence STT, latence LLM, latence TTS pour chaque tour

### Agent BACKEND

```
Lis le fichier CLAUDE.md a la racine du projet. Tu es l'AGENT BACKEND.

TON PERIMETRE : backend/src/infrastructure/, backend/src/api/
NE TOUCHE JAMAIS : domain/, application/, prompts/, frontend/

TACHE J2 : Pipeline audio streaming + adapters STT/TTS

1. Creer backend/src/infrastructure/adapters/deepgram_stt.py :
   - Implemente STTPort
   - Connexion WebSocket a Deepgram en mode streaming
   - Envoie les chunks audio recus de Telnyx vers Deepgram
   - Recoit les transcriptions en temps reel (interim + final)
   - Retourne des tuples (texte, confidence_score)
   - Langue: fr (francais)
   - Modele: nova-2 (le plus performant pour le francais)

2. Creer backend/src/infrastructure/adapters/elevenlabs_tts.py :
   - Implemente TTSPort
   - Utilise l'API streaming d'ElevenLabs
   - Envoie le texte phrase par phrase
   - Recoit les chunks audio en streaming
   - Format audio : mulaw 8000Hz (format telephonique Telnyx)
   - Choisir une voix francaise naturelle (ex: "Antoine" ou "Charlotte")

3. Creer backend/src/infrastructure/audio/pipeline.py :
   - Classe AudioPipeline qui orchestre le flux complet :
     a. Recoit l'audio du patient depuis le WebSocket Telnyx
     b. Forward vers Deepgram STT en streaming
     c. Quand une transcription finale arrive, la passe au graphe LangGraph
        (via un callback ou une queue async)
     d. Recoit la reponse texte du graphe
     e. Forward vers ElevenLabs TTS en streaming
     f. Renvoie les chunks audio TTS vers le WebSocket Telnyx
   - Le pipeline doit gerer le streaming bout-en-bout :
     PAS attendre la reponse complete du LLM avant de lancer le TTS.
     Des qu'une phrase est complete, l'envoyer au TTS.
   - Logger les latences a chaque etape

4. Creer backend/src/infrastructure/audio/barge_in.py :
   - Detecter quand le patient parle pendant que l'agent envoie du TTS
   - Deepgram envoie des transcriptions meme pendant le TTS :
     si on recoit une transcription non-vide pendant qu'on stream du TTS,
     c'est un barge-in
   - Action : couper immediatement le flux TTS, arreter d'envoyer des
     chunks audio a Telnyx, signaler au pipeline de repasser en mode ecoute
   - Implementer un flag is_speaking sur le pipeline

5. Mettre a jour backend/src/api/webhooks/telnyx_webhook.py :
   - Sur call.answered : creer une instance AudioPipeline pour cet appel
   - Connecter le WebSocket Telnyx au pipeline
   - Connecter le pipeline au graphe LangGraph (importer depuis application/graph/)
   - Sur call.hangup : cleanup du pipeline

6. Mettre a jour backend/src/api/dependencies.py :
   - Ajouter les providers pour STTPort (Deepgram) et TTSPort (ElevenLabs)
   - Verifier que les cles API sont chargees depuis settings

Assure-toi que les connexions WebSocket sont proprement fermees quand
l'appel se termine (pas de fuite de connexion).
```

### Agent LLM

```
Lis le fichier CLAUDE.md a la racine du projet. Tu es l'AGENT LLM.

TON PERIMETRE : backend/src/domain/, backend/src/application/, backend/prompts/
NE TOUCHE JAMAIS : infrastructure/audio/, infrastructure/persistence/, api/, frontend/

TACHE J2 : OpenAI adapter + connecter le graphe LangGraph aux vrais ports

1. Creer backend/src/infrastructure/adapters/openai_conversation.py :
   - Implemente ConversationPort
   - Utilise le SDK OpenAI avec model="gpt-4o"
   - Methode chat_stream(messages, tools) :
     utilise client.chat.completions.create(stream=True)
     yield chaque chunk de texte au fur et a mesure
   - Methode chat_with_tools(messages, tools) :
     appel non-streaming, retourne la reponse + les tool_calls
   - Les tools sont definis au format OpenAI function calling :
     book_appointment, cancel_appointment, get_available_slots, leave_message
   - Temperature: 0.3 (reponses coherentes et previsibles)

2. Mettre a jour backend/src/application/graph/state.py :
   - Ajouter les champs necessaires pour le streaming :
     response_text: str (reponse en cours de generation)
     tool_calls: list[ToolCall] (appels de tools en attente)
     error: str | None (si erreur, pour le fallback)

3. Implementer les noeuds du graphe :
   - nodes/greeting.py : charge le system_prompt.md, remplace {nom_cabinet}
     et {nom_praticien} par les valeurs du cabinet. Retourne le texte
     d'accueil a envoyer au TTS.
   - nodes/thinking.py : appelle ConversationPort.chat_with_tools()
     avec l'historique des messages + la derniere transcription.
     Route vers TOOL_EXEC si tool_call, vers RESPONDING sinon.
   - nodes/tool_exec.py : execute le tool call en appelant le bon use case
     (BookAppointment, CancelAppointment, AnswerFAQ). Ajoute le resultat
     a l'historique et retourne vers THINKING (pour que le LLM formule
     la reponse avec le resultat du tool).
   - nodes/responding.py : prend response_text et le marque comme pret
     pour le TTS. L'audio pipeline (agent backend) se chargera du streaming.
   - nodes/summary.py : construit le CallSummary a partir du call_record
     et appelle SendCallSummary.

4. Mettre a jour backend/src/application/graph/call_graph.py :
   - Connecter tous les noeuds avec les bonnes transitions
   - Ajouter la condition sur THINKING :
     si tool_calls present → TOOL_EXEC
     si should_hangup → HANGUP
     sinon → RESPONDING
   - Ajouter la condition sur RESPONDING :
     apres avoir parle → LISTENING (on attend la suite du patient)

5. Affiner les prompts :
   - system_prompt.md : ajouter des exemples de conversations typiques
     (few-shot) pour guider le ton et le style de l'agent
   - Etre TRES explicite sur : reponses COURTES (1-2 phrases max),
     ton naturel oral (pas de langage ecrit), toujours proposer
     des options claires au patient

6. Ajouter des tests :
   - test_call_graph.py : tester le graphe avec des ports mockes
     Scenario : greeting → patient dit "je voudrais un rdv" →
     thinking detecte BOOKING → tool_call get_slots → tool_exec
     retourne des creneaux → thinking formule la reponse → responding
   - Verifier que le state est correctement mis a jour a chaque noeud
```

### Agent FRONTEND

```
Lis le fichier CLAUDE.md a la racine du projet. Tu es l'AGENT FRONTEND.

TON PERIMETRE : frontend/
NE TOUCHE JAMAIS : backend/

TACHE J2 : Formulaire config cabinet fonctionnel + connexion API

1. Connecter CabinetConfig.tsx a l'API backend :
   - Au chargement : GET /api/cabinets → si un cabinet existe, pre-remplir
   - Au submit : POST /api/cabinets (creation) ou PUT /api/cabinets/:id (update)
   - Afficher un toast/notification de succes ou erreur
   - Ajouter un etat loading sur le bouton sauvegarder

2. Ameliorer le formulaire CabinetConfig :
   - Section "Informations generales" : nom cabinet, nom praticien, adresse, telephone
   - Section "Horaires" : pour chaque jour de la semaine, toggle actif/inactif +
     heure debut + heure fin (ex: Lundi 8h-19h, Samedi 8h-12h, Dimanche inactif)
   - Section "Tarifs" : tarif seance conventionnelle, depassement eventuel,
     modes de paiement (checkboxes : CB, cheque, especes)
   - Section "Integration" : Google Calendar ID (champ texte avec aide),
     numero SMS du kine (format +33...)
   - Section "Personnalisation" : message d'accueil (textarea avec placeholder
     montrant le format par defaut)
   - Validation :
     telephone FR (06/07 + 8 chiffres ou +33)
     champs requis marques avec *
     message d'erreur inline sous chaque champ invalide

3. Creer un composant StatusBadge reutilisable :
   - Pour les scenarios d'appel : BOOKING (bleu), CANCELLATION (orange),
     FAQ (gris), OUT_OF_SCOPE (jaune), ERROR (rouge)
   - Utiliser les couleurs Tailwind

4. Ameliorer CallHistory.tsx :
   - Ajouter un filtre par date (aujourd'hui, cette semaine, ce mois)
   - Ajouter le badge scenario sur chaque ligne
   - Ajouter la duree formatee (ex: "2min 34s")
   - Afficher le score de confiance STT avec une jauge visuelle
     (vert > 0.8, orange 0.6-0.8, rouge < 0.6)
   - Cliquer sur une ligne ouvre un detail avec le resume complet

5. Gerer l'etat "pas encore de cabinet configure" :
   - Si GET /api/cabinets retourne une liste vide, afficher un ecran
     d'onboarding : "Bienvenue sur Declio ! Commencez par configurer
     votre cabinet." avec un bouton vers le formulaire
```

---

## J3 — Scenarios metier + Google Calendar

L'objectif est que les 5 scenarios conversationnels fonctionnent en vrai : le patient demande un RDV, l'agent lit le vrai Google Calendar, propose des creneaux reels, et ecrit le RDV confirme.

### Criteres de succes
- [ ] Scenario BOOKING : le patient demande un RDV → l'agent propose 2-3 creneaux reels depuis Google Calendar → le patient confirme → le RDV apparait dans Google Calendar
- [ ] Scenario CANCELLATION : le patient dit "j'annule mon RDV de mardi" → l'agent identifie le RDV → le supprime de Google Calendar → propose un nouveau creneau
- [ ] Scenario FAQ : le patient demande le tarif ou l'adresse → l'agent repond correctement depuis la config du cabinet
- [ ] Scenario HORS PERIMETRE : le patient pose une question medicale → l'agent refuse poliment et propose de laisser un message
- [ ] Scenario MESSAGE : le patient veut laisser un message urgent → l'agent prend le nom et le message → flag URGENT dans le SMS au kine
- [ ] Chaque scenario est testable en appelant le numero Telnyx

### Agent BACKEND

```
Lis le fichier CLAUDE.md a la racine du projet. Tu es l'AGENT BACKEND.

TON PERIMETRE : backend/src/infrastructure/, backend/src/api/
NE TOUCHE JAMAIS : domain/, application/, prompts/, frontend/

TACHE J3 : Google Calendar adapter + stabilisation pipeline

1. Creer backend/src/infrastructure/adapters/google_calendar.py :
   - Implemente CalendarPort
   - Utilise la librairie google-api-python-client + google-auth
   - OAuth2 avec service account OU OAuth2 user consent (plus simple
     pour le PoC : utiliser un service account avec acces au calendar du kine)
   - get_available_slots(cabinet_id, date_range) :
     Lire les events du calendar dans la plage de dates
     Calculer les creneaux libres en croisant avec les horaires du cabinet
     Retourner des TimeSlot
   - book(cabinet_id, slot, patient) :
     Creer un event Google Calendar avec titre "RDV {patient_name}"
     et description avec le telephone du patient
     Verifier qu'il n'y a pas de conflit juste avant d'ecrire (race condition)
   - cancel(appointment_id) :
     Supprimer l'event Google Calendar par son ID
   - Stocker les credentials dans .env (GOOGLE_SERVICE_ACCOUNT_JSON
     ou GOOGLE_CREDENTIALS_PATH)

2. Stabiliser le pipeline audio :
   - Tester avec des vrais appels telephoniques
   - Debugger les problemes de format audio (mulaw vs pcm, sample rate)
   - S'assurer que le silence du patient ne cause pas de timeout
   - Ajouter un silence timeout : si le patient ne parle pas pendant 10s,
     l'agent dit "Etes-vous toujours la ?"
   - Ajouter un max call duration : 5 minutes, apres quoi l'agent
     dit "Je vous remercie pour votre appel" et raccroche

3. Mettre a jour les routes API :
   - GET /api/cabinets/:id/slots?date=2026-03-27 → retourne les creneaux
     disponibles (utile pour le debug et le front)
   - Les routes CRUD existantes doivent charger/sauver le Google Calendar ID
```

### Agent LLM

```
Lis le fichier CLAUDE.md a la racine du projet. Tu es l'AGENT LLM.

TON PERIMETRE : backend/src/domain/, backend/src/application/, backend/prompts/
NE TOUCHE JAMAIS : infrastructure/audio/, infrastructure/persistence/, api/, frontend/

TACHE J3 : Function calling tools + scenarios complets + prompts affines

1. Definir les tools OpenAI dans un fichier dedie
   backend/src/application/tools_definition.py :
   - get_available_slots : parametres (date: str en format "YYYY-MM-DD" ou
     "cette semaine" ou "demain"). L'agent LLM convertit en dates concretes.
   - book_appointment : parametres (date: str, time: str, patient_name: str,
     patient_phone: str)
   - cancel_appointment : parametres (patient_name: str, date: str optionnel)
   - leave_message : parametres (patient_name: str, message: str,
     is_urgent: bool)
   Format : liste de dicts au format OpenAI function calling schema.

2. Mettre a jour nodes/tool_exec.py :
   - Router chaque tool call vers le bon use case :
     get_available_slots → BookAppointment.get_slots()
     book_appointment → BookAppointment.confirm()
     cancel_appointment → CancelAppointment.execute()
     leave_message → stocker le message dans call_record
   - Formater le resultat du tool comme un message systeme pour que
     le LLM puisse formuler une reponse naturelle au patient
     Ex: "Creneaux disponibles : jeudi 14h, jeudi 16h30, vendredi 9h"

3. Affiner les prompts pour chaque scenario :
   - prompts/scenarios/booking.md :
     "Quand le patient demande un RDV, appelle get_available_slots
     avec la date demandee. Propose 2-3 creneaux en les enoncant
     clairement. Quand le patient confirme, appelle book_appointment.
     Confirme avec la date et l'heure. Demande toujours le nom si
     tu ne l'as pas encore."
   - prompts/scenarios/cancellation.md :
     "Quand le patient veut annuler, demande quel RDV (date/heure).
     Appelle cancel_appointment. Confirme l'annulation. Propose
     immediatement un nouveau creneau."
   - prompts/scenarios/faq.md :
     "Pour les questions de tarif, utilise les informations du cabinet.
     Tarif conventionnel : {tarif}. Ne donne JAMAIS de conseil medical.
     Si le patient insiste sur une question medicale, dis :
     'Je ne suis pas en mesure de repondre a cette question.
     Souhaitez-vous que je transmette un message au praticien ?'"

4. Implementer la detection de fin de conversation :
   - Dans nodes/thinking.py, ajouter la logique pour detecter que
     la conversation est terminee :
     Le patient dit "merci au revoir" / "c'est tout" / "bonne journee"
     → mettre should_hangup = True dans le state
   - L'agent doit TOUJOURS conclure par une formule de politesse
     avant le hangup : "Je vous souhaite une bonne journee. Au revoir !"

5. Tests supplementaires :
   - test_tool_exec.py : tester chaque tool call avec ports mockes
   - test_scenarios.py : tester des conversations completes :
     * Patient veut un RDV jeudi → slots retournes → confirme jeudi 14h → booke
     * Patient annule son RDV de mardi → annule → propose vendredi → refuse → fin
     * Patient demande le tarif → repond 16.13 EUR → patient dit merci → fin
     * Patient demande "j'ai mal au dos que faire" → refuse → propose message → fin
```

### Agent FRONTEND

```
Lis le fichier CLAUDE.md a la racine du projet. Tu es l'AGENT FRONTEND.

TON PERIMETRE : frontend/
NE TOUCHE JAMAIS : backend/

TACHE J3 : Historique appels enrichi + dashboard minimal

1. Enrichir CallHistory.tsx avec des donnees reelles :
   - Connecter a GET /api/calls
   - Afficher les appels en temps quasi-reel (polling toutes les 30s
     ou rafraichissement manuel)
   - Pour chaque appel, afficher :
     * Date et heure
     * Numero appelant (masquer les 4 derniers chiffres : 06 12 XX XX)
     * Duree (formatee : "2min 34s")
     * Scenario (badge colore)
     * Resume court (1 ligne)
     * Score confiance STT (jauge)
   - Detail d'un appel (clic sur une ligne ou expand) :
     * Resume complet
     * Actions prises par l'agent
     * Flag urgent si applicable

2. Creer une page Dashboard minimaliste (frontend/src/pages/Dashboard.tsx) :
   - Compteurs : appels aujourd'hui, appels cette semaine, appels total
   - Repartition par scenario (petit bar chart ou compteurs colores)
   - Dernier appel traite (carte resumee)
   - Ajouter la route / → Dashboard dans le router

3. Ameliorer la navigation :
   - Sidebar : Dashboard, Configuration, Historique
   - Indicateur de page active
   - Header : nom du cabinet (charge depuis l'API) + logo Declio

4. Etat de connexion backend :
   - Au chargement, tester GET /api/cabinets
   - Si le backend ne repond pas, afficher un bandeau d'erreur :
     "Impossible de se connecter au serveur Declio"
   - Si OK, masquer le bandeau
```

---

## J4+J5 — Auth (Better Stack) + Persistence + Logging + Deploy

L'objectif est d'avoir le PoC complet, securise et deployable. Authentification via Better Stack,
persistence des appels en DB, logging structure, et deploiement.

### Architecture Auth — Better Stack
- Better Stack (https://betterstack.com) gere l'authentification utilisateur
- Flow : Frontend → Better Stack login → JWT/session token → API backend
- Le backend valide le token Better Stack sur chaque requete protegee
- Pages publiques : aucune (tout derriere auth)
- Le kine se connecte avec email/password via Better Stack

### Criteres de succes J4+J5
- [ ] L'utilisateur doit se connecter via Better Stack pour acceder au dashboard
- [ ] Les routes API sont protegees par un middleware auth
- [ ] Apres chaque appel, le kine recoit un SMS dans les 30 secondes
- [ ] Si un appel plante, le patient entend le fallback : "Je rencontre un souci technique..."
- [ ] Chaque appel est enregistre dans la DB avec : duree, scenario, actions, latences, score STT
- [ ] Les logs sont structures (JSON) et consultables
- [ ] Le PoC tourne sur un serveur distant accessible via URL publique
- [ ] Le front est deploye et connecte au backend de production
- [ ] Le systeme est stable sur 10 appels consecutifs sans crash

Voir les instructions J4+J5 combinées ci-dessous.

---

## J6 — Buffer + onboarding cabinet #1

### Criteres de succes
- [ ] Tous les bugs critiques trouves en J5 sont corriges
- [ ] Le cabinet #1 est configure (horaires, tarifs, Google Calendar connecte)
- [ ] Le numero Telnyx est relie au numero du cabinet via redirection d'appel
- [ ] Un appel test depuis le numero du cabinet → conversation fonctionnelle → SMS recu
- [ ] Le kine a compris comment lire ses SMS et consulter l'historique en ligne
- [ ] Le DPA (Data Processing Agreement) est signe

### Les 3 agents

```
J6 est un jour de correction et d'onboarding. Pas de nouvelles features.

Priorite absolue :
1. Corriger tout bug bloquant identifie en J5
2. Configurer le cabinet #1 dans le systeme
3. Faire un appel de demo avec le kine present
4. Documenter les problemes rencontres pour les cabinets #2 et #3

Pas de nouvelle architecture, pas de refactoring, pas de "tant qu'on y est".
```
