"""remedy_device_image_url

Revision ID: a22565a9bbe6
Revises: 1ecc2026e7c1
Create Date: 2026-08-21 10:00:18.745437
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'a22565a9bbe6'
down_revision: Union[str, None] = '1ecc2026e7c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('remedy_device_cells', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('remedy_device_cells', schema=None) as batch_op:
        batch_op.drop_column('image_url')
