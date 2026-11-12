"""Forward schema stage 1: extensions_identity."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 1)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
