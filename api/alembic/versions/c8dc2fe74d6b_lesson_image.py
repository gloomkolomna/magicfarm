"""lesson image

Revision ID: c8dc2fe74d6b
Revises: 141242a1899d
Create Date: 2026-08-21 17:32:42.680215
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c8dc2fe74d6b'
down_revision: Union[str, None] = '141242a1899d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("lessons")}
    if "image_url" not in cols:
        with op.batch_alter_table('lessons', schema=None) as batch_op:
            batch_op.add_column(sa.Column('image_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_column('image_url')
