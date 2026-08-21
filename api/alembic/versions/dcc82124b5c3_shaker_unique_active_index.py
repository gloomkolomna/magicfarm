"""shaker unique active index

Revision ID: dcc82124b5c3
Revises: 851c5ae68809
Create Date: 2026-08-21 20:40:07.144755
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'dcc82124b5c3'
down_revision: Union[str, None] = '851c5ae68809'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    existing = {
        i["name"] for i in insp.get_indexes("shakers")
    }
    if "uq_shakers_user_active" not in existing:
        bind.execute(sa.text(
            "UPDATE shakers SET status = 'done' "
            "WHERE status != 'done' AND id NOT IN ("
            "  SELECT MIN(id) FROM shakers WHERE status != 'done' GROUP BY user_id"
            ")"
        ))
        op.create_index(
            'uq_shakers_user_active', 'shakers', ['user_id'], unique=True,
            sqlite_where=sa.text("status != 'done'"),
        )


def downgrade() -> None:
    op.drop_index('uq_shakers_user_active', table_name='shakers')
