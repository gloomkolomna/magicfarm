"""infirmary_scenes_min_level_zero

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-08-19 19:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
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
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(fields)")).fetchall()}
    if "clinic_animal_id" not in cols:
        return
    bind.execute(sa.text(
        "UPDATE fields SET min_level=0 WHERE clinic_animal_id IS NOT NULL"
    ))


def downgrade() -> None:
    pass
