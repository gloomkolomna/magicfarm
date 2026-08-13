"""stitch_report_cell_id

Revision ID: 5caf20f6da17
Revises: 6bd2f38dce6e
Create Date: 2026-08-13 11:51:03.701627
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '5caf20f6da17'
down_revision: Union[str, None] = '6bd2f38dce6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('stitch_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cell_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_stitch_report_cell', 'field_cells', ['cell_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('stitch_reports', schema=None) as batch_op:
        batch_op.drop_constraint('fk_stitch_report_cell', type_='foreignkey')
        batch_op.drop_column('cell_id')
