"""notification kind

Revision ID: 53aa1a96c016
Revises: f6099d5d2b34
Create Date: 2026-08-26 16:58:46.473383
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '53aa1a96c016'
down_revision: Union[str, None] = 'f6099d5d2b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("notifications")}
    if "kind" not in cols:
        with op.batch_alter_table('notifications', schema=None) as batch_op:
            batch_op.add_column(sa.Column('kind', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_column('kind')
