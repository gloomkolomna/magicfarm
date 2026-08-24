"""donor_cache_and_donor_exempt

Revision ID: 6a74c0b26e2c
Revises: 62a9d4cc81e7
Create Date: 2026-08-24 10:14:53.038052
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '6a74c0b26e2c'
down_revision: Union[str, None] = '62a9d4cc81e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()
    if 'donor_cache' not in tables:
        op.create_table('donor_cache',
        sa.Column('vk_id', sa.Integer(), nullable=False),
        sa.Column('is_don', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('don_since', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.Column('last_synced_at', sa.String(), server_default='', nullable=False),
        sa.PrimaryKeyConstraint('vk_id')
        )

    user_cols = {c['name'] for c in insp.get_columns('users')}
    added_exempt = False
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'donor_exempt' not in user_cols:
            batch_op.add_column(sa.Column('donor_exempt', sa.Boolean(), server_default='0', nullable=False))
            added_exempt = True

    if added_exempt:
        op.execute("UPDATE users SET donor_exempt = 1 WHERE role != 'admin'")


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('donor_exempt')
    op.drop_table('donor_cache')
