"""0003 zone review bookkeeping (Phase 7).

Adds nullable review_note / reviewed_at to intervention_zones so a review carries
its evidence where humans read it (the audit log already records every transition;
these columns make the current state self-describing). Nullable → safe upgrade on
existing databases; downgrade drops them again.

Revision ID: 0003_zone_review_fields
Revises: 0002_farm_owner_nullable
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_zone_review_fields"
down_revision = "0002_farm_owner_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("intervention_zones") as batch:
        batch.add_column(sa.Column("review_note", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("intervention_zones") as batch:
        batch.drop_column("reviewed_at")
        batch.drop_column("review_note")
