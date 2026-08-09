"""farms.owner_id becomes nullable (pre-auth Phase 6 farms/fields CRUD).

The Phase 5 schema made owner_id NOT NULL, but user accounts don't exist until
Phase 10 wires JWT auth — farms CRUD (Phase 6 UI) would violate the FK on every
create. Phase 10 backfills owners and restores the constraint with real users.

Revision ID: 0002_farm_owner_nullable
Revises: 0001_initial_14_tables
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_farm_owner_nullable"
down_revision = "0001_initial_14_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("farms") as batch_op:  # batch mode: works on SQLite too
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("farms") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=False)
