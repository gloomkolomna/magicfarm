"""payment_order_kind_dlc_topup

Revision ID: 9f10289c3259
Revises: 6a74c0b26e2c
Create Date: 2026-08-24 13:10:23.758373
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '9f10289c3259'
down_revision: Union[str, None] = '6a74c0b26e2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect

    insp = inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('payment_orders')}
    if 'kind' not in cols:
        with op.batch_alter_table('payment_orders', schema=None) as batch_op:
            batch_op.add_column(sa.Column('kind', sa.String(), server_default='subscription', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('payment_orders', schema=None) as batch_op:
        batch_op.drop_column('kind')
