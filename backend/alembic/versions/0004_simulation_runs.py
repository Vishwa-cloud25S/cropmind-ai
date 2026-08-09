"""0004 simulation runs (Phase 8).

Adds the simulation_runs table: every stored simulator run with verbatim params +
labelled result so savings figures stay reproducible and auditable.

Revision ID: 0004_simulation_runs
Revises: 0003_zone_review_fields
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_simulation_runs"
down_revision = "0003_zone_review_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_kind",
            sa.Enum("SPRAY_PLAN", name="simulation_kind", native_enum=False),
            nullable=False,
        ),
        sa.Column("field_id", sa.String(length=36), sa.ForeignKey("fields.id"), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_simulation_runs_field_id", "simulation_runs", ["field_id"])


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_field_id", table_name="simulation_runs")
    op.drop_table("simulation_runs")
