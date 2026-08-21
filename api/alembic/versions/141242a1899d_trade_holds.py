"""trade holds

Revision ID: 141242a1899d
Revises: 7dad8928a586
Create Date: 2026-08-21 17:14:20.780644
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '141242a1899d'
down_revision: Union[str, None] = '7dad8928a586'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    if "trade_holds" not in set(insp.get_table_names()):
        op.create_table(
            'trade_holds',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('offer_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(), nullable=False),
            sa.Column('item_id', sa.Integer(), nullable=False),
            sa.Column('qty', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['offer_id'], ['trade_offers.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    op.drop_table('trade_holds')
