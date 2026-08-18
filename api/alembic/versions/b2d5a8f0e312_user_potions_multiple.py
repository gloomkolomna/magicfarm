"""user_potions_multiple

Revision ID: b2d5a8f0e312
Revises: a1c4f7e9d201
Create Date: 2026-08-18 21:11:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'b2d5a8f0e312'
down_revision: Union[str, None] = 'a1c4f7e9d201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user_potions', schema=None) as batch_op:
        batch_op.drop_constraint('uq_userpotion_user_recipe', type_='unique')


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM user_potions WHERE id NOT IN "
        "(SELECT MIN(id) FROM user_potions GROUP BY user_id, potion_recipe_id)"
    ))
    with op.batch_alter_table('user_potions', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_userpotion_user_recipe', ['user_id', 'potion_recipe_id'])
