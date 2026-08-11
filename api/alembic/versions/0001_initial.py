"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === users ===
    op.create_table('users',
        sa.Column('vk_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='player'),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('crosses_balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('crosses_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('round', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('vk_id'),
    )

    # === settings ===
    op.create_table('settings',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )

    # === stitch_reports ===
    op.create_table('stitch_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('photo_url', sa.String(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.vk_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # === plants ===
    op.create_table('plants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('emoji', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=False, server_default='garden'),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('norm_per_crystal', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('bonus_text', sa.Text(), nullable=True),
        sa.Column('bonus_kind', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # === plots ===
    op.create_table('plots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(), nullable=False, server_default='planted'),
        sa.Column('accumulated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('required', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('crystal_color', sa.String(), nullable=True),
        sa.Column('crystal_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # === productions ===
    op.create_table('productions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='installed'),
        sa.Column('accumulated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('required', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'kind', name='uq_production_user_kind'),
    )

    # === products ===
    op.create_table('products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('emoji', sa.String(), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('stars', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('production_kind', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # === inventory ===
    op.create_table('inventory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_inventory_user_product'),
    )

    # === orders ===
    op.create_table('orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('reward_coins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('customer', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # === request_logs ===
    op.create_table('request_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('path', sa.String(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('client_ip', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # === СИДЫ ===
    # Растения 1 уровня (грядки). Атлас из правил Фермы (слайды 27–28).
    op.execute(
        "INSERT INTO plants (code, name, emoji, category, level, norm_per_crystal, bonus_text, bonus_kind, description) VALUES "
        "('jackobob',  'Джекобоб',        '🫘', 'garden', 1, 100, NULL,      NULL,    'Волшебный боб Джекобоба.'), "
        "('khlebozlak','Хлебозлак',        '🌾', 'garden', 1, 100, NULL,      NULL,    'Злак, из которого пекут магический хлеб.'), "
        "('moon_bean', 'Лунная фасоль',    '🫛', 'garden', 1, 100, NULL,      NULL,    'Светящаяся в темноте фасоль.'), "
        "('morels',    'Сморчки',          '🍄', 'garden', 1, 100, 'Гриб',    'image', 'Деликатесные весенние грибы.'), "
        "('nettle',    'Крапива',          '🌿', 'garden', 1, 100, NULL,      NULL,    'Жгучая, но полезная волшебная крапива.'), "
        "('ghost_fruit','Призрачный плод', '👻', 'garden', 1, 100, 'Ядовитое','text',  'Полупрозрачный ядовитый плод.'), "
        "('poison_mush','Ядовитые грибы',  '🍄', 'garden', 1, 100, 'Ядовитое','text',  'Из них варят яд на столе зельеварения.')"
    )

    # Товар «Яд» — производится из «Ядовитых грибов» на «Столе зельеварения».
    op.execute(
        "INSERT INTO products (code, name, emoji, plant_id, stars, production_kind) VALUES "
        "('poison', 'Яд', '🧪', "
        "(SELECT id FROM plants WHERE code='poison_mush'), 1, 'alchemy')"
    )

    # Настройки по умолчанию.
    op.execute(
        "INSERT INTO settings (key, value) VALUES "
        "('crystal_rate_variant', '1'), "
        "('auto_credit', '1'), "
        "('default_plant_qty', '7'), "
        "('production_required', '500'), "
        "('order_reward_per_unit', '5')"
    )


def downgrade() -> None:
    op.drop_table('request_logs')
    op.drop_table('orders')
    op.drop_table('inventory')
    op.drop_table('products')
    op.drop_table('productions')
    op.drop_table('plots')
    op.drop_table('plants')
    op.drop_table('stitch_reports')
    op.drop_table('settings')
    op.drop_table('users')
