"""pet_forest_task_ingredient_choice

Revision ID: f9517c48e092
Revises: 9f10289c3259
Create Date: 2026-08-24 19:54:40.180612
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f9517c48e092'
down_revision: Union[str, None] = '9f10289c3259'
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
    if not _has_table(bind, "pet_forest_tasks"):
        return
    if "ingredient_id" not in _columns(bind, "pet_forest_tasks"):
        bind.execute(sa.text(
            "ALTER TABLE pet_forest_tasks ADD COLUMN ingredient_id INTEGER "
            "REFERENCES ingredients(id) ON DELETE SET NULL"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "pet_forest_tasks"):
        return
    if "ingredient_id" in _columns(bind, "pet_forest_tasks"):
        bind.execute(sa.text("ALTER TABLE pet_forest_tasks DROP COLUMN ingredient_id"))
