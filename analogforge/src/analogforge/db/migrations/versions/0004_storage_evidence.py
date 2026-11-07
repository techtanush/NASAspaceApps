"""Forward schema stage 4: storage_evidence."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 4)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
