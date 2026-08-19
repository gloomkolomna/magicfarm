"""patient_state_current_field

Revision ID: c4a5b6c7d8e9
Revises: b3f2a1d4e5f6
Create Date: 2026-08-19 17:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c4a5b6c7d8e9'
down_revision: Union[str, None] = 'b3f2a1d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "user_patient_states"):
        return
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(user_patient_states)")).fetchall()}
    if "current_field_id" not in cols:
        bind.execute(sa.text(
            "ALTER TABLE user_patient_states ADD COLUMN current_field_id INTEGER "
            "REFERENCES fields(id) ON DELETE SET NULL"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "user_patient_states"):
        return
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(user_patient_states)")).fetchall()}
    if "current_field_id" in cols:
        bind.execute(sa.text("ALTER TABLE user_patient_states DROP COLUMN current_field_id"))
