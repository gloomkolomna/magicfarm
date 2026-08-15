"""norms_redesign_dice_cache

Revision ID: befe7d004cbd
Revises: 370efa6cb167
Create Date: 2026-08-15 19:40:42.305531
"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa



revision: str = 'befe7d004cbd'
down_revision: Union[str, None] = '370efa6cb167'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_plant_norms',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('plant_id', sa.Integer(), nullable=False),
    sa.Column('norm_per_unit', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.vk_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'plant_id', name='uq_userplantnorm_user_plant')
    )
    with op.batch_alter_table('house_builds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_die', sa.Integer(), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dice_norm', sa.Integer(), nullable=True))

    conn = op.get_bind()

    conn.execute(sa.text(
        "UPDATE users SET dice_norm = COALESCE("
        "(SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'house_material_norm'), 200)"
    ))

    conn.execute(sa.text(
        "INSERT INTO user_plant_norms (user_id, plant_id, norm_per_unit, created_at) "
        "SELECT p.user_id, p.plant_id, (p.required + p.qty - 1) / p.qty, p.created_at "
        "FROM plots p "
        "WHERE p.plant_id IS NOT NULL AND p.qty > 0 AND p.required > 0 "
        "AND p.id = (SELECT p2.id FROM plots p2 "
        "WHERE p2.user_id = p.user_id AND p2.plant_id = p.plant_id "
        "ORDER BY p2.created_at DESC, p2.id DESC LIMIT 1)"
    ))

    conn.execute(sa.text("DELETE FROM user_crystal_norms WHERE count > 1"))

    row = conn.execute(sa.text("SELECT value FROM settings WHERE key = 'crystal_standard'")).fetchone()
    if row is not None:
        try:
            data = json.loads(row[0])
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict):
            new = {}
            ok = True
            for color in ("green", "blue", "violet"):
                per = data.get(color)
                if not isinstance(per, dict):
                    ok = False
                    break
                if "norm" in per:
                    new[color] = {"norm": int(per["norm"]), "treasure": int(per.get("treasure", 0))}
                    continue
                norm = per.get("1", per.get(1))
                treasure = per.get("0", per.get(0, 0))
                if norm is None:
                    ok = False
                    break
                new[color] = {"norm": int(norm), "treasure": int(treasure or 0)}
            if ok:
                conn.execute(
                    sa.text("UPDATE settings SET value = :v WHERE key = 'crystal_standard'"),
                    {"v": json.dumps(new)},
                )
            else:
                conn.execute(sa.text("DELETE FROM settings WHERE key = 'crystal_standard'"))

    conn.execute(sa.text(
        "DELETE FROM settings WHERE key IN "
        "('crystal_rate_variant', 'house_material_norm', 'animal_production_norm')"
    ))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('dice_norm')

    with op.batch_alter_table('house_builds', schema=None) as batch_op:
        batch_op.drop_column('last_die')

    op.drop_table('user_plant_norms')
