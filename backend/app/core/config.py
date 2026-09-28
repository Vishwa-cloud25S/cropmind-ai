"""Application settings — env-driven, no secrets in code (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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

    # Phase 14 — AD-009: real-checkpoint delivery for the public deployment (see docs/02, docs/12 §8).
    # Weights are still never committed to git (AD-008). When MODEL_CHECKPOINT is unset and MODEL_URL is
    # set, the worker downloads the real checkpoint once (e.g. from a private Hugging Face model repo)
    # into the cache dir and serves it flagged demo=false — never a silent fallback to the sample model.
    model_url: str | None = None  # MODEL_URL — https URL of the checkpoint file (e.g. HF .../resolve/main/...)
    model_url_token: str | None = None  # MODEL_URL_TOKEN — Bearer token (secret; never logged, never exposed via API)
    model_url_sha256: str | None = None  # MODEL_URL_SHA256 — integrity pin; a mismatch fails loudly, never serves
    model_cache_dir: str | None = None  # MODEL_CACHE_DIR — default: "models-cache" next to the upload dir
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

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Hosts hand out bare ``postgres://`` or ``postgresql://`` URLs (Render, Supabase).
        The app pins the psycopg-3 driver — normalize instead of asking operators to
        hand-edit the pasted connection string."""
        for scheme in ("postgres://", "postgresql://"):
            if value.startswith(scheme):
                return "postgresql+psycopg://" + value[len(scheme) :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_ml_config_dir(self) -> Path:
        """Shared ML configuration (taxonomy, model thresholds) lives at repo level."""
        if self.ml_config_dir:
            return Path(self.ml_config_dir)
        return Path(__file__).resolve().parents[3] / "ml" / "configs"

    @property
    def resolved_model_cache_dir(self) -> Path:
        """Where remotely-delivered checkpoints land (AD-009). Defaults to a sibling
        of the upload dir so one mounted data volume covers both (Render: /data)."""
        if self.model_cache_dir:
            return Path(self.model_cache_dir)
        return Path(self.upload_dir).resolve().parent / "models-cache"


@lru_cache
def get_settings() -> Settings:
    return Settings()
