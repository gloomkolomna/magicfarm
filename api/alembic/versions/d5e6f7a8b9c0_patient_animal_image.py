"""patient_animal_image

Revision ID: d5e6f7a8b9c0
Revises: c4a5b6c7d8e9
Create Date: 2026-08-19 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "patient_animals"):
        return
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(patient_animals)")).fetchall()}
    if "animal_image_url" not in cols:
        bind.execute(sa.text("ALTER TABLE patient_animals ADD COLUMN animal_image_url VARCHAR"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "patient_animals"):
        return
    cols = {r[1] for r in bind.execute(sa.text("PRAGMA table_info(patient_animals)")).fetchall()}
    if "animal_image_url" in cols:
        bind.execute(sa.text("ALTER TABLE patient_animals DROP COLUMN animal_image_url"))
