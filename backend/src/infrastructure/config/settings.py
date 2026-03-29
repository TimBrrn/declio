from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telnyx
    telnyx_api_key: str = ""
    telnyx_phone_number: str = ""
    telnyx_sip_connection_id: str = ""

    # Mistral (STT + LLM + TTS)
    mistral_api_key: str = ""

    # Legacy providers (kept for fallback / transition)
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Google Calendar (legacy — replaced by internal calendar)
    google_calendar_id: str = ""
    google_service_account_file: str = ""

    # Database
    database_url: str = "sqlite:///declio.db"

    # Auth (Better Stack)
    betterstack_api_token: str = ""

    # Admin login
    admin_email: str = ""
    admin_password: str = ""

    # Cost tracking
    usd_to_eur: float = 0.92  # Override in .env if needed

    # Provider selection: "voxtral" (default) or legacy providers
    stt_provider: str = "voxtral"
    llm_provider: str = "mistral"
    tts_provider: str = "voxtral"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    stream_base_url: str = "wss://localhost:8000"
    cors_origins: str = "http://localhost:5173"  # comma-separated

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
