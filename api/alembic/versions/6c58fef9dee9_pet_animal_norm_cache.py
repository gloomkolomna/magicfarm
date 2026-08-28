"""pet_animal_norm_cache

Revision ID: 6c58fef9dee9
Revises: 1bf141546f97
Create Date: 2026-08-28 22:06:08.667798
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '6c58fef9dee9'
down_revision: Union[str, None] = '1bf141546f97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect

    conn = op.get_bind()
    insp = inspect(conn)
    if not insp.has_table("user_animal_norms"):
        op.create_table('user_animal_norms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('animal_id', sa.Integer(), nullable=False),
        sa.Column('norm', sa.Integer(), nullable=False),
        sa.Column('drawn_cards_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['animal_id'], ['animals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'animal_id', name='uq_useranimalnorm_user_animal')
        )
    if not insp.has_table("user_pet_norms"):
        op.create_table('user_pet_norms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pet_id', sa.Integer(), nullable=False),
        sa.Column('norm', sa.Integer(), nullable=False),
        sa.Column('drawn_cards_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'pet_id', name='uq_userpetnorm_user_pet')
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    from sqlalchemy import inspect

    conn = op.get_bind()
    insp = inspect(conn)
    if insp.has_table("user_pet_norms"):
        op.drop_table('user_pet_norms')
    if insp.has_table("user_animal_norms"):
        op.drop_table('user_animal_norms')
    # ### end Alembic commands ###
