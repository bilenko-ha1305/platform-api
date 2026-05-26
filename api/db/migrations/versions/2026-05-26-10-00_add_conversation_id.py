"""add_conversation_id_to_investigations.

Revision ID: 3f7e2a1d9b4c
Revises: b1d8a340d291
Create Date: 2026-05-26 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "3f7e2a1d9b4c"
down_revision = "b1d8a340d291"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add conversation_id to investigations."""
    op.add_column(
        "investigations",
        sa.Column("conversation_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_investigations_conversation_id",
        "investigations",
        ["conversation_id"],
    )


def downgrade() -> None:
    """Remove conversation_id from investigations."""
    op.drop_index("ix_investigations_conversation_id", table_name="investigations")
    op.drop_column("investigations", "conversation_id")
