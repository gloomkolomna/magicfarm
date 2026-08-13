"""barnyard_slot_cell_id

Revision ID: 6bd2f38dce6e
Revises: 9b72b796e7c8
Create Date: 2026-08-13 11:36:27.979563
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '6bd2f38dce6e'
down_revision: Union[str, None] = '9b72b796e7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('barnyard_slots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cell_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_barnyard_slot_cell', 'field_cells', ['cell_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('barnyard_slots', schema=None) as batch_op:
        batch_op.drop_constraint('fk_barnyard_slot_cell', type_='foreignkey')
        batch_op.drop_column('cell_id')
