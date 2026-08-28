"""subscription_block_after_expiry_and_reminders

Revision ID: 1bf141546f97
Revises: 53aa1a96c016
Create Date: 2026-08-28 09:58:36.587544
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '1bf141546f97'
down_revision: Union[str, None] = '53aa1a96c016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set:
    insp = sa.inspect(bind)
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("subscription_reminders"):
        op.create_table('subscription_reminders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reminder_key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'reminder_key', name='uq_subreminder_user_key')
        )
    if "block_after_expiry" not in _columns(bind, "users"):
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('block_after_expiry', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    if "block_after_expiry" in _columns(bind, "users"):
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('block_after_expiry')
    insp = sa.inspect(bind)
    if insp.has_table("subscription_reminders"):
        op.drop_table('subscription_reminders')
