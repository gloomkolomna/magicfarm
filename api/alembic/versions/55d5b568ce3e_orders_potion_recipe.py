"""orders_potion_recipe

Revision ID: 55d5b568ce3e
Revises: 60dddf9c5f6b
Create Date: 2026-08-17 20:20:55.038065
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '55d5b568ce3e'
down_revision: Union[str, None] = '60dddf9c5f6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('potion_recipe_id', sa.Integer(), nullable=True))
        batch_op.alter_column('product_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_foreign_key('fk_orders_potion_recipe', 'potion_recipes', ['potion_recipe_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_potion_recipe', type_='foreignkey')
        batch_op.drop_column('potion_recipe_id')
        batch_op.alter_column('product_id',
               existing_type=sa.INTEGER(),
               nullable=False)
