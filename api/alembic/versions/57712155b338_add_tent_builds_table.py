"""add tent_builds table

Revision ID: 57712155b338
Revises: 74c9250986f4
Create Date: 2026-08-13 09:17:06.924360
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '57712155b338'
down_revision: Union[str, None] = '74c9250986f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tent_builds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tent_id', sa.Integer(), nullable=False),
        sa.Column('build_status', sa.String(), server_default='slot', nullable=False),
        sa.Column('accumulated', sa.Integer(), server_default='0', nullable=False),
        sa.Column('required', sa.Integer(), server_default='0', nullable=False),
        sa.Column('crystal_color', sa.String(), nullable=True),
        sa.Column('crystal_count', sa.Integer(), nullable=True),
        sa.Column('drawn_cards_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tent_id'], ['tents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tent_id', name='uq_tentbuild_user_tent'),
    )


def downgrade() -> None:
    op.drop_table('tent_builds')
