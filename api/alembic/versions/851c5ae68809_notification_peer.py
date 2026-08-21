"""notification peer

Revision ID: 851c5ae68809
Revises: eb60e8f8edf3
Create Date: 2026-08-21 20:05:20.346750
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '851c5ae68809'
down_revision: Union[str, None] = 'eb60e8f8edf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("notifications")}
    if "peer_vk_id" not in cols:
        with op.batch_alter_table('notifications', schema=None) as batch_op:
            batch_op.add_column(sa.Column('peer_vk_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_column('peer_vk_id')
