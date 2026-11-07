"""Forward schema stage 3: runs_jobs_events."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 3)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
