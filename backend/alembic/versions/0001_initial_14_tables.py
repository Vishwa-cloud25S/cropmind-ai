"""Initial 14-table schema (docs/02-system-architecture §5).

Revision ID: 0001_initial_14_tables
Revises: None
Create Date: 2026-08-09

Explicit, frozen DDL mirroring backend/app/db/models.py — portable on SQLite and
PostgreSQL (string enums as CHECK constraints, GeoJSON as JSON, UUIDs as CHAR(36)).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_14_tables"
down_revision = None
branch_labels = None
depends_on = None

UUID = sa.String(36)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.Enum("FARMER", "AGRONOMIST", "ADMIN", name="user_role", native_enum=False), nullable=False, server_default="FARMER"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "farms",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("location", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_farms_owner_id", "farms", ["owner_id"])

    op.create_table(
        "fields",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("farm_id", UUID, sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("crop_id", sa.String(60)),
        sa.Column("boundary_geojson", sa.JSON),
        sa.Column("area_ha", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fields_farm_id", "fields", ["farm_id"])

    op.create_table(
        "images",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("field_id", UUID, sa.ForeignKey("fields.id")),
        sa.Column("uploader_id", UUID, sa.ForeignKey("users.id")),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("thumb_path", sa.String(500)),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("exif_json", sa.JSON),
        sa.Column("source_type", sa.Enum("SMARTPHONE", "DRONE", "DEMO", name="image_source", native_enum=False), nullable=False, server_default="SMARTPHONE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_images_field_id", "images", ["field_id"])
    op.create_index("ix_images_sha256", "images", ["sha256"], unique=True)

    op.create_table(
        "analyses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("image_id", UUID, sa.ForeignKey("images.id"), nullable=False),
        sa.Column("field_id", UUID, sa.ForeignKey("fields.id")),
        sa.Column("status", sa.Enum("QUEUED", "PROCESSING", "COMPLETED", "FAILED", name="analysis_status", native_enum=False), nullable=False, server_default="QUEUED"),
        sa.Column("requested_by", UUID, sa.ForeignKey("users.id")),
        sa.Column("demo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_analyses_image_id", "analyses", ["image_id"])
    op.create_index("ix_analyses_field_id", "analyses", ["field_id"])
    op.create_index("ix_analyses_status", "analyses", ["status"])

    op.create_table(
        "analysis_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("analysis_id", UUID, sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="job_status", native_enum=False), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(80)),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("error_json", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_analysis_jobs_analysis_id", "analysis_jobs", ["analysis_id"], unique=True)
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_index("ix_analysis_jobs_run_after", "analysis_jobs", ["run_after"])

    op.create_table(
        "model_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("dataset_version", sa.String(80)),
        sa.Column("threshold_version", sa.String(40)),
        sa.Column("checkpoint_uri", sa.String(500)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("eval_report_uri", sa.String(500)),
        sa.Column("demo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
    )

    op.create_table(
        "predictions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("analysis_id", UUID, sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("model_version_id", UUID, sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("status", sa.Enum("SUSPECTED", "INCONCLUSIVE", name="prediction_status", native_enum=False), nullable=False),
        sa.Column("crop", sa.String(60), nullable=False),
        sa.Column("condition", sa.String(120), nullable=False),
        sa.Column("condition_name", sa.String(160), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("band", sa.String(12)),
        sa.Column("uncertainty", sa.Float, nullable=False),
        sa.Column("severity", sa.Float),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("phrasing", sa.String(300), nullable=False),
        sa.Column("demo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("raw_json", sa.JSON, nullable=False),
        sa.Column("gradcam_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_predictions_analysis_id", "predictions", ["analysis_id"], unique=True)
    op.create_index("ix_predictions_model_version_id", "predictions", ["model_version_id"])
    op.create_index("ix_predictions_status", "predictions", ["status"])

    op.create_table(
        "detection_regions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("prediction_id", UUID, sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("geometry_geojson", sa.JSON, nullable=False),
        sa.Column("area_px", sa.Integer),
        sa.Column("confidence", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_detection_regions_prediction_id", "detection_regions", ["prediction_id"])

    op.create_table(
        "intervention_zones",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("analysis_id", UUID, sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("zone_geojson", sa.JSON, nullable=False),
        sa.Column("risk_level", sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level", native_enum=False), nullable=False),
        sa.Column("condition", sa.String(120), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("severity", sa.Float),
        sa.Column("est_area_ha", sa.Float),
        sa.Column("review_status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="review_status", native_enum=False), nullable=False, server_default="PENDING"),
        sa.Column("reviewer_id", UUID, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_intervention_zones_analysis_id", "intervention_zones", ["analysis_id"])

    op.create_table(
        "reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("analysis_id", UUID, sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("report_id", sa.String(40), nullable=False),
        sa.Column("pdf_path", sa.String(500), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_analysis_id", "reports", ["analysis_id"], unique=True)
    op.create_index("ix_reports_report_id", "reports", ["report_id"], unique=True)

    op.create_table(
        "feedback",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("analysis_id", UUID, sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id")),
        sa.Column("correctness", sa.Enum("YES", "NO", "NOT_SURE", name="correctness", native_enum=False), nullable=False),
        sa.Column("actual_condition", sa.String(120)),
        sa.Column("notes", sa.Text),
        sa.Column("image_quality", sa.Enum("GOOD", "BLURRY", "BAD_LIGHTING", "NOT_A_LEAF", name="image_quality", native_enum=False)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_analysis_id", "feedback", ["analysis_id"])

    op.create_table(
        "dataset_sources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("license_id", sa.String(40), nullable=False),
        sa.Column("license_url", sa.String(300)),
        sa.Column("image_count", sa.Integer),
        sa.Column("classes_json", sa.JSON),
        sa.Column("limitations", sa.Text),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_dataset_sources_name", "dataset_sources", ["name"])

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("ip", sa.String(64)),
        sa.Column("request_id", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    for table in (
        "audit_logs", "dataset_sources", "feedback", "reports", "intervention_zones",
        "detection_regions", "predictions", "model_versions", "analysis_jobs",
        "analyses", "images", "fields", "farms", "users",
    ):
        op.drop_table(table)
