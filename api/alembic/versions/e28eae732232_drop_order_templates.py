"""drop_order_templates

Revision ID: e28eae732232
Revises: d956b42d4036
Create Date: 2026-08-16 20:17:35.905627
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e28eae732232'
down_revision: Union[str, None] = 'd956b42d4036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS order_templates")


def downgrade() -> None:
    op.create_table('order_templates',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('source_kind', sa.VARCHAR(), nullable=False),
        sa.Column('source_id', sa.INTEGER(), nullable=False),
        sa.Column('product_id', sa.INTEGER(), nullable=False),
        sa.Column('qty', sa.INTEGER(), nullable=False),
        sa.Column('reward_coins', sa.INTEGER(), server_default=sa.text("'0'"), nullable=False),
        sa.Column('customer', sa.VARCHAR(), nullable=True),
        sa.Column('name', sa.VARCHAR(), nullable=True),
        sa.Column('image_url', sa.VARCHAR(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
