"""lesson_category

Revision ID: 8f6c8f989150
Revises: f9517c48e092
Create Date: 2026-08-24 21:50:40.895579
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '8f6c8f989150'
down_revision: Union[str, None] = 'f9517c48e092'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def _columns(bind, table: str) -> set:
    return {r[1] for r in bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "lessons"):
        return
    if "category" not in _columns(bind, "lessons"):
        bind.execute(sa.text(
            "ALTER TABLE lessons ADD COLUMN category VARCHAR NOT NULL DEFAULT 'farm'"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "lessons"):
        return
    if "category" in _columns(bind, "lessons"):
        bind.execute(sa.text("ALTER TABLE lessons DROP COLUMN category"))
