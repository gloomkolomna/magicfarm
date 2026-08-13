"""add logs table

Revision ID: 5fb69855f8ef
Revises: 57712155b338
Create Date: 2026-08-13 09:48:55.587672
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '5fb69855f8ef'
down_revision: Union[str, None] = '57712155b338'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('level', sa.String(), server_default='info', nullable=False),
        sa.Column('event', sa.String(), nullable=True),
        sa.Column('method', sa.String(), nullable=True),
        sa.Column('path', sa.String(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('client_ip', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_logs_created_at', 'logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_logs_created_at', table_name='logs')
    op.drop_table('logs')
