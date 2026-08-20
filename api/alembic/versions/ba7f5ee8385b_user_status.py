"""user_status

Revision ID: ba7f5ee8385b
Revises: 33675add6709
Create Date: 2026-08-20 20:39:47.062601
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'ba7f5ee8385b'
down_revision: Union[str, None] = '33675add6709'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(), server_default='active', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('status')
