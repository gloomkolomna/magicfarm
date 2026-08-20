"""otter_pet_backfill

Revision ID: e521c2569036
Revises: 00d670aa98b3
Create Date: 2026-08-20 19:26:26.595266
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'e521c2569036'
down_revision: Union[str, None] = '00d670aa98b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :n"),
            {"n": name},
        ).scalar()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()

    required_tables = [
        "pets", "fields", "field_cells", "field_pets", "users",
        "user_pets", "user_patient_states", "patient_animals", "clinic_animal_types",
    ]
    if not all(_table_exists(conn, t) for t in required_tables):
        return

    pet_id = conn.execute(sa.text(
        "SELECT id FROM pets WHERE code IN ('vydra','otter') OR LOWER(name) LIKE '%выдр%' LIMIT 1"
    )).scalar()
    if pet_id is None:
        conn.execute(sa.text(
            "INSERT INTO pets (code, name, emoji) VALUES ('vydra', 'Выдра', '🦦')"
        ))
        pet_id = conn.execute(sa.text("SELECT id FROM pets WHERE code = 'vydra'")).scalar()

    lawn_id = conn.execute(sa.text(
        "SELECT id FROM fields WHERE field_kind = 'lawn' ORDER BY id LIMIT 1"
    )).scalar()
    if lawn_id is not None and pet_id is not None:
        bound = conn.execute(sa.text(
            "SELECT 1 FROM field_pets WHERE field_id = :f AND pet_id = :p"
        ), {"f": lawn_id, "p": pet_id}).scalar()
        if not bound:
            conn.execute(sa.text(
                "INSERT INTO field_pets (field_id, pet_id) VALUES (:f, :p)"
            ), {"f": lawn_id, "p": pet_id})

    if pet_id is None:
        return

    rows = conn.execute(sa.text(
        "SELECT DISTINCT ups.user_id, pa.name, cat.name "
        "FROM user_patient_states ups "
        "JOIN patient_animals pa ON pa.id = ups.patient_id "
        "LEFT JOIN clinic_animal_types cat ON cat.id = pa.animal_type_id "
        "WHERE ups.status IN ('treated','released')"
    )).fetchall()
    user_ids = {
        r[0]
        for r in rows
        if "выдр" in (r[1] or "").lower() or "выдр" in (r[2] or "").lower()
    }
    for uid in user_ids:
        has = conn.execute(sa.text(
            "SELECT 1 FROM user_pets WHERE user_id = :u AND pet_id = :p"
        ), {"u": uid, "p": pet_id}).scalar()
        if has:
            continue
        conn.execute(sa.text(
            "UPDATE users SET unlocked_pets = MAX(COALESCE(unlocked_pets, 0), 6) WHERE vk_id = :u"
        ), {"u": uid})
        occupied = {
            r[0] for r in conn.execute(sa.text(
                "SELECT cell_id FROM user_pets WHERE user_id = :u AND cell_id IS NOT NULL"
            ), {"u": uid}).fetchall()
        }
        cell_id = None
        for c in conn.execute(sa.text(
            "SELECT fc.id FROM field_cells fc JOIN fields f ON f.id = fc.field_id "
            "WHERE f.field_kind = 'lawn' AND fc.kind = 'pet' ORDER BY fc.id"
        )).fetchall():
            if c[0] not in occupied:
                cell_id = c[0]
                break
        conn.execute(sa.text(
            "INSERT INTO user_pets (user_id, pet_id, cell_id, acquired_at) "
            "VALUES (:u, :p, :c, datetime('now'))"
        ), {"u": uid, "p": pet_id, "c": cell_id})


def downgrade() -> None:
    conn = op.get_bind()
    pet_id = conn.execute(sa.text(
        "SELECT id FROM pets WHERE code IN ('vydra','otter') OR LOWER(name) LIKE '%выдр%' LIMIT 1"
    )).scalar()
    if pet_id is None:
        return
    conn.execute(sa.text("DELETE FROM user_pets WHERE pet_id = :p"), {"p": pet_id})
    conn.execute(sa.text("DELETE FROM field_pets WHERE pet_id = :p"), {"p": pet_id})
    conn.execute(sa.text("DELETE FROM pets WHERE id = :p"), {"p": pet_id})
