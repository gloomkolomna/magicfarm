"""remedy recipe items plant source

Revision ID: 193bb603c6c5
Revises: f89acdeb8ed3
Create Date: 2026-08-19 14:22:08.899971
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '193bb603c6c5'
down_revision: Union[str, None] = 'f89acdeb8ed3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('remedy_recipe_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plant_id', sa.Integer(), nullable=True))
        batch_op.alter_column('ingredient_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_unique_constraint('uq_remedyrecipe_remedy_plant', ['remedy_id', 'plant_id'])
        batch_op.create_foreign_key('fk_remedyrecipe_plant', 'plants', ['plant_id'], ['id'], ondelete='CASCADE')
        batch_op.create_check_constraint('ck_remedyrecipe_single_source', '(ingredient_id IS NOT NULL AND plant_id IS NULL) OR (ingredient_id IS NULL AND plant_id IS NOT NULL)')


def downgrade() -> None:
    with op.batch_alter_table('remedy_recipe_items', schema=None) as batch_op:
        batch_op.drop_constraint('ck_remedyrecipe_single_source', type_='check')
        batch_op.drop_constraint('fk_remedyrecipe_plant', type_='foreignkey')
        batch_op.drop_constraint('uq_remedyrecipe_remedy_plant', type_='unique')
        batch_op.alter_column('ingredient_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('plant_id')
