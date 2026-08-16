"""order_customer_phrase

Revision ID: 27299be8c8a9
Revises: e28eae732232
Create Date: 2026-08-16 22:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '27299be8c8a9'
down_revision: Union[str, None] = 'e28eae732232'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_phrase', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('customer_phrase')
