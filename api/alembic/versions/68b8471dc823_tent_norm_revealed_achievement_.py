"""tent_norm_revealed_achievement_production_product_source

Revision ID: 68b8471dc823
Revises: 5fb69855f8ef
Create Date: 2026-08-13 11:08:43.977010
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '68b8471dc823'
down_revision: Union[str, None] = '5fb69855f8ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('production_code', sa.String(), nullable=True))

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('animal_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pet_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_product_animal', 'animals', ['animal_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_product_pet', 'pets', ['pet_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('tent_builds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('norm_revealed', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('tent_builds', schema=None) as batch_op:
        batch_op.drop_column('norm_revealed')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('fk_product_pet', type_='foreignkey')
        batch_op.drop_constraint('fk_product_animal', type_='foreignkey')
        batch_op.drop_column('pet_id')
        batch_op.drop_column('animal_id')

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.drop_column('production_code')
