"""add_internal_plan.

Revision ID: c6444879865c
Revises: 27fcf9155065
Create Date: 2026-05-22 10:59:01.604165

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c6444879865c"
down_revision = "27fcf9155065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.execute("ALTER TYPE plan ADD VALUE IF NOT EXISTS 'internal'")


def downgrade() -> None:
    """Undo the migration."""
    # PostgreSQL does not support removing enum values; a full type rebuild would be needed.
    # Downgrade is intentionally a no-op — remove rows with plan='internal' before reverting.
    pass
