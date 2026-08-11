"""drop_blocked_cells

Revision ID: 0006_drop_blocked_cells
Revises: 0005_plant_stages
Create Date: 2026-08-09 02:00:00.000000
"""
from typing import Sequence, Union
from alembic import op


revision: str = '0006_drop_blocked_cells'
down_revision: Union[str, None] = '0005_plant_stages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE field_cells SET kind='empty' WHERE kind='blocked'")


def downgrade() -> None:
    pass
