"""plant_stages

Revision ID: 0005_plant_stages
Revises: 0004_tent_buildable
Create Date: 2026-08-09 01:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0005_plant_stages'
down_revision: Union[str, None] = '0004_tent_buildable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_young_url', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('image_grown_url', sa.String(), nullable=True))

    op.execute(
        "UPDATE plants SET image_young_url = image_url WHERE image_young_url IS NULL AND image_url IS NOT NULL"
    )

    with op.batch_alter_table('field_cells', schema=None) as batch_op:
        batch_op.alter_column('kind', existing_type=sa.String(), server_default='empty')


def downgrade() -> None:
    with op.batch_alter_table('field_cells', schema=None) as batch_op:
        batch_op.alter_column('kind', existing_type=sa.String(), server_default='bed')

    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_column('image_grown_url')
        batch_op.drop_column('image_young_url')
