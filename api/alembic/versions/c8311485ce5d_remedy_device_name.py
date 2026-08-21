"""remedy_device_name

Revision ID: c8311485ce5d
Revises: 85e44831c7e8
Create Date: 2026-08-21 10:53:59.417674
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'c8311485ce5d'
down_revision: Union[str, None] = '85e44831c7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('remedy_device_cells', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('remedy_device_cells', schema=None) as batch_op:
        batch_op.drop_column('name')
