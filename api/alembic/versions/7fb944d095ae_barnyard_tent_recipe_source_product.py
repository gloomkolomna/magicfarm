"""barnyard_tent_recipe_source_product

Revision ID: 7fb944d095ae
Revises: 465cbd8deff0
Create Date: 2026-08-15 10:18:50.320139
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '7fb944d095ae'
down_revision: Union[str, None] = '465cbd8deff0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('craft_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_product_id', sa.Integer(), nullable=True))
        batch_op.alter_column('plant_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_foreign_key('fk_craft_sessions_source_product', 'products', ['source_product_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_product_id', sa.Integer(), nullable=True))
        batch_op.alter_column('plant_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_unique_constraint('uq_recipe_source_product', ['source_product_id'])
        batch_op.create_foreign_key('fk_recipes_source_product', 'products', ['source_product_id'], ['id'], ondelete='CASCADE')

    op.execute(
        "INSERT INTO production_templates (code, name, emoji, required, cards_to_draw, surcharge) "
        "SELECT 'barnyard', 'Шатёр скотного двора', '🏚️', 500, 2, 30 "
        "WHERE NOT EXISTS (SELECT 1 FROM production_templates WHERE code = 'barnyard')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM production_templates WHERE code = 'barnyard'")

    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_recipes_source_product', type_='foreignkey')
        batch_op.drop_constraint('uq_recipe_source_product', type_='unique')
        batch_op.alter_column('plant_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('source_product_id')

    with op.batch_alter_table('craft_sessions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_craft_sessions_source_product', type_='foreignkey')
        batch_op.alter_column('plant_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('source_product_id')
