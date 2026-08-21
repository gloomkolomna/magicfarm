"""notifications

Revision ID: f3113d1e6388
Revises: c8dc2fe74d6b
Create Date: 2026-08-21 18:52:04.600497
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f3113d1e6388'
down_revision: Union[str, None] = 'c8dc2fe74d6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    if "notifications" not in set(insp.get_table_names()):
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    op.drop_table('notifications')
