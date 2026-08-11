"""drop_legacy_bed_cells

Revision ID: 0007_drop_legacy_bed_cells
Revises: 0006_drop_blocked_cells
Create Date: 2026-08-09 03:00:00.000000

Legacy-локации создавались, когда дефолт клеток был kind='bed' — то есть
«всё поле в грядках». После перехода на рисуемые грядки (дефолт empty)
существующие bed-клетки нужно сбросить в empty: грядки должен осознанно
рисовать админ. Шатры (tent) и иные типы не трогаем — их kind проставлен явно.
"""
from typing import Sequence, Union
from alembic import op


revision: str = '0007_drop_legacy_bed_cells'
down_revision: Union[str, None] = '0006_drop_blocked_cells'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE field_cells SET kind='empty' WHERE kind='bed'")


def downgrade() -> None:
    pass
