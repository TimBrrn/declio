# Declio - Secretaire IA pour kinesitherapeutes

Agent vocal IA qui decroche les appels telephoniques a la place du kinesitherapeute, traite les demandes courantes (prise de RDV, annulations, FAQ tarifs/horaires), et envoie un SMS resume au praticien apres chaque appel.

**Statut :** PoC — validation produit avec des cabinets pilotes.

## Fonctionnalites

- Decroche automatique des appels entrants via numero dedie (+33)
- Conversation naturelle en francais (STT → LLM → TTS en streaming)
- Prise et annulation de rendez-vous sur Google Calendar
- Reponses FAQ (tarifs, horaires, adresse, documents a apporter)
- Refus poli des questions medicales avec proposition de rappel
- SMS resume envoye au praticien apres chaque appel
- Dashboard web : configuration cabinet, historique des appels, suivi des couts

## Architecture

Architecture hexagonale (ports & adapters) avec separation domaine / application / infrastructure.

```
Patient appelle
     |
     v
  Telnyx (telephonie + SMS)
     |
     v
  FastAPI (webhooks + WebSocket audio bidirectionnel)
     |
     +-- Deepgram STT (streaming temps reel)
     |
     +-- OpenAI GPT-4o + LangGraph (raisonnement + function calling)
     |
     +-- ElevenLabs TTS (voix francaise naturelle, streaming)
     |
     +-- Google Calendar API (lecture/ecriture RDV)
     |
     v
  SMS resume → kinesitherapeute
```

**Latence cible :** < 2 secondes entre fin de phrase patient et debut de reponse agent.

### Stack

| Brique | Techno |
|---|---|
| Serveur | Python / FastAPI |
| Telephonie + SMS | Telnyx |
| STT | Deepgram (streaming) |
| LLM | OpenAI GPT-4o + LangGraph |
| TTS | ElevenLabs |
| Agenda | Google Calendar API |
| DB | SQLite + SQLModel |
| Frontend | React + Vite + TanStack Router/Query + Tailwind |

### Structure du projet

```
declio/
├── backend/
│   ├── src/
│   │   ├── domain/          # Entities, value objects, ports (interfaces), services
│   │   ├── application/     # Use cases, LangGraph orchestration, prompts
│   │   ├── infrastructure/  # Adapters (Telnyx, Deepgram, OpenAI, ElevenLabs, Google Calendar)
│   │   └── api/             # FastAPI routes, webhooks, WebSocket, middleware
│   ├── tests/
│   └── prompts/             # System prompt + scenario prompts (booking, cancellation, FAQ)
├── frontend/
│   └── src/
│       ├── pages/           # CabinetConfig, CallHistory
│       ├── components/      # Shared UI components
│       └── api/             # Typed HTTP client
└── docker-compose.yml
```

## Installation

### Prerequis

- Python >= 3.11
- Node.js >= 18
- Comptes API : Telnyx, Deepgram, OpenAI, ElevenLabs, Google Cloud (Calendar API)

### Setup local

```bash
# 1. Cloner le repo
git clone https://github.com/TimBrrn/Declio.git
cd Declio

# 2. Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ./backend
pip install -e "./backend[dev]"

# 3. Configuration
cp .env.example .env
# Remplir les cles API dans .env

# 4. Initialiser la base de donnees (seed cabinet par defaut)
python backend/scripts/seed_cabinet.py

# 5. Lancer le backend
uvicorn backend.src.api.main:app --reload

# 6. Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev
```

Le frontend est accessible sur `http://localhost:5173`, le backend sur `http://localhost:8000`.

### Docker

```bash
cp .env.example .env
# Remplir les cles API dans .env
docker compose up --build
```

L'application est accessible sur `http://localhost:80`.

## Tests

```bash
source .venv/bin/activate
python -m pytest backend/tests/unit/ -v
```

## Variables d'environnement

Voir `.env.example` pour la liste complete. Les principales :

| Variable | Description |
|---|---|
| `TELNYX_API_KEY` | Cle API Telnyx (telephonie + SMS) |
| `TELNYX_PHONE_NUMBER` | Numero de telephone Telnyx (+33...) |
| `DEEPGRAM_API_KEY` | Cle API Deepgram (STT) |
| `OPENAI_API_KEY` | Cle API OpenAI (GPT-4o) |
| `ELEVENLABS_API_KEY` | Cle API ElevenLabs (TTS) |
| `ELEVENLABS_VOICE_ID` | ID de la voix ElevenLabs |
| `GOOGLE_CALENDAR_ID` | ID du calendrier Google |
| `ADMIN_EMAIL` | Email de connexion admin |
| `ADMIN_PASSWORD` | Mot de passe admin |
