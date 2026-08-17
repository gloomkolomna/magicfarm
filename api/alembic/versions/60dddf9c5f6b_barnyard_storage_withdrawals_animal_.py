"""barnyard_storage_withdrawals_animal_product_norm

Revision ID: 60dddf9c5f6b
Revises: 5179db83e1ed
Create Date: 2026-08-17 19:59:27.797797
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '60dddf9c5f6b'
down_revision: Union[str, None] = '5179db83e1ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('barnyard_storage',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('qty', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'product_id', name='uq_barnyard_storage_user_product')
    )
    op.create_table('barnyard_withdrawals',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('qty', sa.Integer(), nullable=False),
    sa.Column('required', sa.Integer(), server_default='0', nullable=False),
    sa.Column('status', sa.String(), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('animal_product_norm', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('animal_product_norm')

    op.drop_table('barnyard_withdrawals')
    op.drop_table('barnyard_storage')
