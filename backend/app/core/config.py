"""Application settings — env-driven, no secrets in code (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://cropmind:cropmind-local-only@localhost:5432/cropmind"
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 25
    demo_mode: bool = True
    ml_config_dir: str | None = None  # default: repo-level ml/configs (see property)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_ml_config_dir(self) -> Path:
        """Shared ML configuration (taxonomy, model thresholds) lives at repo level."""
        if self.ml_config_dir:
            return Path(self.ml_config_dir)
        return Path(__file__).resolve().parents[3] / "ml" / "configs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
