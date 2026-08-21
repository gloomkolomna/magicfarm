"""story slides lessons

Revision ID: fffb1f7ef678
Revises: 37934f423cf2
Create Date: 2026-08-21 13:31:42.434939
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'fffb1f7ef678'
down_revision: Union[str, None] = '37934f423cf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    existing = set(insp.get_table_names())

    if "story_slides" not in existing:
        op.create_table(
            'story_slides',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('image_url', sa.String(), nullable=True),
            sa.Column('text', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    if "lessons" not in existing:
        op.create_table(
            'lessons',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('video_url', sa.String(), nullable=True),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "story_seen" not in user_cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('story_seen', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('story_seen')
    op.drop_table('lessons')
    op.drop_table('story_slides')
