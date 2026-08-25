"""user_hidden_flag

Revision ID: f6099d5d2b34
Revises: 8f6c8f989150
Create Date: 2026-08-25 07:42:27.683748
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'f6099d5d2b34'
down_revision: Union[str, None] = '8f6c8f989150'
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
    if not _has_table(bind, "users"):
        return
    if "hidden" not in _columns(bind, "users"):
        bind.execute(sa.text(
            "ALTER TABLE users ADD COLUMN hidden BOOLEAN NOT NULL DEFAULT 0"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "users"):
        return
    if "hidden" in _columns(bind, "users"):
        bind.execute(sa.text("ALTER TABLE users DROP COLUMN hidden"))
