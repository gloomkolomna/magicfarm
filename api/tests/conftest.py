import os
import sys
import tempfile

# In-memory SQLite для тестов (чистая БД на каждый запуск процесса).
# Должно быть установлено ДО импорта config/db.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "dev"
os.environ["DEV_LOGIN_ENABLED"] = "true"
os.environ["ADMIN_VK_IDS"] = "400977,795384"
os.environ["SECRET_KEY"] = "test-secret-not-for-prod"
os.environ["VK_APP_SECRET"] = "test-secret"
os.environ["S3_ENABLED"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool, text
from sqlalchemy.orm import sessionmaker

from db import get_db
from deps import get_current_user
from models import Base, User, UserCrystalNorm
from routes.settings import DEFAULT_CARD_NORMS, CRYSTAL_COLORS

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_farm():
    """Сиды растений, товара и настроек — нужны почти во всех тестах."""
    now = "2026-08-08 00:00:00"
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO plants (code, name, emoji, category, level, norm_per_crystal, bonus_text, bonus_kind, description) VALUES "
            "('jackobob',  'Джекобоб',        '🫘', 'garden', 1, 100, NULL,      NULL,    'Боб'), "
            "('khlebozlak','Хлебозлак',        '🌾', 'garden', 1, 100, NULL,      NULL,    'Злак'), "
            "('morels',    'Сморчки',          '🍄', 'garden', 1, 100, 'Гриб',    'image', 'Грибы'), "
            "('poison_mush','Ядовитые грибы',  '🍄', 'garden', 1, 100, 'Ядовитое','text',  'Яд')"
        ))
        conn.execute(text(
            "INSERT INTO products (code, name, emoji, plant_id, stars, production_kind) VALUES "
            "('poison', 'Яд', '🧪', "
            "(SELECT id FROM plants WHERE code='poison_mush'), 1, 'alchemy')"
        ))
        conn.execute(text(
            "INSERT INTO production_templates (code, name, emoji, required, cards_to_draw, surcharge) VALUES "
            "('alchemy', 'Стол зельеварения', '🔮', 500, 5, 40), "
            "('sewing', 'Шатёр портнихи', '🧵', 500, 3, 30), "
            "('workshop', 'Мастерская', '🔨', 500, 4, 35), "
            "('barnyard', 'Шатёр скотного двора', '🏚️', 500, 2, 30)"
        ))
        conn.execute(text(
            "INSERT INTO settings (key, value) VALUES "
            "('auto_credit', '1'), "
            "('default_plant_qty', '7'), "
            "('production_required', '500'), "
            "('order_reward_per_unit', '5'), "
            "('animal_build_norm', '1000'), "
            "('sale_price_ratio', '0.5')"
        ))
        conn.execute(text(
            "INSERT INTO animals (code, name, emoji, product_name, sort_order) VALUES "
            "('wool_sheep', 'Ватная овечка', '🐑', 'Радужная шерсть', 1), "
            "('easter_bunny', 'Пасхальный кролик', '🐰', 'Сладкое яйцо', 2)"
        ))
        conn.execute(text(
            "INSERT INTO pets (code, name, emoji, bonus_kind, bonus_description) VALUES "
            "('dragon', 'Дракон Эфир', '🐉', 'order_coins', '+5 монет к заказу'), "
            "('fox', 'Лис Сильварис', '🦊', 'harvest_orchard', '+1 к урожаю сада')"
        ))
        conn.execute(text(
            "INSERT INTO potion_recipes (code, name, level, ingredient_slots, bonus_code, reward_coins) VALUES "
            "('sonnoe_prorochestvo', 'Сонное пророчество', 'green', '[\"plant_garden\",\"plant_garden\",\"plant_garden\",\"alchemy\"]', 'skip_plant_stitch', 100)"
        ))
        conn.execute(text(
            "INSERT INTO recipes (plant_id, product_id, level) VALUES "
            "((SELECT id FROM plants WHERE code='poison_mush'), "
            "(SELECT id FROM products WHERE code='poison'), 1)"
        ))
        for color in ("green", "blue", "violet"):
            for value in range(1, 6):
                conn.execute(text(
                    "INSERT INTO crystal_cards (color, value, is_treasure) VALUES "
                    f"('{color}', {value}, 0)"
                ))
        for color in ("green", "blue", "violet"):
            conn.execute(text(
                "INSERT INTO crystal_cards (color, value, is_treasure) VALUES "
                f"('{color}', 0, 1)"
            ))
        conn.execute(text(
            "INSERT INTO level_gates (level, coins_required, plots_required) VALUES "
            "(0, 0, 0), "
            "(1, 800, 2), "
            "(2, 1600, 4), "
            "(3, 2500, 6)"
        ))
        conn.commit()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    seed_farm()
    yield
    Base.metadata.drop_all(bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _deny_user():
    """Для клиента без авторизации — имитируем 401 через зависимость."""
    from fastapi import HTTPException, status
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_default_norms(db, user_id: int) -> None:
    """Заполняет персональные нормы игрока базами по умолчанию (для существующих тестов)."""
    for color in CRYSTAL_COLORS:
        db.add(UserCrystalNorm(user_id=user_id, color=color, count=1, value=DEFAULT_CARD_NORMS[color]))
    u = db.query(User).filter(User.vk_id == user_id).first()
    if u is not None:
        u.study_norm_l1 = 500
        u.study_norm_l2 = 1000
        u.study_norm_l3 = 1500
        u.production_norm_l1 = 100
        u.production_norm_l2 = 200
        u.production_norm_l3 = 300
    db.commit()


def _make_user_override(vk_id: int, role: str):
    """Фабрика override'ов get_current_user под конкретную роль.

    Generator-форма: сессия держится открытой до конца запроса, чтобы
    возвращённый user оставался bound (маршруты читают user.onboarding_done и др.).
    """
    def _override():
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.vk_id == vk_id).first()
            if user is None:
                user = User(vk_id=vk_id, role=role, unlocked_pets=5, unlocked_barnyard=8)
                db.add(user)
                db.commit()
                db.refresh(user)
                _seed_default_norms(db, user.vk_id)
                user.onboarding_done = True
                db.commit()
            yield user
        finally:
            db.close()
    return _override


def _make_user_override_no_onboarding(vk_id: int, role: str):
    """Как _make_user_override, но без онбординга (для тестов блокировки)."""
    def _override():
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.vk_id == vk_id).first()
            if user is None:
                user = User(vk_id=vk_id, role=role)
                db.add(user)
                db.commit()
                db.refresh(user)
            yield user
        finally:
            db.close()
    return _override


def _setup_app(app):
    """Общие настройки app для всех фикстур-клиентов."""
    app.dependency_overrides[get_db] = _override_get_db
    # Middleware должен писать логи в тестовую БД.
    app.state.session_factory = TestingSessionLocal


@pytest.fixture
def client():
    """Клиент без авторизации — для тестов health/public и 401."""
    from main import app
    _setup_app(app)
    app.dependency_overrides[get_current_user] = _deny_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client():
    """Клиент, авторизованный как admin (vk_id=400977)."""
    from main import app
    _setup_app(app)
    app.dependency_overrides[get_current_user] = _make_user_override(400977, "admin")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def player_client():
    """Клиент, авторизованный как player (vk_id=123)."""
    from main import app
    _setup_app(app)
    app.dependency_overrides[get_current_user] = _make_user_override(123, "player")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def uploads_tmp(monkeypatch):
    import config
    tmp = tempfile.mkdtemp(prefix="farm_test_uploads_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    yield tmp
    for name in os.listdir(tmp):
        os.remove(os.path.join(tmp, name))
    os.rmdir(tmp)


def make_user_client(vk_id: int, role: str = "player"):
    """Создаёт TestClient от имени произвольного игрока.

    Менеджер контекста: восстанавливает предыдущий override get_current_user на выходе.
    """
    from contextlib import contextmanager
    from main import app
    from fastapi.testclient import TestClient

    @contextmanager
    def _ctx():
        _setup_app(app)
        prev = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides[get_current_user] = _make_user_override(vk_id, role)
        with TestClient(app) as c:
            yield c
        if prev is not None:
            app.dependency_overrides[get_current_user] = prev
        else:
            app.dependency_overrides.pop(get_current_user, None)

    return _ctx()


def make_user_client_no_onboarding(vk_id: int, role: str = "player"):
    """TestClient от имени игрока БЕЗ онбординга (для тестов блокировки)."""
    from contextlib import contextmanager
    from main import app
    from fastapi.testclient import TestClient

    @contextmanager
    def _ctx():
        _setup_app(app)
        prev = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides[get_current_user] = _make_user_override_no_onboarding(vk_id, role)
        with TestClient(app) as c:
            yield c
        if prev is not None:
            app.dependency_overrides[get_current_user] = prev
        else:
            app.dependency_overrides.pop(get_current_user, None)

    return _ctx()
