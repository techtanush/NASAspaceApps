"""Forward schema stage 7: immutability_rls."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 7)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
