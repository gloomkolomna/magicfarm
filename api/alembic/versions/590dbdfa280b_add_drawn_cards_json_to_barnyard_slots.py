"""add_drawn_cards_json_to_barnyard_slots

Revision ID: 590dbdfa280b
Revises: 482f88174e21
Create Date: 2026-08-11 10:53:01.811389
"""
from typing import Union
from alembic import op
import sqlalchemy as sa



revision: str = '590dbdfa280b'
down_revision: Union[str, None] = '482f88174e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('barnyard_slots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('drawn_cards_json', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('barnyard_slots', schema=None) as batch_op:
        batch_op.drop_column('drawn_cards_json')
