"""phase11_meadow_shop_cells

Revision ID: 48a0b1ea3146
Revises: 8924ec161fed
Create Date: 2026-08-18 20:41:17.499638
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '48a0b1ea3146'
down_revision: Union[str, None] = '8924ec161fed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('gather_cells',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('col', sa.Integer(), nullable=False),
    sa.Column('row', sa.Integer(), nullable=False),
    sa.Column('window', sa.String(), server_default='always', nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('field_id', 'col', 'row', name='uq_gathercell_field_col_row')
    )
    op.create_table('trade_cells',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('col', sa.Integer(), nullable=False),
    sa.Column('row', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('field_id', 'col', 'row', name='uq_tradecell_field_col_row')
    )
    op.create_table('gather_cell_ingredients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('gather_cell_id', sa.Integer(), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['gather_cell_id'], ['gather_cells.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('gather_cell_id', 'ingredient_id', name='uq_gathercell_ingredient')
    )
    op.create_table('trade_cell_ingredients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('trade_cell_id', sa.Integer(), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['trade_cell_id'], ['trade_cells.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trade_cell_id', 'ingredient_id', name='uq_tradecell_ingredient')
    )
    op.create_table('user_gather_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('gather_cell_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['gather_cell_id'], ['gather_cells.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'gather_cell_id', 'date', name='uq_usergatherlog_user_cell_date')
    )


def downgrade() -> None:
    op.drop_table('user_gather_logs')
    op.drop_table('trade_cell_ingredients')
    op.drop_table('gather_cell_ingredients')
    op.drop_table('trade_cells')
    op.drop_table('gather_cells')
