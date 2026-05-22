"""use_pg_enums_for_plan_role.

Revision ID: 68e8fcfe3f4e
Revises: 873b1ff0e426
Create Date: 2026-05-22 10:35:13.380112

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "68e8fcfe3f4e"
down_revision = "873b1ff0e426"
branch_labels = None
depends_on = None

orgrole_enum = sa.Enum("admin", "member", name="orgrole")
plan_enum = sa.Enum("free", "solo", "studio", name="plan")


def upgrade() -> None:
    """Run the migration."""
    bind = op.get_bind()
    orgrole_enum.create(bind, checkfirst=True)
    plan_enum.create(bind, checkfirst=True)

    for table, col in [
        ("organization_invites", "role"),
        ("organization_members", "role"),
    ]:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {col} TYPE orgrole"
            f" USING {col}::text::orgrole"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT 'member'::orgrole")

    for table, col in [
        ("organizations", "plan"),
        ("users", "plan"),
    ]:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {col} TYPE plan"
            f" USING {col}::text::plan"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT 'free'::plan")


def downgrade() -> None:
    """Undo the migration."""
    for table, col in [
        ("users", "plan"),
        ("organizations", "plan"),
    ]:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE VARCHAR(20) USING {col}::text")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT 'free'")

    for table, col in [
        ("organization_members", "role"),
        ("organization_invites", "role"),
    ]:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE VARCHAR(20) USING {col}::text")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT 'member'")

    orgrole_enum.drop(op.get_bind(), checkfirst=True)
    plan_enum.drop(op.get_bind(), checkfirst=True)
