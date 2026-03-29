import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Field, SQLModel


class CabinetModel(SQLModel, table=True):
    __tablename__ = "cabinets"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    nom_cabinet: str
    nom_praticien: str = ""
    adresse: str = ""
    telephone: str = ""
    horaires_json: str = "{}"  # JSON: {"lundi": ["09:00-12:00", "14:00-18:00"], ...}
    tarifs_json: str = "{}"  # JSON: {"seance": 50.0, ...}
    google_calendar_id: str = ""
    numero_sms_kine: str = ""
    message_accueil: str = ""
    faq_json: str = "{}"  # JSON: {"question_key": "reponse", ...}
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def horaires(self) -> dict[str, list[str]]:
        return json.loads(self.horaires_json)

    @horaires.setter
    def horaires(self, value: dict[str, list[str]]) -> None:
        self.horaires_json = json.dumps(value, ensure_ascii=False)

    @property
    def tarifs(self) -> dict[str, float]:
        return json.loads(self.tarifs_json)

    @tarifs.setter
    def tarifs(self, value: dict[str, float]) -> None:
        self.tarifs_json = json.dumps(value, ensure_ascii=False)

    @property
    def faq(self) -> dict[str, str]:
        return json.loads(self.faq_json)

    @faq.setter
    def faq(self, value: dict[str, str]) -> None:
        self.faq_json = json.dumps(value, ensure_ascii=False)

    def to_domain_dict(self) -> dict[str, Any]:
        """Return a dict compatible with the domain Cabinet dataclass."""
        return {
            "id": self.id,
            "nom_cabinet": self.nom_cabinet,
            "nom_praticien": self.nom_praticien,
            "adresse": self.adresse,
            "telephone": self.telephone,
            "horaires": self.horaires,
            "tarifs": self.tarifs,
            "google_calendar_id": self.google_calendar_id,
            "numero_sms_kine": self.numero_sms_kine,
            "message_accueil": self.message_accueil,
            "faq": self.faq,
        }


class PatientModel(SQLModel, table=True):
    __tablename__ = "patients"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    cabinet_id: str = Field(foreign_key="cabinets.id")
    nom: str = ""
    telephone: str = ""
    email: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AppointmentModel(SQLModel, table=True):
    __tablename__ = "appointments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    cabinet_id: str = Field(foreign_key="cabinets.id")
    patient_id: str | None = Field(default=None, foreign_key="patients.id")
    patient_nom: str = ""
    patient_telephone: str = ""
    date_heure: datetime
    duree_minutes: int = 30
    status: str = "confirmed"  # confirmed, cancelled, completed
    source: str = "manual"  # manual, ai_call
    google_event_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CallRecordModel(SQLModel, table=True):
    __tablename__ = "call_records"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    cabinet_id: str = Field(foreign_key="cabinets.id")
    caller_number: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    duration_seconds: int = 0
    scenario: str = ""  # booking, cancellation, faq_tarifs, faq_pratique, hors_perimetre
    summary: str = ""
    actions_taken: str = ""  # JSON string
    stt_confidence: float = 0.0
    transcript_json: str = "[]"  # JSON: [{"role":"assistant","content":"...","timestamp":"..."},...]
    sms_sent: bool = False
    telnyx_call_id: str = ""

    # Structured patient data
    patient_name: str = ""
    patient_message: str = ""  # From leave_message tool
    error_detail: str = ""  # Error message if call errored

    # Cost tracking
    total_cost_usd: float = 0.0
    total_cost_eur: float = 0.0
    llm_cost_usd: float = 0.0
    stt_cost_usd: float = 0.0
    tts_cost_usd: float = 0.0
    tts_chars_total: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0


class ApiUsageModel(SQLModel, table=True):
    __tablename__ = "api_usage"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    call_record_id: str = Field(foreign_key="call_records.id", index=True)
    service: str = ""  # "llm", "stt", "tts"
    turn_index: int = 0  # LLM turn number; 0 for stt/tts summary rows
    prompt_tokens: int = 0  # LLM only
    completion_tokens: int = 0  # LLM only
    total_tokens: int = 0  # LLM only
    cost_usd: float = 0.0
    model: str = ""  # "gpt-4o", "nova-2", "eleven_multilingual_v2"
    tool_name: str | None = None  # LLM only — multiple joined with "+"
    chars: int = 0  # TTS only
    duration_seconds: float = 0.0  # STT only
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
