"""phase11_ingredients_apothecary

Revision ID: 8924ec161fed
Revises: e8f1a2b3c4d5
Create Date: 2026-08-18 20:38:35.605105
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '8924ec161fed'
down_revision: Union[str, None] = 'e8f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ingredients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('user_ingredients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=False),
    sa.Column('qty', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'ingredient_id', name='uq_useringredient_user_ingredient')
    )


def downgrade() -> None:
    op.drop_table('user_ingredients')
    op.drop_table('ingredients')
