"""wave_d_infirmary_pharmacy_otter

Revision ID: 00d670aa98b3
Revises: g3h4i5j6k7l8
Create Date: 2026-08-20 17:39:08.102287
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '00d670aa98b3'
down_revision: Union[str, None] = 'g3h4i5j6k7l8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pet_action_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('pet_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('date', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'pet_id', 'action', 'date', name='uq_practionlog_user_pet_action_date')
    )
    op.create_table('user_remedies',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('remedy_id', sa.Integer(), nullable=False),
    sa.Column('qty', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['remedy_id'], ['remedies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'remedy_id', name='uq_userremedy_user_remedy')
    )
    op.create_table('user_examine_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('part_code', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient_animals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'patient_id', 'part_code', name='uq_userexaminelog_user_patient_part')
    )
    op.create_table('remedy_device_cells',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('col', sa.Integer(), nullable=False),
    sa.Column('row', sa.Integer(), nullable=False),
    sa.Column('install_cards', sa.Integer(), server_default='10', nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('field_id', 'col', 'row', name='uq_remedydevicecell_field_col_row')
    )
    op.create_table('remedy_device_remedies',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('cell_id', sa.Integer(), nullable=False),
    sa.Column('remedy_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['cell_id'], ['remedy_device_cells.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['remedy_id'], ['remedies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cell_id', 'remedy_id', name='uq_remedydeviceremedy_cell_remedy')
    )
    op.create_table('user_remedy_devices',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('cell_id', sa.Integer(), nullable=False),
    sa.Column('build_status', sa.String(), server_default='building', nullable=False),
    sa.Column('accumulated', sa.Integer(), server_default='0', nullable=False),
    sa.Column('required', sa.Integer(), server_default='0', nullable=False),
    sa.Column('drawn_cards_json', sa.Text(), nullable=True),
    sa.Column('brew_card_id', sa.Integer(), nullable=True),
    sa.Column('brew_required', sa.Integer(), nullable=True),
    sa.Column('brew_accumulated', sa.Integer(), server_default='0', nullable=False),
    sa.Column('brew_dice_json', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['brew_card_id'], ['user_remedy_cards.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['cell_id'], ['remedy_device_cells.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'cell_id', name='uq_userremedydevice_user_cell')
    )
    with op.batch_alter_table('user_patient_states', schema=None) as batch_op:
        batch_op.add_column(sa.Column('penalty_due', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('user_patient_states', schema=None) as batch_op:
        batch_op.drop_column('penalty_due')

    op.drop_table('user_remedy_devices')
    op.drop_table('remedy_device_remedies')
    op.drop_table('remedy_device_cells')
    op.drop_table('user_examine_logs')
    op.drop_table('user_remedies')
    op.drop_table('pet_action_logs')
