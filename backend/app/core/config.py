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

    # Phase 5 — uploads pipeline
    upload_max_side: int = 2048  # stored normalized copy, longest edge px
    upload_thumb_side: int = 384  # thumbnail longest edge px

    # Phase 5 — analysis worker (worker process only; API never imports torch)
    model_checkpoint: str | None = None  # MODEL_CHECKPOINT; unset => clearly-flagged DEMO sample model
    worker_poll_interval_s: float = 2.0
    job_max_attempts: int = 3
    job_heartbeat_timeout_s: int = 120  # RUNNING job silent longer than this => retried/failed
    job_retry_backoff_s: float = 10.0  # run_after = now + attempts^2 * backoff

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
