"""user_animal_openings

Revision ID: 4e488dbc9ec1
Revises: b23211b2df09
Create Date: 2026-08-22 15:48:52.925065
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = '4e488dbc9ec1'
down_revision: Union[str, None] = 'b23211b2df09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_animal_openings_tbl = sa.table(
    'user_animal_openings',
    sa.column('user_id', sa.Integer),
    sa.column('animal_id', sa.Integer),
    sa.column('opening_order', sa.Integer),
    sa.column('created_at', sa.DateTime),
)


def upgrade() -> None:
    from sqlalchemy import inspect

    conn = op.get_bind()
    if not inspect(conn).has_table("user_animal_openings"):
        op.create_table('user_animal_openings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('animal_id', sa.Integer(), nullable=False),
        sa.Column('opening_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['animal_id'], ['animals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'animal_id', name='uq_user_animal_openings')
        )

    if not inspect(conn).has_table("barnyard_slots"):
        return

    bs = sa.table(
        'barnyard_slots',
        sa.column('id', sa.Integer), sa.column('user_id', sa.Integer),
        sa.column('animal_id', sa.Integer), sa.column('opening_order', sa.Integer),
    )
    rows = conn.execute(
        sa.select(bs.c.user_id, bs.c.animal_id, bs.c.opening_order)
        .where(bs.c.animal_id.isnot(None))
        .order_by(bs.c.user_id, bs.c.id)
    ).fetchall()
    seen_pairs = set()
    next_order = {}
    for user_id, animal_id, slot_order in rows:
        if (user_id, animal_id) in seen_pairs:
            continue
        seen_pairs.add((user_id, animal_id))
        order = slot_order if slot_order is not None else next_order.get(user_id, 0) + 1
        next_order[user_id] = max(next_order.get(user_id, 0), order)
        conn.execute(
            user_animal_openings_tbl.insert().values(
                user_id=user_id, animal_id=animal_id, opening_order=order,
                created_at=sa.func.current_timestamp(),
            )
        )


def downgrade() -> None:
    op.drop_table('user_animal_openings')
