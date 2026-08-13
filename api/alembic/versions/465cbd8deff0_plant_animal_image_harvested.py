"""plant_animal_image_harvested

Revision ID: 465cbd8deff0
Revises: 5caf20f6da17
Create Date: 2026-08-13 12:25:43.924442
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '465cbd8deff0'
down_revision: Union[str, None] = '5caf20f6da17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('animals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_harvested_url', sa.String(), nullable=True))

    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_harvested_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_column('image_harvested_url')

    with op.batch_alter_table('animals', schema=None) as batch_op:
        batch_op.drop_column('image_harvested_url')
