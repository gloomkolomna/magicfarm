"""production_templates_code

Revision ID: ec117d759fc0
Revises: 0a98e9b441d3
Create Date: 2026-08-10 08:32:59.597985
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'ec117d759fc0'
down_revision: Union[str, None] = '0a98e9b441d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('production_templates', schema=None) as batch_op:
        batch_op.alter_column('kind', new_column_name='code', existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('production_templates', schema=None) as batch_op:
        batch_op.alter_column('code', new_column_name='kind', existing_type=sa.String(), nullable=False)
