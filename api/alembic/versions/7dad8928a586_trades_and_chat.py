"""trades and chat

Revision ID: 7dad8928a586
Revises: 71d6c61e4262
Create Date: 2026-08-21 13:59:01.461078
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '7dad8928a586'
down_revision: Union[str, None] = '71d6c61e4262'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    existing = set(insp.get_table_names())

    if "chat_messages" not in existing:
        op.create_table(
            'chat_messages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('from_user_id', sa.Integer(), nullable=False),
            sa.Column('to_user_id', sa.Integer(), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['from_user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['to_user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
    if "trade_offers" not in existing:
        op.create_table(
            'trade_offers',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('from_user_id', sa.Integer(), nullable=False),
            sa.Column('to_user_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(), server_default='open', nullable=False),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['from_user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['to_user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
    if "trade_offer_items" not in existing:
        op.create_table(
            'trade_offer_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('offer_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(), nullable=False),
            sa.Column('item_id', sa.Integer(), nullable=False),
            sa.Column('qty', sa.Integer(), nullable=False),
            sa.Column('direction', sa.String(), nullable=False),
            sa.ForeignKeyConstraint(['offer_id'], ['trade_offers.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    op.drop_table('trade_offer_items')
    op.drop_table('trade_offers')
    op.drop_table('chat_messages')
