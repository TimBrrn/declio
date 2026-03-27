# Declio — PoC Secretaire IA pour kinesitherapeutes

## Projet

Agent IA vocal qui decroche les appels telephoniques a la place du kine, traite les demandes courantes (RDV, annulations, FAQ), et envoie un SMS resume au praticien apres chaque appel.

**Phase :** PoC — validation produit avec 3 cabinets pilotes
**Objectif :** valider que les kines trouvent ca utile et sont prets a payer 99 EUR/mois

---

## Stack technique

| Brique | Techno | Justification |
|---|---|---|
| Serveur | **Python / FastAPI** | SDKs IA matures (Deepgram, OpenAI, ElevenLabs), async natif, WebSocket support, DI integre via Depends() |
| Telephonie | **Telnyx** | Numeros francais +33, WebSocket audio bidirectionnel, SMS integre, moins cher que Twilio |
| STT | **Deepgram** | Streaming temps reel (pas d'attente fin de phrase), meilleure latence que Whisper en live, bon francais |
| LLM | **OpenAI GPT-4o + LangGraph** | GPT-4o pour le raisonnement et function calling. LangGraph pour orchestrer la conversation comme un graphe d'etats explicite (listen → think → tool_call → respond). Plus lisible et debuggable qu'une boucle while/if manuelle. |
| TTS | **ElevenLabs** | Voix francaise naturelle, streaming audio chunk par chunk, qualite superieure aux alternatives |
| Agenda | **Google Calendar API** | Gratuit, OAuth standard, les kines liberaux utilisent souvent Google |
| SMS | **Telnyx SMS** | Deja dans la stack telephonie, evite un provider supplementaire |
| DB | **SQLite + SQLModel** | Zero ops (fichier unique), Pydantic + SQLAlchemy integre, suffisant pour 3 cabinets. Migration PostgreSQL en v1 |
| Frontend | **React + Vite + Tailwind** | SPA moderne, build rapide (Vite), UI propre (Tailwind), separation nette front/back |

---

## Architecture : Hexagonale / DDD

### Pourquoi l'hexagonale

1. **Multi-agent dev** : les ports (interfaces) definissent des contrats clairs entre agents. Chaque agent travaille dans son dossier sans conflit.
2. **Testabilite** : le domaine (logique metier) est pur Python, testable sans appeler les APIs externes.
3. **Swappabilite** : changer Deepgram pour Whisper = 1 nouveau adapter, zero changement dans le domaine.

### Couches et dependances

```
  FRONTEND (React)
       │ HTTP REST
       ▼
  API (FastAPI) ──────────────────────────┐
       │                                   │
       ▼                                   ▼
  APPLICATION (use cases) ──────▶  INFRASTRUCTURE (adapters)
       │                                   │
       ▼                                   │
  DOMAIN (entities, ports, services) ◀─────┘
       │
       ▼
  RIEN — le domaine n'importe aucun package externe

  REGLE : toutes les fleches pointent VERS le domaine.
  L'infra depend du domaine (via les ports), JAMAIS l'inverse.
```

### Domaine

Le domaine contient les regles metier pures, independantes de toute technologie :

- **Entities** : Cabinet, Appointment, CallRecord
- **Value Objects** : TimeSlot, PhoneNumber, CallSummary, PatientContact
- **Services** : AppointmentScheduler (trouver creneaux, verifier conflits), CallProcessor (detecter scenario, router)
- **Ports** (interfaces) : CalendarPort, TelephonyPort, STTPort, TTSPort, ConversationPort, NotificationPort

Les ports sont des `Protocol` Python — ils definissent "ce dont le domaine a besoin" sans savoir "qui le fournit."

### Adapters (infrastructure)

Chaque port a un adapter concret qui parle a une API externe :

```
PORT (interface)          ADAPTER (implementation)
CalendarPort         →    GoogleCalendarAdapter
TelephonyPort        →    TelnyxTelephonyAdapter
STTPort              →    DeepgramSTTAdapter
TTSPort              →    ElevenLabsTTSAdapter
ConversationPort     →    OpenAIConversationAdapter
NotificationPort     →    TelnyxSMSAdapter
```

### Injection de dependances

FastAPI Depends() natif — zero librairie en plus. Au demarrage de l'app, des fonctions provider instancient les adapters et les injectent dans les use cases.

```python
# backend/src/api/dependencies.py
def get_calendar() -> CalendarPort:
    return GoogleCalendarAdapter(settings.google_credentials)

# backend/src/api/routes/cabinets.py
@router.post("/book")
def book(calendar: CalendarPort = Depends(get_calendar)):
    BookAppointment(calendar).execute(...)
```

---

## Pipeline audio temps reel

Le streaming est bout-en-bout pour minimiser la latence :

```
Patient parle
    │
    ├── Deepgram STT (streaming, pas d'attente fin de phrase) : ~300-500ms
    │
    ├── OpenAI GPT-4o (streaming, phrase par phrase) : ~500-1500ms
    │
    ├── ElevenLabs TTS (streaming, chunk par chunk) : ~300-500ms
    │
    └── Latence percue : ~1-1.5s (le patient entend le debut avant que la fin soit generee)
```

**Barge-in :** quand le patient parle pendant que l'agent parle, Deepgram detecte la voix → le serveur coupe le flux TTS → ecoute le patient.

**Latence cible :** < 2 secondes entre fin de phrase patient et debut de reponse agent.

---

## Orchestration conversationnelle — LangGraph

La conversation telephonique est modelisee comme un graphe d'etats LangGraph :

```
                    ┌──────────────┐
                    │   GREETING   │  Message d'accueil du cabinet
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌────▶│   LISTENING   │◀────────────────────┐
              │     └──────┬───────┘                      │
              │            │ transcription recue           │
              │     ┌──────▼───────┐                      │
              │     │   THINKING   │  LLM analyse +       │
              │     │              │  detect scenario      │
              │     └──────┬───────┘                      │
              │            │                              │
              │     ┌──────▼───────┐      ┌───────────┐  │
              │     │  TOOL_CALL   │─────▶│ TOOL_EXEC │  │
              │     │ (si besoin)  │      │ Calendar/  │  │
              │     └──────────────┘      │ SMS/etc    │  │
              │                           └─────┬─────┘  │
              │                                 │        │
              │     ┌──────▼───────┐            │        │
              │     │  RESPONDING  │◀───────────┘        │
              │     │  (TTS stream)│                     │
              │     └──────┬───────┘                     │
              │            │                              │
              │            ├── patient repond ────────────┘
              │            │
              │     ┌──────▼───────┐
              │     │   HANGUP     │  Fin de conversation
              │     └──────┬───────┘
              │            │
              │     ┌──────▼───────┐
              └─────│   SUMMARY    │  SMS resume au kine
                    └──────────────┘
```

Les etats du graphe :
- **GREETING** : joue le message d'accueil TTS, passe a LISTENING
- **LISTENING** : attend la transcription STT du patient
- **THINKING** : le LLM analyse la transcription, detecte le scenario, decide s'il faut appeler un tool
- **TOOL_CALL** : appelle un tool (Google Calendar, etc.) via function calling
- **TOOL_EXEC** : execute le tool et retourne le resultat au LLM
- **RESPONDING** : genere la reponse TTS en streaming vers le patient
- **HANGUP** : detecte la fin de conversation, raccroche
- **SUMMARY** : construit et envoie le SMS resume au kine

Le barge-in est gere par une transition RESPONDING → LISTENING quand Deepgram detecte la voix du patient.

Dependencies : `langgraph`, `langchain-openai`, `langchain-core`

---

## Structure du monorepo

```
declio/
├── CLAUDE.md                                # Ce fichier
├── .gitignore
├── .env.example
│
├── backend/                                 # Python / FastAPI
│   ├── pyproject.toml
│   ├── src/
│   │   ├── domain/                          # ── AGENT LLM ──
│   │   │   ├── entities/
│   │   │   │   ├── cabinet.py               # Dataclass: nom, adresse, tarifs, horaires
│   │   │   │   ├── appointment.py           # Dataclass: date, patient, duree, status
│   │   │   │   └── call_record.py           # Dataclass: duree, resume, actions, scores
│   │   │   ├── value_objects/
│   │   │   │   ├── time_slot.py             # Immutable: start, end, duration
│   │   │   │   ├── phone_number.py          # Validated: format FR
│   │   │   │   ├── call_summary.py          # Immutable: patient, type, action, urgent
│   │   │   │   └── patient_contact.py       # Immutable: nom, telephone
│   │   │   ├── ports/
│   │   │   │   ├── calendar_port.py         # Protocol: get_slots, book, cancel
│   │   │   │   ├── telephony_port.py        # Protocol: answer, stream_audio, hangup
│   │   │   │   ├── stt_port.py              # Protocol: transcribe_stream
│   │   │   │   ├── tts_port.py              # Protocol: synthesize_stream
│   │   │   │   ├── conversation_port.py     # Protocol: chat_stream (avec fn calling)
│   │   │   │   └── notification_port.py     # Protocol: send_sms
│   │   │   └── services/
│   │   │       ├── appointment_scheduler.py # Logique pure: trouver creneaux, verifier conflits
│   │   │       └── call_processor.py        # Logique pure: detecter scenario, router
│   │   │
│   │   ├── application/                     # ── AGENT LLM ──
│   │   │   ├── graph/
│   │   │   │   ├── call_graph.py            # LangGraph StateGraph definition
│   │   │   │   ├── state.py                 # CallState TypedDict (conversation state)
│   │   │   │   └── nodes/
│   │   │   │       ├── greeting.py          # Noeud GREETING : message d'accueil
│   │   │   │       ├── listening.py         # Noeud LISTENING : attente transcription
│   │   │   │       ├── thinking.py          # Noeud THINKING : LLM analyse + routing
│   │   │   │       ├── tool_exec.py         # Noeud TOOL_EXEC : execute tool calls
│   │   │   │       ├── responding.py        # Noeud RESPONDING : TTS streaming
│   │   │   │       └── summary.py           # Noeud SUMMARY : SMS resume au kine
│   │   │   └── use_cases/
│   │   │       ├── book_appointment.py      # Lecture creneaux → proposition → confirmation
│   │   │       ├── cancel_appointment.py    # Identification → suppression → re-proposition
│   │   │       ├── answer_faq.py            # Reponse depuis config cabinet
│   │   │       └── send_call_summary.py     # Construit le resume → SMS au kine
│   │   │
│   │   ├── infrastructure/                  # ── AGENT BACKEND ──
│   │   │   ├── adapters/
│   │   │   │   ├── telnyx_telephony.py      # TelephonyPort → Telnyx WebSocket
│   │   │   │   ├── deepgram_stt.py          # STTPort → Deepgram streaming
│   │   │   │   ├── elevenlabs_tts.py        # TTSPort → ElevenLabs streaming
│   │   │   │   ├── openai_conversation.py   # ConversationPort → GPT-4o streaming
│   │   │   │   ├── google_calendar.py       # CalendarPort → Google Calendar API
│   │   │   │   └── telnyx_sms.py            # NotificationPort → Telnyx SMS API
│   │   │   ├── audio/
│   │   │   │   ├── pipeline.py              # Orchestration streaming STT→LLM→TTS
│   │   │   │   └── barge_in.py              # Detection interruption patient
│   │   │   ├── persistence/
│   │   │   │   ├── database.py              # SQLite engine + session factory
│   │   │   │   └── models.py               # SQLModel tables
│   │   │   └── config/
│   │   │       └── settings.py              # Pydantic Settings (.env loading)
│   │   │
│   │   └── api/                             # ── AGENT BACKEND ──
│   │       ├── main.py                      # FastAPI app + startup + DI wiring
│   │       ├── dependencies.py              # Depends() providers pour les ports
│   │       ├── webhooks/
│   │       │   └── telnyx_webhook.py        # POST /webhooks/telnyx
│   │       └── routes/
│   │           ├── cabinets.py              # CRUD /api/cabinets
│   │           └── calls.py                 # GET /api/calls
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── domain/                      # Tests purs Python, zero mock externe
│   │   │   └── application/                 # Tests use cases avec ports mockes
│   │   └── integration/
│   │       └── adapters/                    # Tests avec APIs sandbox (optionnel PoC)
│   │
│   └── prompts/                             # ── AGENT LLM ──
│       ├── system_prompt.md                 # Prompt systeme agent vocal
│       └── scenarios/
│           ├── booking.md
│           ├── cancellation.md
│           └── faq.md
│
└── frontend/                                # ── AGENT FRONTEND ──
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── api/
        │   └── client.ts                   # Client HTTP vers le backend
        ├── pages/
        │   ├── CabinetConfig.tsx            # Formulaire config cabinet
        │   └── CallHistory.tsx              # Tableau historique appels
        └── components/
```

---

## Developpement multi-agent

3 agents Claude travaillent en parallele. Chaque agent a un perimetre exclusif.

### Agent BACKEND

**Owns :** `backend/src/infrastructure/`, `backend/src/api/`
**Responsabilites :**
- Adapters Telnyx (telephonie + SMS), Deepgram (STT), ElevenLabs (TTS)
- Pipeline audio streaming (orchestration, barge-in)
- API FastAPI (webhooks, routes CRUD, DI wiring)
- Persistence SQLite/SQLModel
- Configuration (.env, settings)
- Deploiement

**Ne touche JAMAIS :** `domain/`, `application/`, `prompts/`, `frontend/`

### Agent LLM

**Owns :** `backend/src/domain/`, `backend/src/application/`, `backend/prompts/`
**Responsabilites :**
- Entities, value objects, ports (interfaces)
- Domain services (AppointmentScheduler, CallProcessor)
- Use cases (HandleIncomingCall, BookAppointment, etc.)
- Prompts systeme et scenarios
- Adapter OpenAI (ConversationPort) — exception car intimement lie a la logique LLM
- Adapter Google Calendar (CalendarPort) — exception car c'est un tool du LLM
- Tests unitaires domain + application

**Ne touche JAMAIS :** `infrastructure/audio/`, `infrastructure/persistence/`, `api/`, `frontend/`

### Agent FRONTEND

**Owns :** `frontend/`
**Responsabilites :**
- Interface React config cabinet (CRUD)
- Interface historique appels (lecture)
- Client HTTP vers les routes API du backend
- UI/UX avec Tailwind

**Ne touche JAMAIS :** `backend/`

### Contrat entre agents

Les **ports** (`backend/src/domain/ports/`) sont le contrat. L'agent LLM definit les interfaces, l'agent backend les implemente. Si un port change, les deux agents doivent se synchroniser.

Les **routes API** (`backend/src/api/routes/`) sont le contrat front/back. L'agent backend expose les endpoints, l'agent frontend les consomme. Le contrat est documente dans les schemas Pydantic des routes.

---

## Scenarios couverts par le PoC

1. **Prise de RDV** — lire creneaux Google Calendar, proposer 2-3 options, confirmer, ecrire dans Calendar
2. **Annulation de RDV** — identifier le RDV, supprimer, proposer un nouveau creneau
3. **FAQ tarifs** — tarif seance, remboursement, modes de paiement (donnees en config)
4. **FAQ pratique** — adresse, horaires, parking, documents a apporter (donnees en config)
5. **Hors perimetre** — refus poli des questions medicales, proposition de laisser un message

---

## Gestion des erreurs

**Fallback universel :** si une erreur survient a n'importe quelle etape du pipeline, l'agent dit :
> "Je rencontre un petit souci technique. Puis-je prendre votre nom et numero pour que le cabinet vous rappelle ?"
Puis envoie un SMS au kine avec le contexte.

**Exception critique :** si l'envoi SMS au kine echoue, retenter 1 fois apres 30s. Si echec persistant, logger en critique et afficher dans l'historique appels du front.

**Reconnexion WebSocket :** si la connexion Deepgram ou ElevenLabs se coupe en cours d'appel, tenter 1 reconnexion silencieuse. Si echec, basculer sur le fallback universel.

---

## Tests

**Niveau :** domaine + application (pas d'integration adapters pour le PoC).

**Tests unitaires domaine (~10) :**
- AppointmentScheduler: find_available_slots, book happy path, book conflit, cancel
- CallProcessor: detect chaque scenario (RDV, annulation, FAQ, hors perimetre, ambigu)
- CallSummary: build format SMS

**Tests unitaires application (~5) :**
- HandleIncomingCall: routing vers le bon use case
- BookAppointment: happy path avec port mocke, pas de creneau
- CancelAppointment: happy path, RDV introuvable
- Fallback universel: erreur → message + SMS

**Framework :** pytest

---

## Regles de dev

- **Architecture hexagonale stricte** : le domaine n'importe JAMAIS de package externe
- **Ports = Protocol Python** : utiliser `typing.Protocol` pour les interfaces
- **Type hints partout** : mypy strict sur domain/ et application/
- **Logger chaque appel** : timestamp, numero, duree, scenario, actions, latences, score confiance STT
- **Ne jamais stocker d'enregistrement audio** au-dela de la transcription en cours
- **Message d'information obligatoire** en debut d'appel : "Cet appel est traite par un assistant virtuel"
- **Cles API dans .env** jamais dans le code
- **Prompts en fichiers Markdown** dans `prompts/`, jamais inline dans le Python
- **Un commit = un changement logique** avec message clair

---

## Hors perimetre PoC

Rappels 48h, test multi-operateurs, 99% uptime monitoring, detection auto disponibilite, mode debug rejeu, reecoute audio, multi-praticiens, HDS certification, WhatsApp, Doctolib, app mobile, CI/CD, auth login front, generation auto types TS, PostgreSQL.

---

## Planning

| Jour | Agent Backend | Agent LLM | Agent Frontend |
|---|---|---|---|
| J1 | Telnyx telephonie + WebSocket + decroché | Entities, value objects, ports (interfaces) | Setup React+Vite+Tailwind, layout |
| J2 | Deepgram STT adapter + ElevenLabs TTS adapter | Domain services + use cases | Page config cabinet (formulaire) |
| J3 | Pipeline streaming + barge-in | OpenAI adapter + function calling + prompts | Page historique appels |
| J4 | API routes CRUD + webhook + SMS adapter | Google Calendar adapter + tests unitaires | Client HTTP + integration API |
| J5 | Integration bout-en-bout + deploiement | Tests application + polish prompts | Polish UI + tests manuels |
| J6 | Buffer / debug / onboarding cabinet #1 | Iteration prompts apres premiers tests | Corrections post-test |
