"""0005 revoked tokens (Phase 10).

Adds the revoked_tokens denylist: signing out writes the token's jti here and
every authenticated request checks it — logout is a real server-side
revocation, not client-side theatre.

Revision ID: 0005_revoked_tokens
Revises: 0004_simulation_runs
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_revoked_tokens"
down_revision = "0004_simulation_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_revoked_tokens_user_id", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
