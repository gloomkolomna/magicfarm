"""cauldron_field_id

Revision ID: 03eb6a93e324
Revises: 4e488dbc9ec1
Create Date: 2026-08-23 10:00:31.923435
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '03eb6a93e324'
down_revision: Union[str, None] = '4e488dbc9ec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def _columns(bind, table: str) -> set:
    return {r[1] for r in bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()}


def _brewery_field_by_material(bind, material: str):
    row = bind.execute(sa.text(
        "SELECT f.id FROM fields f"
        " JOIN brewery_zones z ON z.field_id = f.id AND z.zone_kind = 'ingredient'"
        " WHERE f.field_kind = 'brewery'"
        " GROUP BY f.id"
        " HAVING COUNT(z.id) = :slots"
        " ORDER BY f.id LIMIT 1"
    ), {"slots": {"tin": 4, "silver": 5, "gold": 6}[material]}).fetchone()
    if row is not None:
        return row[0]
    fallback = bind.execute(sa.text(
        "SELECT id FROM fields WHERE field_kind = 'brewery' ORDER BY id"
    )).fetchall()
    order = {"tin": 0, "silver": 1, "gold": 2}
    idx = order.get(material, 0)
    if idx < len(fallback):
        return fallback[idx][0]
    return None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "cauldrons"):
        return
    if "field_id" not in _columns(bind, "cauldrons"):
        bind.execute(sa.text(
            "ALTER TABLE cauldrons ADD COLUMN field_id INTEGER REFERENCES fields(id) ON DELETE CASCADE"
        ))
    if not _has_table(bind, "fields") or not _has_table(bind, "brewery_zones"):
        return
    for material in ("tin", "silver", "gold"):
        fid = _brewery_field_by_material(bind, material)
        if fid is not None:
            bind.execute(sa.text(
                "UPDATE cauldrons SET field_id = :fid WHERE material = :material AND field_id IS NULL"
            ), {"fid": fid, "material": material})


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "cauldrons"):
        return
    if "field_id" in _columns(bind, "cauldrons"):
        bind.execute(sa.text("ALTER TABLE cauldrons DROP COLUMN field_id"))
