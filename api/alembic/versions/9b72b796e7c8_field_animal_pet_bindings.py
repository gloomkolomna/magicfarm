"""field_animal_pet_bindings

Revision ID: 9b72b796e7c8
Revises: 68b8471dc823
Create Date: 2026-08-13 11:21:19.794381
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '9b72b796e7c8'
down_revision: Union[str, None] = '68b8471dc823'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('field_animals',
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('animal_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['animal_id'], ['animals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('field_id', 'animal_id')
    )
    op.create_table('field_pets',
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('pet_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('field_id', 'pet_id')
    )


def downgrade() -> None:
    op.drop_table('field_pets')
    op.drop_table('field_animals')
