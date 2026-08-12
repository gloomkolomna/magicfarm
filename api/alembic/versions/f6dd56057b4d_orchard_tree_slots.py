"""orchard_tree_slots

Revision ID: f6dd56057b4d
Revises: bee443355cff
Create Date: 2026-08-12 11:05:29.686813
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'f6dd56057b4d'
down_revision: Union[str, None] = 'bee443355cff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('plant_beds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plant_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('occupant_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_plantbed_plant', 'plants', ['plant_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_plantbed_user', 'users', ['occupant_user_id'], ['vk_id'], ondelete='SET NULL')

    with op.batch_alter_table('plots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plant_bed_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_plot_plantbed', 'plant_beds', ['plant_bed_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('plots', schema=None) as batch_op:
        batch_op.drop_constraint('fk_plot_plantbed', type_='foreignkey')
        batch_op.drop_column('plant_bed_id')

    with op.batch_alter_table('plant_beds', schema=None) as batch_op:
        batch_op.drop_constraint('fk_plantbed_user', type_='foreignkey')
        batch_op.drop_constraint('fk_plantbed_plant', type_='foreignkey')
        batch_op.drop_column('occupant_user_id')
        batch_op.drop_column('plant_id')
