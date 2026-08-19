"""infirmary zones and patient stages

Revision ID: f89acdeb8ed3
Revises: 5a8e8325cdb2
Create Date: 2026-08-19 14:01:31.356078
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'f89acdeb8ed3'
down_revision: Union[str, None] = '5a8e8325cdb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('infirmary_zones',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('zone_kind', sa.String(), nullable=False),
    sa.Column('col1', sa.Integer(), nullable=False),
    sa.Column('row1', sa.Integer(), nullable=False),
    sa.Column('col2', sa.Integer(), nullable=False),
    sa.Column('row2', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('patient_animals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hospital_image_url', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('healthy_image_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('patient_animals', schema=None) as batch_op:
        batch_op.drop_column('healthy_image_url')
        batch_op.drop_column('hospital_image_url')

    op.drop_table('infirmary_zones')
