"""board_posts_board

Revision ID: a84014c79066
Revises: 6c58fef9dee9
Create Date: 2026-09-05 18:33:34.749790
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'a84014c79066'
down_revision: Union[str, None] = '6c58fef9dee9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if 'board_posts' not in existing:
        op.create_table('board_posts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), server_default='open', nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('fulfilled_by', sa.Integer(), nullable=True),
        sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
    if 'board_post_items' not in existing:
        op.create_table('board_post_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['board_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
    if 'board_holds' not in existing:
        op.create_table('board_holds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['board_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    op.drop_table('board_holds')
    op.drop_table('board_post_items')
    op.drop_table('board_posts')
