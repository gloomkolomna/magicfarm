"""disease_image_url

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-19 19:50:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f2g3h4i5j6k7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "diseases"):
        return
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(diseases)")).fetchall()}
    if "image_url" not in cols:
        bind.execute(sa.text("ALTER TABLE diseases ADD COLUMN image_url VARCHAR"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "diseases"):
        return
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(diseases)")).fetchall()}
    if "image_url" in cols:
        bind.execute(sa.text("ALTER TABLE diseases DROP COLUMN image_url"))
