"""Forward schema stage 2: mission_rover_revisions."""

from alembic import op

from analogforge.db.schema import migrate_stage

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_stage(op.get_bind(), 2)


def downgrade() -> None:
    raise RuntimeError("Deployed-data downgrade unsupported; restore a verified backup")
