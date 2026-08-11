"""phase10_indexes

Revision ID: 482f88174e21
Revises: 2cee147e2014
Create Date: 2026-08-11 10:29:51.696829
"""
from typing import Sequence, Union
from alembic import op

revision: str = '482f88174e21'
down_revision: Union[str, None] = '2cee147e2014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_stitch_reports_user_created ON stitch_reports (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_user ON inventory (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_plots_user ON plots (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_user_status ON orders (user_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_barnyard_slots_user ON barnyard_slots (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_stitch_reports_user_created")
    op.execute("DROP INDEX IF EXISTS ix_inventory_user")
    op.execute("DROP INDEX IF EXISTS ix_plots_user")
    op.execute("DROP INDEX IF EXISTS ix_orders_user_status")
    op.execute("DROP INDEX IF EXISTS ix_barnyard_slots_user")
