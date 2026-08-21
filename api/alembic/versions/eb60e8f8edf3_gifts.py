"""gifts

Revision ID: eb60e8f8edf3
Revises: f3113d1e6388
Create Date: 2026-08-21 19:11:23.701001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'eb60e8f8edf3'
down_revision: Union[str, None] = 'f3113d1e6388'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    existing = set(insp.get_table_names())

    if "gifts" not in existing:
        op.create_table(
            'gifts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('from_user_id', sa.Integer(), nullable=False),
            sa.Column('to_user_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(), nullable=False),
            sa.Column('item_id', sa.Integer(), nullable=False),
            sa.Column('qty', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('claimed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['from_user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['to_user_id'], ['users.vk_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    msg_cols = {c["name"] for c in insp.get_columns("chat_messages")}
    if "kind" not in msg_cols:
        with op.batch_alter_table('chat_messages', schema=None) as batch_op:
            batch_op.add_column(sa.Column('kind', sa.String(), server_default='text', nullable=False))
    if "gift_id" not in msg_cols:
        with op.batch_alter_table('chat_messages', schema=None) as batch_op:
            batch_op.add_column(sa.Column('gift_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_chat_messages_gift_id_gifts', 'gifts', ['gift_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('gift_id')
        batch_op.drop_column('kind')
    op.drop_table('gifts')
