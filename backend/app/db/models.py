"""ORM models — 14-table schema per docs/02-system-architecture §5 (Phase 5).

Portability rules (tests run on SQLite, production on PostgreSQL 16): no
dialect-specific column types — GeoJSON is JSON, enums are portable CHECK-string
enums, UUIDs are 36-char strings. Crops/diseases stay config-seeded
(ml/configs/taxonomy.yaml), not tables.

Geo honesty: `detection_regions.geometry_geojson` is IMAGE-SPACE (normalized
xyxy → polygon) produced by Grad-CAM regions — not geographic coordinates.
Field-level geo mapping is the FieldMappingProvider interface (docs/02 §8).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

_UUID = sa.String(36)
_JSON = sa.JSON


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Auth-ready (Phase 6 attaches endpooints); role: FARMER|AGRONOMIST|ADMIN."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(sa.String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(128))
    role: Mapped[str] = mapped_column(sa.Enum("FARMER", "AGRONOMIST", "ADMIN", name="user_role", native_enum=False), default="FARMER")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    farms: Mapped[list[Farm]] = relationship(back_populates="owner")


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    owner_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    location: Mapped[str | None] = mapped_column(sa.String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    owner: Mapped[User] = relationship(back_populates="farms")
    fields: Mapped[list[Field]] = relationship(back_populates="farm")


class Field(Base):
    """boundary_geojson: real geographic polygon (GeoJSON), stored as JSON."""

    __tablename__ = "fields"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    farm_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("farms.id"), index=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    crop_id: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)  # taxonomy crop_id, config-seeded
    boundary_geojson: Mapped[dict | None] = mapped_column(_JSON, nullable=True)  # GEOGRAPHIC GeoJSON
    area_ha: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    farm: Mapped[Farm] = relationship(back_populates="fields")
    images: Mapped[list[Image]] = relationship(back_populates="field")


class Image(Base):
    __tablename__ = "images"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    field_id: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("fields.id"), nullable=True, index=True)
    uploader_id: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("users.id"), nullable=True)
    path: Mapped[str] = mapped_column(sa.String(500))
    thumb_path: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    sha256: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    width: Mapped[int] = mapped_column(sa.Integer)
    height: Mapped[int] = mapped_column(sa.Integer)
    byte_size: Mapped[int] = mapped_column(sa.BigInteger)
    captured_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    exif_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(
        sa.Enum("SMARTPHONE", "DRONE", "DEMO", name="image_source", native_enum=False), default="SMARTPHONE"
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    field: Mapped[Field | None] = relationship(back_populates="images")
    analyses: Mapped[list[Analysis]] = relationship(back_populates="image")


class Analysis(Base):
    """API-facing status mirrors its job's transitions (worker-owned)."""

    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    image_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("images.id"), index=True)
    field_id: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("fields.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        sa.Enum("QUEUED", "PROCESSING", "COMPLETED", "FAILED", name="analysis_status", native_enum=False),
        default="QUEUED",
        index=True,
    )
    requested_by: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("users.id"), nullable=True)
    demo: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    image: Mapped[Image] = relationship(back_populates="analyses")
    job: Mapped[AnalysisJob | None] = relationship(back_populates="analysis", uselist=False)
    prediction: Mapped[Prediction | None] = relationship(back_populates="analysis", uselist=False)
    intervention_zones: Mapped[list[InterventionZone]] = relationship(back_populates="analysis")
    report: Mapped[Report | None] = relationship(back_populates="analysis", uselist=False)
    feedback_rows: Mapped[list[Feedback]] = relationship(back_populates="analysis")


class AnalysisJob(Base):
    """DB-backed queue row (ADR-004): polled by workers; interface-compatible with Celery/RQ."""

    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    analysis_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("analyses.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(
        sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="job_status", native_enum=False),
        default="PENDING",
        index=True,
    )
    attempts: Mapped[int] = mapped_column(sa.Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(sa.Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, index=True)
    locked_by: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="job")


class ModelVersion(Base):
    """Weights never in git (AD-008); this row records identity + hashes for audit."""

    __tablename__ = "model_versions"
    __table_args__ = (sa.UniqueConstraint("name", "version", name="uq_model_versions_name_version"),)
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(sa.String(120))
    version: Mapped[str] = mapped_column(sa.String(40))
    dataset_version: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    threshold_version: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    checkpoint_uri: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    sha256: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    eval_report_uri: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    demo: Mapped[bool] = mapped_column(sa.Boolean, default=False)  # sample-model identity is never silent
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    predictions: Mapped[list[Prediction]] = relationship(back_populates="model_version")


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    analysis_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("analyses.id"), unique=True, index=True)
    model_version_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("model_versions.id"), index=True)
    status: Mapped[str] = mapped_column(
        sa.Enum("SUSPECTED", "INCONCLUSIVE", name="prediction_status", native_enum=False), index=True
    )
    crop: Mapped[str] = mapped_column(sa.String(60))
    condition: Mapped[str] = mapped_column(sa.String(120))  # disease_id (taxonomy key)
    condition_name: Mapped[str] = mapped_column(sa.String(160))
    confidence: Mapped[float] = mapped_column(sa.Float)
    band: Mapped[str | None] = mapped_column(sa.String(12), nullable=True)  # HIGH|MEDIUM|LOW|None(INCONCLUSIVE)
    uncertainty: Mapped[float] = mapped_column(sa.Float)
    severity: Mapped[float | None] = mapped_column(sa.Float, nullable=True)  # visual proxy, labelled (raw_json)
    latency_ms: Mapped[float] = mapped_column(sa.Float)
    phrasing: Mapped[str] = mapped_column(sa.String(300))  # "Suspected {crop} - {name} - {x}% confidence"
    demo: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    raw_json: Mapped[dict] = mapped_column(_JSON)  # full predictor contract, verbatim
    gradcam_path: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    analysis: Mapped[Analysis] = relationship(back_populates="prediction")
    model_version: Mapped[ModelVersion] = relationship(back_populates="predictions")
    regions: Mapped[list[DetectionRegion]] = relationship(back_populates="prediction")


class DetectionRegion(Base):
    """IMAGE-SPACE region (normalized coords) — see module docstring; NOT geographic."""

    __tablename__ = "detection_regions"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    prediction_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("predictions.id"), index=True)
    geometry_geojson: Mapped[dict] = mapped_column(_JSON)  # image-space polygon, coordinate_space: normalized-xyxy
    area_px: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    prediction: Mapped[Prediction] = relationship(back_populates="regions")


class InterventionZone(Base):
    __tablename__ = "intervention_zones"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    analysis_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("analyses.id"), index=True)
    zone_geojson: Mapped[dict] = mapped_column(_JSON)
    risk_level: Mapped[str] = mapped_column(
        sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level", native_enum=False)
    )
    condition: Mapped[str] = mapped_column(sa.String(120))
    confidence: Mapped[float] = mapped_column(sa.Float)
    severity: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    est_area_ha: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    review_status: Mapped[str] = mapped_column(
        sa.Enum("PENDING", "APPROVED", "REJECTED", name="review_status", native_enum=False), default="PENDING"
    )
    reviewer_id: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    analysis: Mapped[Analysis] = relationship(back_populates="intervention_zones")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    analysis_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("analyses.id"), unique=True, index=True)
    report_id: Mapped[str] = mapped_column(sa.String(40), unique=True, index=True)  # human-facing, e.g. CMA-…
    pdf_path: Mapped[str] = mapped_column(sa.String(500))
    generated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    analysis: Mapped[Analysis] = relationship(back_populates="report")


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    analysis_id: Mapped[str] = mapped_column(_UUID, sa.ForeignKey("analyses.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("users.id"), nullable=True)
    correctness: Mapped[str] = mapped_column(sa.Enum("YES", "NO", "NOT_SURE", name="correctness", native_enum=False))
    actual_condition: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    image_quality: Mapped[str | None] = mapped_column(
        sa.Enum("GOOD", "BLURRY", "BAD_LIGHTING", "NOT_A_LEAF", name="image_quality", native_enum=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    analysis: Mapped[Analysis] = relationship(back_populates="feedback_rows")


class DatasetSource(Base):
    __tablename__ = "dataset_sources"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(sa.String(120), index=True)
    version: Mapped[str] = mapped_column(sa.String(80))
    source_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    license_id: Mapped[str] = mapped_column(sa.String(40))
    license_url: Mapped[str | None] = mapped_column(sa.String(300), nullable=True)
    image_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)  # null = not yet measured, never invented
    classes_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    limitations: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(_UUID, sa.ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(60), index=True)
    entity: Mapped[str] = mapped_column(sa.String(60))
    entity_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


ALL_TABLES = [
    "users", "farms", "fields", "images", "analyses", "analysis_jobs", "model_versions",
    "predictions", "detection_regions", "intervention_zones", "reports", "feedback",
    "dataset_sources", "audit_logs",
]
