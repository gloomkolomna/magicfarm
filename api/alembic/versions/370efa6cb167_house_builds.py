"""house_builds

Revision ID: 370efa6cb167
Revises: 7fb944d095ae
Create Date: 2026-08-15 10:50:45.976803
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '370efa6cb167'
down_revision: Union[str, None] = '7fb944d095ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('house_builds',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('tent_id', sa.Integer(), nullable=False),
    sa.Column('phase', sa.String(), server_default='materials', nullable=False),
    sa.Column('current_material', sa.String(), nullable=True),
    sa.Column('current_die', sa.Integer(), nullable=True),
    sa.Column('current_required', sa.Integer(), nullable=True),
    sa.Column('collected_json', sa.Text(), server_default='[]', nullable=False),
    sa.Column('cards_json', sa.Text(), nullable=True),
    sa.Column('required', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tent_id'], ['tents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'tent_id', name='uq_housebuild_user_tent')
    )


def downgrade() -> None:
    op.drop_table('house_builds')
