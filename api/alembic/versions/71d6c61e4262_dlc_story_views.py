"""dlc story views

Revision ID: 71d6c61e4262
Revises: fffb1f7ef678
Create Date: 2026-08-21 13:51:17.315186
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '71d6c61e4262'
down_revision: Union[str, None] = 'fffb1f7ef678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    existing = set(insp.get_table_names())

    if "user_dlc_story_views" not in existing:
        op.create_table(
            'user_dlc_story_views',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('location_code', sa.String(), nullable=False),
            sa.Column('seen_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'location_code', name='uq_userdlcstoryview_user_location'),
        )

    slide_cols = {c["name"] for c in insp.get_columns("story_slides")}
    if "location_code" not in slide_cols:
        with op.batch_alter_table('story_slides', schema=None) as batch_op:
            batch_op.add_column(sa.Column('location_code', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('story_slides', schema=None) as batch_op:
        batch_op.drop_column('location_code')
    op.drop_table('user_dlc_story_views')
