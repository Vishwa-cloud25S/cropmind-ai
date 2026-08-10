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

    # Phase 7 — intervention zones (rules documented in app/services/mapping.py)
    zone_severity_critical: float = 0.5  # visual-severity proxy >= this escalates risk one level

    # Phase 10 — auth, sessions, rate limiting (docs/04 §3.10, §3.11)
    auth_required: bool = True  # AUTH_REQUIRED=false exists only for fully-local trusted dev rigs
    jwt_secret_key: str | None = None  # placeholder/None => ephemeral per-boot secret (loud warning, tokens die on restart)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720  # 12 h access tokens; refresh tokens are a documented post-MVP item
    rate_limit_enabled: bool = True  # in-memory per-process buckets (single instance; Redis-class store post-MVP)
    rate_limit_auth_per_minute: int = 10  # /auth/register + /auth/login per IP — brute-force brake
    rate_limit_write_per_minute: int = 120  # all other mutating calls per IP

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
