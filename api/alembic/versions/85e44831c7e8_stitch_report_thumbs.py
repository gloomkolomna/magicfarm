"""stitch_report_thumbs

Revision ID: 85e44831c7e8
Revises: a22565a9bbe6
Create Date: 2026-08-21 10:11:43.750028
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '85e44831c7e8'
down_revision: Union[str, None] = 'a22565a9bbe6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('stitch_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_before_thumb_url', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('photo_after_thumb_url', sa.String(), nullable=True))
        batch_op.alter_column('photo_after_url', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('stitch_reports', schema=None) as batch_op:
        batch_op.alter_column('photo_after_url', existing_type=sa.String(), nullable=False)
        batch_op.drop_column('photo_after_thumb_url')
        batch_op.drop_column('photo_before_thumb_url')
