"""add used to user potions

Revision ID: 5179db83e1ed
Revises: 27299be8c8a9
Create Date: 2026-08-16 21:31:35.081377
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '5179db83e1ed'
down_revision: Union[str, None] = '27299be8c8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_potions', sa.Column('used', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('user_potions', 'used')
