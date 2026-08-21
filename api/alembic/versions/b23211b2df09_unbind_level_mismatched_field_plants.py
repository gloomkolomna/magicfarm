"""unbind_level_mismatched_field_plants

Локации с заданным уровнем (fields.min_level > 0) теперь могут содержать
только растения того же уровня. Миграция тихо отвязывает несоответствующие
растения от локаций, НЕ удаляя сами растения из каталога:
  - удаляет строки-связки field_plants с рассинхроном уровней;
  - у грядок игроков сбрасывает ссылку на клетку/слот локации (plots.cell_id,
    plots.plant_bed_id), если растение не того уровня.

Revision ID: b23211b2df09
Revises: dcc82124b5c3
Create Date: 2026-08-21 20:50:05.785208
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'b23211b2df09'
down_revision: Union[str, None] = 'dcc82124b5c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_columns(conn, name: str) -> set[str]:
    if conn.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :n"),
        {"n": name},
    ).fetchone() is None:
        return set()
    return {row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({name})"))}


def upgrade() -> None:
    conn = op.get_bind()

    field_cols = _table_columns(conn, "fields")
    plant_cols = _table_columns(conn, "plants")
    has_levels = {"id", "min_level"} <= field_cols and {"id", "level"} <= plant_cols
    if not has_levels:
        return

    if _table_columns(conn, "field_plants") >= {"field_id", "plant_id"}:
        conn.execute(sa.text(
            "DELETE FROM field_plants WHERE EXISTS ("
            "SELECT 1 FROM fields f, plants pl "
            "WHERE f.id = field_plants.field_id AND pl.id = field_plants.plant_id "
            "AND f.min_level IS NOT NULL AND f.min_level > 0 AND pl.level != f.min_level)"
        ))

    plot_cols = _table_columns(conn, "plots")
    if {"id", "plant_id", "cell_id"} <= plot_cols and _table_columns(conn, "field_cells") >= {"id", "field_id"}:
        conn.execute(sa.text(
            "UPDATE plots SET cell_id = NULL WHERE id IN ("
            "SELECT p.id FROM plots p "
            "JOIN field_cells c ON p.cell_id = c.id "
            "JOIN fields f ON c.field_id = f.id "
            "JOIN plants pl ON p.plant_id = pl.id "
            "WHERE f.min_level IS NOT NULL AND f.min_level > 0 AND pl.level != f.min_level)"
        ))

    if {"id", "plant_id", "plant_bed_id"} <= plot_cols and _table_columns(conn, "plant_beds") >= {"id", "field_id"}:
        conn.execute(sa.text(
            "UPDATE plots SET plant_bed_id = NULL WHERE id IN ("
            "SELECT p.id FROM plots p "
            "JOIN plant_beds b ON p.plant_bed_id = b.id "
            "JOIN fields f ON b.field_id = f.id "
            "JOIN plants pl ON p.plant_id = pl.id "
            "WHERE f.min_level IS NOT NULL AND f.min_level > 0 AND pl.level != f.min_level)"
        ))


def downgrade() -> None:
    pass
