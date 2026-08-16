"""customers_table_orders_fulfilled_by

Revision ID: d956b42d4036
Revises: 2a78a22e8347
Create Date: 2026-08-16 12:05:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'd956b42d4036'
down_revision: Union[str, None] = '2a78a22e8347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CUSTOMER_NAMES = (
    "Леди Бейлин", "Иллюзионист Мерлин", "Крестьянка Бэт", "Крестьянин Том",
    "Травница Свентана", "Профессор Дамболдор", "Волшебница Альвева", "Палач Мор",
    "Ведьма Бригида", "Волшебник Рандольф", "Ученица Гильда", "Профессор Рон",
    "Господин Иоханн", "Поэт Вальтер", "Цветочница Колетта", "Маг Годвин",
    "Ведьма Груда", "Ведьма Доротея", "Водяная Акварис", "Тролль Гослин",
    "Воин Стасий", "Водяной Дионисий", "Болотная Иса", "Прокажённый Гус",
    "Хамон", "Разбойница Томасина", "Эльф Эверард", "Бусли",
    "Разбойник Гольём", "Библиотекарь Летард", "Книжница Элоиза", "Циркач Белкс",
    "Старец Эдрик", "Изобретатель Нигель", "Розамунда", "Гуннильда",
    "Фей Алан", "Прометеус", "Гном Дремотун", "Гном Гром",
    "Гном Плясун", "Султан Арагим", "Султан Эфиос", "Красавица Ева",
    "Художница Стефания", "Сэр Аорон", "Фея Аврора", "Король Артур",
    "Оборотень Рандус", "Старец Симонус", "Эльф Анарендил", "Эльфийка Хиварра",
    "Эльф Фараун", "Астроном Сириус", "Русалка Марин", "Профессор Сусанна",
    "Гадалка Сванекильда", "Ученица Холли", "Русалка Оресия", "Русалка Эделина",
    "Профессор Гилотта", "Иллюзионист Сфериус", "Волшебница Идонея", "Учёный Томас",
    "Профессор Кларисса", "Оборотень Уолк", "Мышиный воин Осборт", "Ледяная Сванекильда",
)


def upgrade() -> None:
    op.create_table('customers',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    customers_table = sa.table('customers', sa.column('name', sa.String))
    op.bulk_insert(customers_table, [{'name': n} for n in CUSTOMER_NAMES])

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fulfilled_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_orders_fulfilled_by', 'users', ['fulfilled_by'], ['vk_id'], ondelete='SET NULL')

    op.execute("UPDATE orders SET fulfilled_by = user_id WHERE status = 'fulfilled' AND user_id IS NOT NULL")


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_fulfilled_by', type_='foreignkey')
        batch_op.drop_column('fulfilled_by')

    op.drop_table('customers')
