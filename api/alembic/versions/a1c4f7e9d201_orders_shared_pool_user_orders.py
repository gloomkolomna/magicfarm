"""orders_shared_pool_user_orders

Revision ID: a1c4f7e9d201
Revises: 48a0b1ea3146
Create Date: 2026-08-18 21:10:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'a1c4f7e9d201'
down_revision: Union[str, None] = '48a0b1ea3146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE orders SET status='open', user_id=NULL, fulfilled_by=NULL, fulfilled_at=NULL"
    ))
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('fulfilled_at')
        batch_op.drop_column('fulfilled_by')
        batch_op.drop_column('user_id')
    op.create_table('user_orders',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('taken_at', sa.DateTime(), nullable=False),
    sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
    sa.Column('reward_coins', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'order_id', name='uq_userorder_user_order')
    )


def downgrade() -> None:
    op.drop_table('user_orders')
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fulfilled_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fulfilled_at', sa.DateTime(), nullable=True))
