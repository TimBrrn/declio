from sqlmodel import Session

from backend.src.infrastructure.adapters.deepgram_stt import DeepgramSTTAdapter
from backend.src.infrastructure.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
from backend.src.infrastructure.adapters.telnyx_telephony import (
    TelnyxTelephonyAdapter,
)
from backend.src.infrastructure.persistence.database import engine

# Singleton adapters — instantiated once at module load
_telephony_adapter = TelnyxTelephonyAdapter()
_stt_adapter = DeepgramSTTAdapter()
_tts_adapter = ElevenLabsTTSAdapter()


def get_db_session():
    with Session(engine) as session:
        yield session


def get_telephony():
    return _telephony_adapter


def get_stt():
    return _stt_adapter


def get_tts():
    return _tts_adapter
