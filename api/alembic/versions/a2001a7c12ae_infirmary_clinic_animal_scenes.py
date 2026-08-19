"""infirmary_clinic_animal_scenes

Revision ID: a2001a7c12ae
Revises: fecdbd441c2b
Create Date: 2026-08-19 15:52:49.792812
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import datetime
import re


revision: str = 'a2001a7c12ae'
down_revision: Union[str, None] = 'fecdbd441c2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(bind, table: str) -> set[str]:
    return {r[1] for r in bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()}


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone() is not None


def _slugify(name: str, fallback: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or fallback
    if not base[0].isalpha():
        base = f"{fallback}_{base}"
    return base


def _unique_code(bind, table: str, base: str) -> str:
    code = base
    n = 2
    while bind.execute(sa.text(f"SELECT 1 FROM {table} WHERE code=:c"), {"c": code}).fetchone():
        code = f"{base}_{n}"
        n += 1
    return code


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS clinic_animal_types ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "code VARCHAR NOT NULL UNIQUE, "
        "name VARCHAR NOT NULL, "
        "emoji VARCHAR, "
        "sort_order INTEGER NOT NULL DEFAULT 0)"
    ))

    has_patients = _has_table(bind, "patient_animals")
    has_fields = _has_table(bind, "fields")

    if has_fields:
        fcols = _cols(bind, "fields")
        if "clinic_animal_id" not in fcols:
            bind.execute(sa.text("ALTER TABLE fields ADD COLUMN clinic_animal_id INTEGER"))
        if "clinic_stage" not in fcols:
            bind.execute(sa.text("ALTER TABLE fields ADD COLUMN clinic_stage VARCHAR"))

    if has_patients:
        pcols = _cols(bind, "patient_animals")
        if "animal_type_id" not in pcols:
            bind.execute(sa.text(
                "ALTER TABLE patient_animals ADD COLUMN animal_type_id INTEGER "
                "REFERENCES clinic_animal_types(id) ON DELETE SET NULL"
            ))

    if has_patients and has_fields:
        patients = bind.execute(
            sa.text("SELECT id, name FROM patient_animals")
        ).fetchall()

        scene_rows = {
            "sick": "больное",
            "treating": "на лечении",
            "healthy": "здоровое",
        }

        for pid, name in patients:
            row = bind.execute(
                sa.text("SELECT id FROM clinic_animal_types WHERE name=:n"), {"n": name}
            ).fetchone()
            if row is None:
                type_code = _unique_code(bind, "clinic_animal_types", _slugify(name, "animal_type"))
                bind.execute(
                    sa.text("INSERT INTO clinic_animal_types (code, name) VALUES (:c, :n)"),
                    {"c": type_code, "n": name or "Животное"},
                )
                row = bind.execute(
                    sa.text("SELECT id FROM clinic_animal_types WHERE code=:c"), {"c": type_code}
                ).fetchone()
            bind.execute(
                sa.text("UPDATE patient_animals SET animal_type_id=:t WHERE id=:p AND animal_type_id IS NULL"),
                {"t": row[0], "p": pid},
            )

            existing = {
                r[0] for r in bind.execute(
                    sa.text("SELECT clinic_stage FROM fields WHERE clinic_animal_id=:p"),
                    {"p": pid},
                ).fetchall()
            }
            for stage in scene_rows:
                if stage in existing:
                    continue
                if stage == "sick":
                    f_row = bind.execute(
                        sa.text("SELECT id, cols, rows FROM fields WHERE field_kind='infirmary' "
                                "AND clinic_animal_id IS NULL ORDER BY id ASC LIMIT 1")
                    ).fetchone()
                else:
                    f_row = None
                if f_row is not None:
                    src_id, cols, rows = f_row
                    bind.execute(
                        sa.text("UPDATE fields SET clinic_animal_id=:p, clinic_stage='sick' WHERE id=:f"),
                        {"p": pid, "f": src_id},
                    )
                else:
                    cols, rows = (3, 2)
                code = _unique_code(bind, "fields", f"{_slugify(name, 'scene')}_{stage}")
                bind.execute(
                    sa.text(
                        "INSERT INTO fields (code, name, cols, rows, grid_color, min_level, field_kind, clinic_animal_id, clinic_stage, created_at) "
                        "VALUES (:c, :n, :cols, :rows, '#2a1a0e', 0, 'infirmary', :p, :stage, :ts)"
                    ),
                    {"c": code, "n": f"{name} — {scene_rows[stage]}", "cols": cols, "rows": rows,
                     "p": pid, "stage": stage, "ts": datetime.datetime.utcnow()},
                )

    if _has_table(bind, "infirmary_zones"):
        bind.execute(sa.text("DELETE FROM infirmary_zones WHERE zone_kind='animal'"))

    if has_fields and _has_table(bind, "clinic_part_cells") and "animal_id" in _cols(bind, "clinic_part_cells"):
        bind.execute(sa.text(
            "CREATE TABLE clinic_part_cells_new ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "field_id INTEGER NOT NULL, "
            "col INTEGER NOT NULL, "
            "row INTEGER NOT NULL, "
            "part_code VARCHAR NOT NULL, "
            "CONSTRAINT uq_clinicpartcell_field_col_row UNIQUE (field_id, col, row), "
            "FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE CASCADE)"
        ))
        bind.execute(sa.text(
            "INSERT INTO clinic_part_cells_new (id, field_id, col, row, part_code) "
            "SELECT id, field_id, col, row, part_code FROM clinic_part_cells"
        ))
        bind.execute(sa.text("DROP TABLE clinic_part_cells"))
        bind.execute(sa.text("ALTER TABLE clinic_part_cells_new RENAME TO clinic_part_cells"))

    if has_patients and ("field_id" in _cols(bind, "patient_animals") or "image_url" in _cols(bind, "patient_animals")):
        bind.execute(sa.text(
            "CREATE TABLE patient_animals_new ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "code VARCHAR NOT NULL UNIQUE, "
            "name VARCHAR NOT NULL, "
            "level INTEGER NOT NULL DEFAULT 1, "
            "card_image_url VARCHAR, "
            "animal_type_id INTEGER, "
            "disease_id INTEGER, "
            "FOREIGN KEY(animal_type_id) REFERENCES clinic_animal_types(id) ON DELETE SET NULL, "
            "FOREIGN KEY(disease_id) REFERENCES diseases(id) ON DELETE SET NULL)"
        ))
        bind.execute(sa.text(
            "INSERT INTO patient_animals_new (id, code, name, level, card_image_url, animal_type_id, disease_id) "
            "SELECT id, code, name, level, card_image_url, animal_type_id, disease_id FROM patient_animals"
        ))
        bind.execute(sa.text("DROP TABLE patient_animals"))
        bind.execute(sa.text("ALTER TABLE patient_animals_new RENAME TO patient_animals"))


def downgrade() -> None:
    bind = op.get_bind()

    if "clinic_animal_id" in _cols(bind, "patient_animals") or "animal_type_id" not in _cols(bind, "patient_animals"):
        pass

    if "animal_id" not in _cols(bind, "clinic_part_cells"):
        bind.execute(sa.text(
            "CREATE TABLE clinic_part_cells_new ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "field_id INTEGER NOT NULL, "
            "animal_id INTEGER NOT NULL, "
            "col INTEGER NOT NULL, "
            "row INTEGER NOT NULL, "
            "part_code VARCHAR NOT NULL, "
            "CONSTRAINT uq_clinicpartcell_field_col_row UNIQUE (field_id, col, row), "
            "FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE CASCADE, "
            "FOREIGN KEY(animal_id) REFERENCES patient_animals(id) ON DELETE CASCADE)"
        ))
        bind.execute(sa.text(
            "INSERT INTO clinic_part_cells_new (id, field_id, animal_id, col, row, part_code) "
            "SELECT id, field_id, animal_id, col, row, part_code FROM clinic_part_cells"
        ))
        bind.execute(sa.text("DROP TABLE clinic_part_cells"))
        bind.execute(sa.text("ALTER TABLE clinic_part_cells_new RENAME TO clinic_part_cells"))

    if "animal_type_id" in _cols(bind, "patient_animals"):
        bind.execute(sa.text(
            "CREATE TABLE patient_animals_new ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "code VARCHAR NOT NULL UNIQUE, "
            "name VARCHAR NOT NULL, "
            "level INTEGER NOT NULL DEFAULT 1, "
            "image_url VARCHAR, "
            "card_image_url VARCHAR, "
            "hospital_image_url VARCHAR, "
            "healthy_image_url VARCHAR, "
            "animal_type_id INTEGER, "
            "disease_id INTEGER, "
            "field_id INTEGER, "
            "FOREIGN KEY(animal_type_id) REFERENCES clinic_animal_types(id) ON DELETE SET NULL, "
            "FOREIGN KEY(disease_id) REFERENCES diseases(id) ON DELETE SET NULL, "
            "FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE CASCADE)"
        ))
        bind.execute(sa.text(
            "INSERT INTO patient_animals_new (id, code, name, level, image_url, card_image_url, hospital_image_url, healthy_image_url, animal_type_id, disease_id, field_id) "
            "SELECT id, code, name, level, NULL, card_image_url, NULL, NULL, animal_type_id, disease_id, NULL FROM patient_animals"
        ))
        bind.execute(sa.text("DROP TABLE patient_animals"))
        bind.execute(sa.text("ALTER TABLE patient_animals_new RENAME TO patient_animals"))

    if "clinic_animal_id" in _cols(bind, "fields"):
        bind.execute(sa.text("ALTER TABLE fields DROP COLUMN clinic_stage"))
        bind.execute(sa.text("ALTER TABLE fields DROP COLUMN clinic_animal_id"))

    bind.execute(sa.text("DROP TABLE IF EXISTS clinic_animal_types"))
