"""brewery_zones_field_potion_recipes

Revision ID: 2a78a22e8347
Revises: 70c66a045f31
Create Date: 2026-08-16 10:41:18.461283
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '2a78a22e8347'
down_revision: Union[str, None] = '70c66a045f31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('brewery_zones',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('zone_kind', sa.String(), nullable=False),
    sa.Column('col1', sa.Integer(), nullable=False),
    sa.Column('row1', sa.Integer(), nullable=False),
    sa.Column('col2', sa.Integer(), nullable=False),
    sa.Column('row2', sa.Integer(), nullable=False),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.Column('recipe_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['potion_recipes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('field_potion_recipes',
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['potion_recipes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('field_id', 'recipe_id')
    )
    with op.batch_alter_table('potion_recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('card_image_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('potion_recipes', schema=None) as batch_op:
        batch_op.drop_column('card_image_url')

    op.drop_table('field_potion_recipes')
    op.drop_table('brewery_zones')
