"""remedy_device_zone_col2_row2

Revision ID: 1ecc2026e7c1
Revises: d42d747ffdaf
Create Date: 2026-08-20 21:48:14.614024
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '1ecc2026e7c1'
down_revision: Union[str, None] = 'd42d747ffdaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('remedy_device_cells', schema=None) as batch_op:
        batch_op.add_column(sa.Column('col2', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('row2', sa.Integer(), nullable=False, server_default='0'))
    op.execute("UPDATE remedy_device_cells SET col2 = col, row2 = row")


def downgrade() -> None:
    with op.batch_alter_table('remedy_device_cells', schema=None) as batch_op:
        batch_op.drop_column('row2')
        batch_op.drop_column('col2')
