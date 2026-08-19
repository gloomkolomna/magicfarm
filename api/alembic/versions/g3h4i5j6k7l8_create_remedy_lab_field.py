"""create_remedy_lab_field

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-08-19 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import datetime


revision: str = 'g3h4i5j6k7l8'
down_revision: Union[str, None] = 'f2g3h4i5j6k7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "fields"):
        return
    if bind.execute(
        sa.text("SELECT 1 FROM fields WHERE field_kind='remedy_lab' LIMIT 1")
    ).fetchone():
        return
    code = "remedy_lab"
    n = 2
    while bind.execute(sa.text("SELECT 1 FROM fields WHERE code=:c"), {"c": code}).fetchone():
        code = f"remedy_lab_{n}"
        n += 1
    bind.execute(
        sa.text(
            "INSERT INTO fields (code, name, cols, rows, grid_color, min_level, field_kind, created_at) "
            "VALUES (:c, 'Лаборатория снадобий', 4, 3, '#1f1426', 0, 'remedy_lab', :ts)"
        ),
        {"c": code, "ts": datetime.datetime.utcnow()},
    )


def downgrade() -> None:
    pass
