import json
import os
import sqlite3

import pytest


API_DIR = os.path.join(os.path.dirname(__file__), "..")
OLD_REV = "370efa6cb167"


@pytest.fixture
def migrated_db(tmp_path, monkeypatch):
    """Старая схема (как на проде до редизайна норм) + upgrade до head.

    Схема старой ревизии создаётся напрямую SQL (миграции проекта
    предполагают базу, созданную create_all), затем применяется
    реальный прогон alembic до head.
    """
    import config
    db_path = tmp_path / "farm_migration.db"
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            CREATE TABLE users (vk_id INTEGER PRIMARY KEY, role VARCHAR NOT NULL);
            CREATE TABLE house_builds (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
            CREATE TABLE user_crystal_norms (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                color VARCHAR NOT NULL, count INTEGER NOT NULL, value INTEGER NOT NULL);
            CREATE TABLE plots (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, plant_id INTEGER,
                qty INTEGER NOT NULL DEFAULT 1, required INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME);
            CREATE TABLE settings (key VARCHAR PRIMARY KEY, value VARCHAR);
            CREATE TABLE production_templates (
                id INTEGER PRIMARY KEY, code VARCHAR NOT NULL,
                name VARCHAR NOT NULL, emoji VARCHAR,
                required INTEGER NOT NULL DEFAULT 500,
                cards_to_draw INTEGER NOT NULL DEFAULT 3,
                surcharge INTEGER NOT NULL DEFAULT 30);
            CREATE TABLE user_recipes (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
            CREATE TABLE potion_recipes (
                id INTEGER PRIMARY KEY, code VARCHAR NOT NULL, name VARCHAR NOT NULL,
                level VARCHAR NOT NULL, ingredient_slots TEXT NOT NULL,
                bonus_code VARCHAR, reward_coins INTEGER NOT NULL DEFAULT 100,
                image_url VARCHAR);
            CREATE TABLE user_potions (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                potion_recipe_id INTEGER NOT NULL, bonus_code VARCHAR,
                activated BOOLEAN NOT NULL DEFAULT 0,
                acquired_at DATETIME NOT NULL,
                CONSTRAINT uq_userpotion_user_recipe UNIQUE (user_id, potion_recipe_id));
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY, user_id INTEGER, product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL, reward_coins INTEGER NOT NULL DEFAULT 0,
                customer VARCHAR, status VARCHAR NOT NULL DEFAULT 'open',
                name VARCHAR, image_url VARCHAR,
                created_at DATETIME, fulfilled_at DATETIME);
            CREATE TABLE stitch_reports (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                photo_before_url VARCHAR, photo_after_url VARCHAR NOT NULL,
                note TEXT, context_type VARCHAR, context_id INTEGER, cell_id INTEGER,
                status VARCHAR NOT NULL DEFAULT 'pending',
                reviewer_id INTEGER, reviewed_at DATETIME, created_at DATETIME);
        """)
        conn.execute("INSERT INTO alembic_version (version_num) VALUES (:r)", {"r": OLD_REV})
        conn.execute("INSERT INTO settings (key, value) VALUES ('house_material_norm', '150')")
        conn.execute("INSERT INTO settings (key, value) VALUES ('crystal_standard', :v)", {
            "v": json.dumps({
                "green": {"1": 11, "2": 22, "3": 33, "4": 44, "5": 55, "0": 500},
                "blue": {"1": 22, "2": 44, "3": 66, "4": 88, "5": 110, "0": 0},
                "violet": {"1": 33, "2": 66, "3": 99, "4": 132, "5": 165, "0": 700},
            }),
        })
        conn.execute("INSERT INTO users (vk_id, role) VALUES (1, 'player')")
        conn.execute("INSERT INTO users (vk_id, role) VALUES (2, 'player')")
        for cnt in range(1, 6):
            conn.execute(
                "INSERT INTO user_crystal_norms (user_id, color, count, value) "
                "VALUES (1, 'green', :c, :v)",
                {"c": cnt, "v": 10 * cnt},
            )
        conn.execute(
            "INSERT INTO user_crystal_norms (user_id, color, count, value) "
            "VALUES (1, 'treasure_green', 0, 500)"
        )
        conn.execute(
            "INSERT INTO plots (user_id, plant_id, qty, required, created_at) VALUES "
            "(1, 7, 2, 100, '2026-01-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO plots (user_id, plant_id, qty, required, created_at) VALUES "
            "(1, 7, 3, 101, '2026-01-02 00:00:00')"
        )
        conn.execute(
            "INSERT INTO orders (user_id, product_id, qty, status, fulfilled_at) VALUES "
            "(1, 9, 2, 'fulfilled', '2026-01-03 00:00:00')"
        )
        conn.execute(
            "INSERT INTO orders (user_id, product_id, qty, status) VALUES "
            "(NULL, 9, 1, 'open')"
        )
        conn.commit()
    finally:
        conn.close()

    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    command.upgrade(cfg, "head")
    yield str(db_path)


def _fetch(db_path, sql, args=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_migration_dice_norm_from_global_setting(migrated_db):
    rows = _fetch(migrated_db, "SELECT vk_id, dice_norm FROM users")
    assert all(r[1] == 150 for r in rows)


def test_migration_user_plant_norms_from_latest_plot(migrated_db):
    rows = _fetch(migrated_db, "SELECT user_id, plant_id, norm_per_unit FROM user_plant_norms")
    assert rows == [(1, 7, 34)]


def test_migration_trims_crystal_norms_to_base(migrated_db):
    rows = _fetch(migrated_db, "SELECT color, count, value FROM user_crystal_norms ORDER BY count")
    assert rows == [("treasure_green", 0, 500), ("green", 1, 10)]


def test_migration_converts_crystal_standard(migrated_db):
    rows = _fetch(migrated_db, "SELECT value FROM settings WHERE key = 'crystal_standard'")
    assert len(rows) == 1
    data = json.loads(rows[0][0])
    assert data["green"] == {"norm": 11, "treasure": 500}
    assert data["blue"] == {"norm": 22, "treasure": 0}
    assert data["violet"] == {"norm": 33, "treasure": 700}


def test_migration_removes_obsolete_settings(migrated_db):
    keys = _fetch(
        migrated_db,
        "SELECT key FROM settings WHERE key IN "
        "('crystal_rate_variant', 'house_material_norm', 'animal_production_norm', "
        "'study_norm_lvl1', 'study_norm_lvl2', 'study_norm_lvl3', "
        "'production_norm_lvl1', 'production_norm_lvl2', 'production_norm_lvl3')",
    )
    assert keys == []


def test_migration_new_columns_exist(migrated_db):
    house_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(house_builds)")]
    assert "last_die" in house_cols

    user_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(users)")]
    for col in ("dice_norm", "animal_product_norm", "study_norm_l1", "study_norm_l2", "study_norm_l3",
                "production_norm_l1", "production_norm_l2", "production_norm_l3"):
        assert col in user_cols

    recipe_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(user_recipes)")]
    assert "required" in recipe_cols

    pt_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(production_templates)")]
    assert "processing_crystal" in pt_cols

    order_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(orders)")]
    assert "customer_phrase" in order_cols
    assert "potion_recipe_id" in order_cols

    potion_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(user_potions)")]
    assert "used" in potion_cols

    storage_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(barnyard_storage)")]
    assert {"user_id", "product_id", "qty"} <= set(storage_cols)

    withdrawal_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(barnyard_withdrawals)")]
    assert {"user_id", "product_id", "qty", "required", "status"} <= set(withdrawal_cols)


def test_migration_seeds_customers(migrated_db):
    rows = _fetch(migrated_db, "SELECT COUNT(*) FROM customers")
    assert rows[0][0] == 68
    names = {r[0] for r in _fetch(migrated_db, "SELECT name FROM customers")}
    assert "Леди Бейлин" in names
    assert "Ледяная Сванекильда" in names


def test_migration_orders_single_model(migrated_db):
    order_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(orders)")]
    assert "user_id" not in order_cols
    assert "fulfilled_by" not in order_cols
    assert "fulfilled_at" not in order_cols
    uo_cols = [r[1] for r in _fetch(migrated_db, "PRAGMA table_info(user_orders)")]
    assert {"user_id", "order_id", "taken_at", "fulfilled_at", "reward_coins"} <= set(uo_cols)
    rows = _fetch(migrated_db, "SELECT status FROM orders ORDER BY id")
    assert rows == [("open",), ("open",)]


PRE_GHOST_PURGE_REV = "ba7f5ee8385b"


@pytest.fixture
def ghost_purge_db(tmp_path, monkeypatch):
    """База на ревизии перед чисткой загонов-призраков, с засеянными призраками.

    Таблицы fields/field_cells/barnyard_slots создаются не миграциями, а create_all,
    поэтому после upgrade до PRE_GHOST_PURGE_REV они досоздаются по моделям.
    """
    import config
    db_path = tmp_path / "farm_ghost_purge.db"
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            CREATE TABLE users (vk_id INTEGER PRIMARY KEY, role VARCHAR NOT NULL);
            CREATE TABLE house_builds (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
            CREATE TABLE user_crystal_norms (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                color VARCHAR NOT NULL, count INTEGER NOT NULL, value INTEGER NOT NULL);
            CREATE TABLE plots (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, plant_id INTEGER,
                qty INTEGER NOT NULL DEFAULT 1, required INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME);
            CREATE TABLE settings (key VARCHAR PRIMARY KEY, value VARCHAR);
            CREATE TABLE production_templates (
                id INTEGER PRIMARY KEY, code VARCHAR NOT NULL,
                name VARCHAR NOT NULL, emoji VARCHAR,
                required INTEGER NOT NULL DEFAULT 500,
                cards_to_draw INTEGER NOT NULL DEFAULT 3,
                surcharge INTEGER NOT NULL DEFAULT 30);
            CREATE TABLE user_recipes (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
            CREATE TABLE potion_recipes (
                id INTEGER PRIMARY KEY, code VARCHAR NOT NULL, name VARCHAR NOT NULL,
                level VARCHAR NOT NULL, ingredient_slots TEXT NOT NULL,
                bonus_code VARCHAR, reward_coins INTEGER NOT NULL DEFAULT 100,
                image_url VARCHAR);
            CREATE TABLE user_potions (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                potion_recipe_id INTEGER NOT NULL, bonus_code VARCHAR,
                activated BOOLEAN NOT NULL DEFAULT 0,
                acquired_at DATETIME NOT NULL,
                CONSTRAINT uq_userpotion_user_recipe UNIQUE (user_id, potion_recipe_id));
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY, user_id INTEGER, product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL, reward_coins INTEGER NOT NULL DEFAULT 0,
                customer VARCHAR, status VARCHAR NOT NULL DEFAULT 'open',
                name VARCHAR, image_url VARCHAR,
                created_at DATETIME, fulfilled_at DATETIME);
            CREATE TABLE stitch_reports (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                photo_before_url VARCHAR, photo_after_url VARCHAR NOT NULL,
                note TEXT, context_type VARCHAR, context_id INTEGER, cell_id INTEGER,
                status VARCHAR NOT NULL DEFAULT 'pending',
                reviewer_id INTEGER, reviewed_at DATETIME, created_at DATETIME);
        """)
        conn.execute("INSERT INTO alembic_version (version_num) VALUES (:r)", {"r": OLD_REV})
        conn.execute("INSERT INTO users (vk_id, role) VALUES (1, 'player')")
        conn.commit()
    finally:
        conn.close()

    from alembic import command
    from alembic.config import Config
    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    command.upgrade(cfg, PRE_GHOST_PURGE_REV)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import Base, BarnyardSlot, Field, FieldCell
    eng = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()
    try:
        s.add(Field(id=9, code="f9", name="Скотный", cols=4, rows=2))
        s.flush()
        in_grid = FieldCell(id=100, field_id=9, col=1, row=1, kind="barnyard")
        out_grid = FieldCell(id=101, field_id=9, col=2, row=2, kind="barnyard")
        bed = FieldCell(id=102, field_id=9, col=0, row=0, kind="bed")
        s.add_all([in_grid, out_grid, bed])
        s.flush()
        s.add(BarnyardSlot(id=1, user_id=1, animal_id=1, cell_id=100, status="ready"))
        s.add(BarnyardSlot(id=2, user_id=1, animal_id=1, cell_id=None, status="ready"))
        s.add(BarnyardSlot(id=3, user_id=1, animal_id=1, cell_id=101, status="ready"))
        s.add(BarnyardSlot(id=4, user_id=1, animal_id=1, cell_id=102, status="ready"))
        s.add(BarnyardSlot(id=6, user_id=1, animal_id=1, cell_id=99999, status="ready"))
        s.commit()
    finally:
        s.close()
    eng.dispose()

    command.upgrade(cfg, "head")
    yield str(db_path)


def test_migration_purges_barnyard_ghost_slots(ghost_purge_db):
    rows = _fetch(ghost_purge_db, "SELECT id, cell_id FROM barnyard_slots")
    assert rows == [(1, 100)]
