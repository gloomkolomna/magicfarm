"""pet_forest_tasks

Revision ID: e1236fd10bb4
Revises: e521c2569036
Create Date: 2026-08-20 19:59:30.568920
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'e1236fd10bb4'
down_revision: Union[str, None] = 'e521c2569036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pet_forest_tasks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('pet_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.String(), nullable=False),
    sa.Column('required', sa.Integer(), server_default='200', nullable=False),
    sa.Column('accumulated', sa.Integer(), server_default='0', nullable=False),
    sa.Column('status', sa.String(), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'pet_id', 'date', name='uq_petforesttask_user_pet_date')
    )


def downgrade() -> None:
    op.drop_table('pet_forest_tasks')
