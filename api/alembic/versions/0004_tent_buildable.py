"""tent_buildable

Revision ID: 0004_tent_buildable
Revises: 0003_user_crystal_norms
Create Date: 2026-08-09 00:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0004_tent_buildable'
down_revision: Union[str, None] = '0003_user_crystal_norms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('builder_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('build_status', sa.String(), nullable=False, server_default='slot'))
        batch_op.add_column(sa.Column('accumulated', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('required', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('crystal_color', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('crystal_count', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_tents_builder_user', 'users', ['builder_user_id'], ['vk_id'], ondelete='SET NULL'
        )

    # Существующие шатры — уже готовые (их создал админ раньше как объекты),
    # помечаем как построенные, чтобы не сломать текущие локации.
    op.execute("UPDATE tents SET build_status = 'built' WHERE build_status = 'slot'")


def downgrade() -> None:
    with op.batch_alter_table('tents', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tents_builder_user', type_='foreignkey')
        batch_op.drop_column('crystal_count')
        batch_op.drop_column('crystal_color')
        batch_op.drop_column('required')
        batch_op.drop_column('accumulated')
        batch_op.drop_column('build_status')
        batch_op.drop_column('builder_user_id')
