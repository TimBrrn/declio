# Declio

Side-project en cours — assistant vocal IA qui gere les appels entrants d'un professionnel : prise de RDV, annulations, FAQ, et SMS recap apres chaque appel.

## Stack

- **Backend** : Python / FastAPI, SQLite, LangGraph
- **Telephonie** : Telnyx (appels + SMS)
- **IA** : Deepgram (STT), OpenAI GPT-4o (LLM), ElevenLabs (TTS)
- **Agenda** : Google Calendar API
- **Frontend** : React, Vite, Tailwind, TanStack Router/Query

## Structure

```
backend/
  src/
    domain/          # Logique metier, ports (interfaces)
    application/     # Use cases, orchestration LangGraph
    infrastructure/  # Adapters (Telnyx, Deepgram, OpenAI, ElevenLabs)
    api/             # Routes FastAPI, webhooks, WebSocket
  tests/
  prompts/           # Prompts systeme et scenarios
frontend/
  src/
    pages/           # Config, historique appels
    components/
    api/             # Client HTTP type
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "./backend[dev]"
cp .env.example .env  # remplir les cles API
python backend/scripts/seed_cabinet.py
uvicorn backend.src.api.main:app --reload

# frontend (autre terminal)
cd frontend && npm install && npm run dev
```

Backend sur `:8000`, frontend sur `:5173`.

Docker : `docker compose up --build` → `:80`.

## Tests

```bash
python -m pytest backend/tests/unit/ -v
```

## Env

Voir `.env.example`. Cles requises : Telnyx, Deepgram, OpenAI, ElevenLabs, Google Calendar.
