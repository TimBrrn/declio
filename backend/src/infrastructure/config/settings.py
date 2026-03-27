from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telnyx
    telnyx_api_key: str = ""
    telnyx_phone_number: str = ""
    telnyx_sip_connection_id: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # OpenAI
    openai_api_key: str = ""

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Google Calendar
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

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    stream_base_url: str = "wss://localhost:8000"
    cors_origins: str = "http://localhost:5173"  # comma-separated

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
