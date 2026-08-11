"""field_maps

Revision ID: 0002_field_maps
Revises: 0001_initial
Create Date: 2026-08-08 15:30:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0002_field_maps'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Карты-локации фермы (Огород, Сад, Склад…).
    op.create_table('fields',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('map_url', sa.String(), nullable=True),
        sa.Column('cols', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('rows', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('grid_color', sa.String(), nullable=False, server_default='#2a1a0e'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # Шатры (прямоугольные производства) — создаются ДО field_cells,
    # т.к. field_cells ссылается на tents.
    op.create_table('tents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('kind', sa.String(), nullable=False, server_default='alchemy'),
        sa.Column('col1', sa.Integer(), nullable=False),
        sa.Column('row1', sa.Integer(), nullable=False),
        sa.Column('col2', sa.Integer(), nullable=False),
        sa.Column('row2', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Клетки поля.
    op.create_table('field_cells',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('col', sa.Integer(), nullable=False),
        sa.Column('row', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False, server_default='bed'),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('occupant_user_id', sa.Integer(), nullable=True),
        sa.Column('tent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['occupant_user_id'], ['users.vk_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tent_id'], ['tents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('field_id', 'col', 'row', name='uq_fieldcell_field_col_row'),
    )

    # Доступные растения локации.
    op.create_table('field_plants',
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('field_id', 'plant_id'),
    )

    # Связь существующих грядок/производств с пространственным полем.
    with op.batch_alter_table('plots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cell_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_plots_cell_id', 'field_cells', ['cell_id'], ['id'], ondelete='SET NULL'
        )

    with op.batch_alter_table('productions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_productions_tent_id', 'tents', ['tent_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    with op.batch_alter_table('productions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_productions_tent_id', type_='foreignkey')
        batch_op.drop_column('tent_id')

    with op.batch_alter_table('plots', schema=None) as batch_op:
        batch_op.drop_constraint('fk_plots_cell_id', type_='foreignkey')
        batch_op.drop_column('cell_id')

    op.drop_table('field_plants')
    op.drop_table('field_cells')
    op.drop_table('tents')
    op.drop_table('fields')
