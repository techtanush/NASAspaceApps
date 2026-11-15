"""Private immutable operator documents, reviewed context and exact scope pins."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 8)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
