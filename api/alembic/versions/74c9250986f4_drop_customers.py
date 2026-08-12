"""drop_customers

Revision ID: 74c9250986f4
Revises: 5004156e7382
Create Date: 2026-08-12 20:00:22.929004
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '74c9250986f4'
down_revision: Union[str, None] = '5004156e7382'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_customer_id', type_='foreignkey')
        batch_op.drop_column('customer_id')

    with op.batch_alter_table('order_templates', schema=None) as batch_op:
        batch_op.drop_constraint('fk_order_templates_customer_id', type_='foreignkey')
        batch_op.drop_column('customer_id')

    op.drop_table('customers')


def downgrade() -> None:
    op.create_table('customers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    with op.batch_alter_table('order_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_order_templates_customer_id', 'customers', ['customer_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_orders_customer_id', 'customers', ['customer_id'], ['id'], ondelete='SET NULL')
