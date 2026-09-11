from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "ComplaintIQ API"
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "changeme"

    # CORS
    backend_cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database (Supabase Postgres)
    database_url: str = ""

    # Groq LLM
    groq_api_key: str = ""
    groq_model_extract: str = "gemma2-9b-it"
    groq_model_risk: str = "llama-3.3-70b-versatile"


settings = Settings()
