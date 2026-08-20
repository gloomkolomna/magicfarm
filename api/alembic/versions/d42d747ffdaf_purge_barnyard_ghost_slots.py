"""purge_barnyard_ghost_slots

Revision ID: d42d747ffdaf
Revises: ba7f5ee8385b
Create Date: 2026-08-20 21:23:48.381487
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'd42d747ffdaf'
down_revision: Union[str, None] = 'ba7f5ee8385b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if not all(insp.has_table(t) for t in ("barnyard_slots", "field_cells", "fields")):
        return
    bind.execute(sa.text("""
        DELETE FROM barnyard_slots
        WHERE cell_id IS NULL
           OR cell_id NOT IN (SELECT id FROM field_cells)
           OR cell_id IN (
                SELECT fc.id FROM field_cells fc
                JOIN fields f ON f.id = fc.field_id
                WHERE fc.kind != 'barnyard'
                   OR fc.col >= f.cols OR fc.row >= f.rows
           )
    """))


def downgrade() -> None:
    pass
