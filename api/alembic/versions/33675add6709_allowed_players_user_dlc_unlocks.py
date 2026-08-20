"""allowed_players_user_dlc_unlocks

Revision ID: 33675add6709
Revises: e1236fd10bb4
Create Date: 2026-08-20 20:13:46.227050
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '33675add6709'
down_revision: Union[str, None] = 'e1236fd10bb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('allowed_players',
    sa.Column('vk_id', sa.Integer(), nullable=False),
    sa.Column('screen_name', sa.String(), nullable=True),
    sa.Column('added_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['added_by'], ['users.vk_id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('vk_id')
    )
    op.create_table('user_dlc_unlocks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('location_code', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'location_code', name='uq_userdlcunlock_user_location')
    )


def downgrade() -> None:
    op.drop_table('user_dlc_unlocks')
    op.drop_table('allowed_players')
