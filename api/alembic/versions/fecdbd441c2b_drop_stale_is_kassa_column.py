"""drop stale is_kassa column

Revision ID: fecdbd441c2b
Revises: 193bb603c6c5
Create Date: 2026-08-19 14:36:12.363351
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'fecdbd441c2b'
down_revision: Union[str, None] = '193bb603c6c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('production_templates')]
    if 'is_kassa' in cols:
        with op.batch_alter_table('production_templates', schema=None) as batch_op:
            batch_op.drop_column('is_kassa')


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('production_templates')]
    if 'is_kassa' not in cols:
        with op.batch_alter_table('production_templates', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_kassa', sa.Boolean(), server_default=sa.text("'0'"), nullable=False))
