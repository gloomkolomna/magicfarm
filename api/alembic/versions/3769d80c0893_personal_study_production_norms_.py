"""personal_study_production_norms_processing_crystal

Revision ID: 3769d80c0893
Revises: befe7d004cbd
Create Date: 2026-08-15 20:08:06.024174
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '3769d80c0893'
down_revision: Union[str, None] = 'befe7d004cbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('production_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('processing_crystal', sa.Integer(), server_default='0', nullable=False))

    with op.batch_alter_table('user_recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('required', sa.Integer(), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('study_norm_l1', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('study_norm_l2', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('study_norm_l3', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('production_norm_l1', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('production_norm_l2', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('production_norm_l3', sa.Integer(), nullable=True))

    op.execute(sa.text(
        "DELETE FROM settings WHERE key IN "
        "('study_norm_lvl1', 'study_norm_lvl2', 'study_norm_lvl3', "
        "'production_norm_lvl1', 'production_norm_lvl2', 'production_norm_lvl3')"
    ))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('production_norm_l3')
        batch_op.drop_column('production_norm_l2')
        batch_op.drop_column('production_norm_l1')
        batch_op.drop_column('study_norm_l3')
        batch_op.drop_column('study_norm_l2')
        batch_op.drop_column('study_norm_l1')

    with op.batch_alter_table('user_recipes', schema=None) as batch_op:
        batch_op.drop_column('required')

    with op.batch_alter_table('production_templates', schema=None) as batch_op:
        batch_op.drop_column('processing_crystal')
