import datetime
from contextlib import contextmanager
from datetime import timedelta

from fastapi.testclient import TestClient

from db import get_db
from main import app
from models import User
from services.subscription import (
    days_left, extend_subscription, is_access_active, is_subscription_active,
    is_trial_active, set_trial_days,
)
from tests.conftest import TestingSessionLocal, _override_get_db, _setup_app


def _utcnow():
    return datetime.datetime.utcnow()


def _make_user(vk_id: int, role: str = "player", trial=None, sub=None, dlc=""):
    with TestingSessionLocal() as db:
        u = User(vk_id=vk_id, role=role, trial_until=trial, subscription_until=sub,
                 subscription_dlc_codes=dlc or None)
        db.add(u)
        db.commit()
        return u.vk_id


class _FakeUser:
    def __init__(self, trial=None, sub=None, dlc=""):
        self.trial_until = trial
        self.subscription_until = sub
        self.subscription_dlc_codes = dlc


@contextmanager
def token_client(vk_id: int):
    """Клиент с настоящим get_current_user + JWT — проверяет гейт 402 по-настоящему."""
    from services.auth import create_access_token

    _setup_app(app)
    app.dependency_overrides[get_db] = _override_get_db
    token = create_access_token(vk_id)
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c
    app.dependency_overrides.clear()


def test_access_flags():
    future = _utcnow() + timedelta(days=1)
    past = _utcnow() - timedelta(days=1)
    assert is_trial_active(_FakeUser(trial=future))
    assert not is_trial_active(_FakeUser(trial=past))
    assert not is_trial_active(_FakeUser(trial=None))
    assert is_subscription_active(_FakeUser(sub=future))
    assert not is_subscription_active(_FakeUser(sub=past))
    assert is_access_active(_FakeUser(trial=future))
    assert is_access_active(_FakeUser(sub=future))
    assert not is_access_active(_FakeUser(trial=past, sub=past))
    assert not is_access_active(_FakeUser())


def test_days_left():
    assert days_left(None) is None
    assert days_left(_utcnow() - timedelta(hours=1)) == 0
    assert days_left(_utcnow() + timedelta(hours=1)) == 1
    assert days_left(_utcnow() + timedelta(days=3, hours=1)) == 4
    assert days_left(_utcnow() + timedelta(days=3)) == 3


def test_extend_subscription_stacking():
    with TestingSessionLocal() as db:
        u = User(vk_id=990001)
        db.add(u)
        db.commit()

        extend_subscription(db, u, 30, ["infirmary"])
        first = u.subscription_until
        assert u.subscription_dlc_codes == "infirmary"

        extend_subscription(db, u, 30, ["infirmary", "brewery"])
        assert u.subscription_until == first + timedelta(days=30)
        assert u.subscription_dlc_codes == "infirmary,brewery"

        u.subscription_until = _utcnow() - timedelta(days=1)
        extend_subscription(db, u, 30, [])
        assert u.subscription_until - _utcnow() > timedelta(days=29)
        assert u.subscription_dlc_codes == ""


def test_set_trial_days_from_today():
    with TestingSessionLocal() as db:
        u = User(vk_id=990002, trial_until=_utcnow() + timedelta(days=5))
        db.add(u)
        db.commit()
        set_trial_days(db, u, 10)
        expected = _utcnow() + timedelta(days=10)
        assert abs((u.trial_until - expected).total_seconds()) < 5


def test_gate_402_blocks_mutations_without_access():
    _make_user(990010)
    with TestingSessionLocal() as db:
        u = db.query(User).filter(User.vk_id == 990010).first()
        u.trial_until = None
        u.subscription_until = None
        db.commit()

    with token_client(990010) as c:
        assert c.post("/api/farm/sell-surplus").status_code == 402
        assert c.get("/api/me").status_code == 200


def test_gate_allows_trial_subscription_and_admin():
    _make_user(990011, trial=_utcnow() + timedelta(days=1))
    _make_user(990012, sub=_utcnow() + timedelta(days=1))
    _make_user(990013, role="admin")

    for vk in (990011, 990012, 990013):
        with token_client(vk) as c:
            r = c.post("/api/farm/sell-surplus")
            assert r.status_code != 402


def test_me_reports_subscription_fields(player_client):
    r = player_client.get("/api/me")
    assert r.status_code == 200
    data = r.json()
    assert data["access_active"] is True
    assert data["trial_active"] is True
    assert data["subscription_active"] is False
    assert data["days_left"] == 7
    assert data["subscription_dlc_codes"] == []


def test_me_days_left_zero_when_expired():
    _make_user(990020, trial=_utcnow() - timedelta(days=1))
    with token_client(990020) as c:
        data = c.get("/api/me").json()
        assert data["access_active"] is False
        assert data["days_left"] == 0


def test_dlc_available_via_active_subscription(player_client, db):
    from models import Setting

    player_client.get("/api/me")
    db.add(Setting(key="locked_locations", value="infirmary,brewery"))
    db.commit()
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        u.subscription_until = _utcnow() + timedelta(days=5)
        u.subscription_dlc_codes = "infirmary"
        s.commit()

    from services.availability import location_lock_reason

    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        assert location_lock_reason("infirmary", u, s) is None
        assert location_lock_reason("brewery", u, s) is not None

        u.subscription_until = _utcnow() - timedelta(days=1)
        s.commit()
        assert location_lock_reason("infirmary", u, s) is not None


def test_admin_extend_trial(admin_client, db):
    _make_user(123)
    r = admin_client.post("/api/admin/players/123/trial", json={"days": 14})
    assert r.status_code == 200
    data = r.json()
    assert data["trial_until"] is not None
    parsed = datetime.datetime.fromisoformat(data["trial_until"])
    assert parsed - _utcnow() > timedelta(days=13)

    assert admin_client.post("/api/admin/players/123/trial", json={"days": 0}).status_code == 400
    assert admin_client.post("/api/admin/players/999999/trial", json={"days": 5}).status_code == 404
    assert player_client_post_trial_denied()


def player_client_post_trial_denied():
    from tests.conftest import make_user_client

    with make_user_client(124) as pc:
        return pc.post("/api/admin/players/123/trial", json={"days": 5}).status_code == 403


def test_finance_settings_admin_only(admin_client):
    assert admin_client.put("/api/admin/settings/trial_days", json={"value": "10"}).status_code == 200
    assert admin_client.get("/api/settings/trial_days").json()["value"] == "10"
    assert admin_client.put("/api/admin/settings/subscription_price_rub", json={"value": "350"}).status_code == 200
    assert admin_client.put("/api/admin/settings/subscription_price_rub_infirmary", json={"value": "75"}).status_code == 200
    assert admin_client.put("/api/admin/settings/subscription_price_rub_brewery", json={"value": "60"}).status_code == 200
    assert admin_client.put("/api/admin/settings/dlc_change_immediate", json={"value": "1"}).status_code == 200
    assert admin_client.put("/api/admin/settings/trial_days", json={"value": "-5"}).json()["value"] == "0"


def test_new_user_gets_trial_setting_days(db):
    from models import Setting
    from routes.auth import router  # noqa: F401

    db.add(Setting(key="trial_days", value="3"))
    db.commit()
    from services.subscription import get_trial_days
    assert get_trial_days(db) == 3
