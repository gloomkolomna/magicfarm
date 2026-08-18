"""seed_kassa_production_template

Revision ID: e8f1a2b3c4d5
Revises: 55d5b568ce3e
Create Date: 2026-08-18 17:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e8f1a2b3c4d5'
down_revision: Union[str, None] = '55d5b568ce3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "INSERT INTO production_templates (code, name, emoji, required, cards_to_draw, surcharge, processing_crystal) "
        "SELECT 'kassa', 'Шатёр-касса', '🧾', 500, 3, 0, 0 "
        "WHERE NOT EXISTS (SELECT 1 FROM production_templates WHERE code = 'kassa')"
    ))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM production_templates WHERE code = 'kassa'"))
