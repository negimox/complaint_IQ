from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Any
import json


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
    backend_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    return json.loads(v_stripped)
                except Exception:
                    pass
            return [i.strip() for i in v_stripped.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        return ["http://localhost:5173", "http://localhost:3000"]

    # Database (Supabase Postgres)
    database_url: str = ""

    # Groq LLM
    groq_api_key: str = ""
    groq_model_extract: str = "openai/gpt-oss-20b"
    groq_model_risk: str = "openai/gpt-oss-120b"


settings = Settings()
