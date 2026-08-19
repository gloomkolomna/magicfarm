"""dedupe_infirmary_scenes_unique_index

Revision ID: b3f2a1d4e5f6
Revises: a2001a7c12ae
Create Date: 2026-08-19 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b3f2a1d4e5f6'
down_revision: Union[str, None] = 'a2001a7c12ae'
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

    dupes = sa.text(
        "SELECT id FROM ("
        "  SELECT id, ROW_NUMBER() OVER (PARTITION BY clinic_animal_id, clinic_stage ORDER BY id) AS rn "
        "  FROM fields WHERE clinic_animal_id IS NOT NULL"
        ") WHERE rn > 1"
    )
    for table in ("clinic_part_cells", "field_cells", "infirmary_zones"):
        if _has_table(bind, table):
            bind.execute(
                sa.text(f"DELETE FROM {table} WHERE field_id IN ({dupes.text})")
            )
    bind.execute(sa.text("DELETE FROM fields WHERE id IN (" + dupes.text + ")"))

    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_field_clinic_animal_stage "
        "ON fields (clinic_animal_id, clinic_stage)"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "fields"):
        return
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_field_clinic_animal_stage"))
