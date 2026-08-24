"""subscriptions_trial_payment

Revision ID: 62a9d4cc81e7
Revises: 03eb6a93e324
Create Date: 2026-08-24 08:36:30.979558
"""
import datetime
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '62a9d4cc81e7'
down_revision: Union[str, None] = '03eb6a93e324'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _trial_days() -> int:
    conn = op.get_bind()
    try:
        row = conn.execute(sa.text("SELECT value FROM settings WHERE key = 'trial_days'")).fetchone()
        if row and str(row[0]).strip().isdigit():
            return int(str(row[0]).strip())
    except Exception:
        pass
    return 7


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()
    if 'payment_logs' not in tables:
        op.create_table('payment_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vk_id', sa.Integer(), nullable=True),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('txn_id', sa.String(), nullable=True),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    if 'payment_orders' not in tables:
        op.create_table('payment_orders',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vk_id', sa.Integer(), nullable=False),
    sa.Column('amount_kop', sa.Integer(), nullable=False),
    sa.Column('period_days', sa.Integer(), server_default='30', nullable=False),
    sa.Column('dlc_codes', sa.String(), server_default='', nullable=False),
    sa.Column('provider', sa.String(), server_default='pay_gateway', nullable=False),
    sa.Column('gateway_txn_id', sa.String(), nullable=True),
    sa.Column('receipt_email', sa.String(), nullable=True),
    sa.Column('status', sa.String(), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['vk_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    if 'payment_orders' not in tables:
        with op.batch_alter_table('payment_orders', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_payment_orders_gateway_txn_id'), ['gateway_txn_id'], unique=False)

    user_cols = {c['name'] for c in insp.get_columns('users')}
    added_trial = False
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'trial_until' not in user_cols:
            batch_op.add_column(sa.Column('trial_until', sa.DateTime(), nullable=True))
            added_trial = True
        if 'subscription_until' not in user_cols:
            batch_op.add_column(sa.Column('subscription_until', sa.DateTime(), nullable=True))
        if 'subscription_dlc_codes' not in user_cols:
            batch_op.add_column(sa.Column('subscription_dlc_codes', sa.String(), nullable=True))

    if added_trial:
        until = datetime.datetime.utcnow() + datetime.timedelta(days=_trial_days())
        op.execute(
            sa.text("UPDATE users SET trial_until = :until WHERE trial_until IS NULL").bindparams(until=until)
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('subscription_dlc_codes')
        batch_op.drop_column('subscription_until')
        batch_op.drop_column('trial_until')
    with op.batch_alter_table('payment_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_orders_gateway_txn_id'))
    op.drop_table('payment_orders')
    op.drop_table('payment_logs')
