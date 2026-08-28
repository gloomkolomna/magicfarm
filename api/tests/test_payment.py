import datetime
import hashlib
import hmac
import json
from datetime import timedelta

import config
from models import PaymentOrder, User
from services.subscription import price_rub_for
from tests.conftest import TestingSessionLocal


def _utcnow():
    return datetime.datetime.utcnow()


def _enable_gateway(monkeypatch, txn="farm-order-1"):
    monkeypatch.setattr(config, "PAY_GATEWAY_ENABLED", True)
    monkeypatch.setattr(config, "PAY_GATEWAY_GAME_ID", "farm")
    monkeypatch.setattr(config, "PAY_GATEWAY_WEBHOOK_SECRET", "test-webhook-secret")

    def fake_create_order(vk_id, amount_kop, description, receipt_email=None):
        return {"transaction_id": txn, "payment_url": f"https://gw/pay/{txn}",
                "amount_kop": amount_kop, "expires_at": "2030-01-01T00:00:00Z"}

    import services.pay_gateway_client as client
    monkeypatch.setattr(client, "create_order", fake_create_order)


def _sign(payload: dict) -> dict:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(b"test-webhook-secret", raw, hashlib.sha256).hexdigest()
    return {"content": raw.decode("utf-8"), "headers": {"X-Pay-Signature": sig}}


def _order(db, **kw):
    defaults = dict(vk_id=123, amount_kop=35000, period_days=30, dlc_codes="infirmary",
                    kind="subscription", status="pending", gateway_txn_id="farm-order-1")
    defaults.update(kw)
    o = PaymentOrder(**defaults)
    db.add(o)
    db.commit()
    return o


def test_price_endpoint(player_client):
    r = player_client.get("/api/payment/price")
    assert r.status_code == 200
    data = r.json()
    assert data["period_days"] == 30
    assert data["base_rub"] == 300
    assert {d["code"]: d["price_rub"] for d in data["dlc"]} == {"infirmary": 50, "brewery": 50}


def test_public_pricing_no_auth(client):
    r = client.get("/api/public/pricing")
    assert r.status_code == 200
    data = r.json()
    assert data["period_days"] == 30
    assert data["base_rub"] == 300
    assert {d["code"]: d["name"] for d in data["dlc"]} == {
        "infirmary": "Лечебница",
        "brewery": "Зельеварение",
    }
    assert {d["code"]: d["price_rub"] for d in data["dlc"]} == {
        "infirmary": 50,
        "brewery": 50,
    }


def test_public_pricing_reflects_settings(client, db):
    from models import Setting

    db.add(Setting(key="subscription_price_rub", value="400"))
    db.add(Setting(key="subscription_price_rub_brewery", value="70"))
    db.commit()

    r = client.get("/api/public/pricing")
    assert r.status_code == 200
    data = r.json()
    assert data["base_rub"] == 400
    assert {d["code"]: d["price_rub"] for d in data["dlc"]} == {
        "infirmary": 50,
        "brewery": 70,
    }


def test_create_order_disabled(player_client):
    assert config.PAY_GATEWAY_ENABLED is False
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 503


def test_create_order_happy_path(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["amount_rub"] == 350
    assert data["amount_kop"] == 35000
    assert data["period_days"] == 30
    assert data["dlc_codes"] == ["infirmary"]
    assert data["payment_url"].startswith("https://gw/pay/")
    assert data["transaction_id"] == "farm-order-1"

    with TestingSessionLocal() as db:
        o = db.query(PaymentOrder).filter(PaymentOrder.id == data["order_id"]).first()
        assert o.status == "pending"
        assert o.vk_id == 123
        assert o.amount_kop == 35000


def test_create_order_blocked_during_trial(player_client, monkeypatch):
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 403
    assert "пробного периода" in r.json()["detail"]

    with TestingSessionLocal() as db:
        assert db.query(PaymentOrder).count() == 0


def test_create_order_allowed_after_trial_end(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    assert r.json()["amount_rub"] == 300


def test_renewal_allowed_with_trial_overlap(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=5, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    assert r.json()["kind"] == "subscription"
    assert r.json()["amount_rub"] == 350


def test_create_order_unknown_dlc(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["castle"], "receipt_email": "player@example.com"})
    assert r.status_code == 400


def test_create_order_requires_email(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": []})
    assert r.status_code == 422
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "not-an-email"})
    assert r.status_code == 400


def test_create_order_stores_email(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "  Player@Example.COM "})
    assert r.status_code == 200
    with TestingSessionLocal() as db:
        o = db.query(PaymentOrder).filter(PaymentOrder.id == r.json()["order_id"]).first()
        assert o.receipt_email == "player@example.com"


def test_price_calculation_with_settings(db, player_client):
    from models import Setting
    from routes.settings import set_locked_locations

    db.add(Setting(key="subscription_price_rub", value="400"))
    db.add(Setting(key="subscription_price_rub_brewery", value="70"))
    db.commit()
    assert price_rub_for(db, ["brewery", "infirmary"]) == 400 + 70 + 50


def _activate_subscription(vk_id=123, days=10, codes="infirmary"):
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        u.subscription_until = _utcnow() + timedelta(days=days)
        u.subscription_dlc_codes = codes
        s.commit()


def _expire_trial(vk_id=123):
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        u.trial_until = _utcnow() - timedelta(days=1)
        s.commit()


def test_dlc_topup_order_prorated(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=10, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary", "brewery"], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "dlc_topup"
    assert data["amount_rub"] == 17
    assert data["amount_kop"] == 1700
    assert data["period_days"] == 10
    assert data["dlc_codes"] == ["brewery"]

    with TestingSessionLocal() as db2:
        o = db2.query(PaymentOrder).filter(PaymentOrder.id == data["order_id"]).first()
        assert o.kind == "dlc_topup"
        assert o.dlc_codes == "brewery"
        assert o.amount_kop == 1700


def test_dlc_removal_blocked_while_active(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=10, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["brewery"], "receipt_email": "player@example.com"})
    assert r.status_code == 409

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 409


def test_dlc_same_set_renews_full_price(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=5, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "subscription"
    assert data["amount_rub"] == 350
    assert data["period_days"] == 30


def test_price_topup_for_active_subscriber(player_client, db):
    player_client.get("/api/me")
    _activate_subscription(days=10, codes="infirmary")

    r = player_client.get("/api/payment/price")
    assert r.status_code == 200
    data = r.json()
    assert data["topup_days_left"] == 10
    prices = {d["code"]: d["topup_rub"] for d in data["dlc"]}
    assert prices["infirmary"] is None
    assert prices["brewery"] == 17


def test_price_no_topup_without_subscription(player_client, db):
    player_client.get("/api/me")
    r = player_client.get("/api/payment/price")
    assert r.status_code == 200
    data = r.json()
    assert data["topup_days_left"] is None
    assert all(d["topup_rub"] is None for d in data["dlc"])


def test_expired_pending_cancelled_on_new_order(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch, txn="farm-order-2")
    with TestingSessionLocal() as s:
        old = _order(s, gateway_txn_id="farm-old", status="pending",
                     created_at=_utcnow() - timedelta(hours=2))
        old_id = old.id
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    with TestingSessionLocal() as s:
        old = s.query(PaymentOrder).filter(PaymentOrder.id == old_id).first()
        assert old.status == "cancelled"


def test_webhook_bad_signature(player_client, monkeypatch, db):
    _enable_gateway(monkeypatch)
    _order(db)
    r = player_client.post(
        "/api/payment/webhook",
        content=json.dumps({"transaction_id": "farm-order-1"}),
        headers={"X-Pay-Signature": "bad"},
    )
    assert r.status_code == 401


def test_webhook_game_mismatch(player_client, monkeypatch, db):
    _enable_gateway(monkeypatch)
    _order(db)
    body = _sign({"transaction_id": "farm-order-1", "game_id": "dragons", "vk_id": 123, "amount_kop": 35000})
    r = player_client.post("/api/payment/webhook", **body)
    assert r.status_code == 400


def test_webhook_success_extends_subscription(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _order(db)
    before = _utcnow()
    body = _sign({"transaction_id": "farm-order-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 35000, "status": "success", "moneta_operation_id": "op-1"})
    r = player_client.post("/api/payment/webhook", **body)
    assert r.status_code == 200

    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        o = s.query(PaymentOrder).filter(PaymentOrder.gateway_txn_id == "farm-order-1").first()
        assert o.status == "success"
        assert o.completed_at is not None
        assert u.subscription_dlc_codes == "infirmary"
        until = u.subscription_until - before
        assert until > timedelta(days=29) and until < timedelta(days=31)


def test_webhook_idempotent(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _order(db)
    body = _sign({"transaction_id": "farm-order-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 35000, "status": "success"})
    assert player_client.post("/api/payment/webhook", **body).status_code == 200
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        first = u.subscription_until
    assert player_client.post("/api/payment/webhook", **body).status_code == 200
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        assert u.subscription_until == first


def test_webhook_amount_mismatch(player_client, monkeypatch, db):
    _enable_gateway(monkeypatch)
    _order(db)
    body = _sign({"transaction_id": "farm-order-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 34999, "status": "success"})
    assert player_client.post("/api/payment/webhook", **body).status_code == 400


def test_webhook_vk_mismatch(player_client, monkeypatch, db):
    _enable_gateway(monkeypatch)
    _order(db)
    body = _sign({"transaction_id": "farm-order-1", "game_id": "farm", "vk_id": 999,
                  "amount_kop": 35000, "status": "success"})
    assert player_client.post("/api/payment/webhook", **body).status_code == 400


def test_webhook_stacks_on_active_subscription(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _order(db)
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        u.subscription_until = _utcnow() + timedelta(days=10)
        u.subscription_dlc_codes = ""
        s.commit()
    body = _sign({"transaction_id": "farm-order-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 35000, "status": "success"})
    assert player_client.post("/api/payment/webhook", **body).status_code == 200
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        assert u.subscription_until - _utcnow() > timedelta(days=39)


def test_webhook_dlc_topup_merges_codes(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _order(db, gateway_txn_id="farm-topup-1", kind="dlc_topup", amount_kop=1700,
           period_days=10, dlc_codes="brewery")
    _activate_subscription(days=10, codes="infirmary")
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        until_before = u.subscription_until
    body = _sign({"transaction_id": "farm-topup-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 1700, "status": "success", "moneta_operation_id": "op-top"})
    r = player_client.post("/api/payment/webhook", **body)
    assert r.status_code == 200

    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        o = s.query(PaymentOrder).filter(PaymentOrder.gateway_txn_id == "farm-topup-1").first()
        assert o.status == "success"
        assert sorted(u.subscription_dlc_codes.split(",")) == ["brewery", "infirmary"]
        assert abs((u.subscription_until - until_before).total_seconds()) < 5


def test_webhook_dlc_topup_idempotent(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _order(db, gateway_txn_id="farm-topup-1", kind="dlc_topup", amount_kop=1700,
           period_days=10, dlc_codes="brewery")
    _activate_subscription(days=10, codes="infirmary")
    body = _sign({"transaction_id": "farm-topup-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 1700, "status": "success"})
    assert player_client.post("/api/payment/webhook", **body).status_code == 200
    assert player_client.post("/api/payment/webhook", **body).status_code == 200
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        assert sorted(u.subscription_dlc_codes.split(",")) == ["brewery", "infirmary"]


def test_order_status_own_and_foreign(player_client, db):
    _order(db)
    r = player_client.get("/api/payment/orders/1")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"

    from tests.conftest import make_user_client
    with make_user_client(124) as other:
        assert other.get("/api/payment/orders/1").status_code == 404


def test_admin_payment_orders_and_cancel(admin_client, monkeypatch, db):
    from models import User as U
    db.add(U(vk_id=123))
    db.add(U(vk_id=124))
    db.commit()
    _enable_gateway(monkeypatch)
    _order(db, status="pending")
    _order(db, vk_id=124, gateway_txn_id="farm-order-2", amount_kop=30000, dlc_codes="", status="success")

    r = admin_client.get("/api/admin/payment-orders")
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = admin_client.get("/api/admin/payment-orders?status_filter=pending")
    assert len(r.json()) == 1

    r = admin_client.post("/api/admin/payment-orders/1/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    r = admin_client.post("/api/admin/payment-orders/1/cancel")
    assert r.json()["status"] == "cancelled"

    assert admin_client.post("/api/admin/payment-orders/999/cancel").status_code == 404

    logs = admin_client.get("/api/admin/payment-logs")
    assert logs.status_code == 200
    actions = [l["action"] for l in logs.json()]
    assert "cancelled_by_admin" in actions

    from tests.conftest import make_user_client
    with make_user_client(124) as pc:
        assert pc.get("/api/admin/payment-orders").status_code == 403


def test_readonly_player_can_pay_subscription(monkeypatch):
    from tests.test_player_status import _auth, _seed_user, _token, token_client

    _enable_gateway(monkeypatch)
    _seed_user(123, status="readonly")
    _expire_trial()
    with token_client() as c:
        r = c.post(
            "/api/payment/create-order",
            json={"dlc_codes": ["infirmary"], "receipt_email": "ro@example.com"},
            headers=_auth(_token(123)),
        )
        assert r.status_code == 200
        assert r.json()["amount_rub"] == 350


def test_readonly_player_price_available(monkeypatch):
    from tests.test_player_status import _auth, _seed_user, _token, token_client

    _seed_user(123, status="readonly")
    with token_client() as c:
        r = c.get("/api/payment/price", headers=_auth(_token(123)))
        assert r.status_code == 200
        assert {d["code"]: d["price_rub"] for d in r.json()["dlc"]} == {"infirmary": 50, "brewery": 50}


def test_no_access_player_can_pay_subscription(monkeypatch):
    from models import User
    from tests.test_player_status import _auth, _token, token_client

    _enable_gateway(monkeypatch)
    with TestingSessionLocal() as db:
        db.add(User(vk_id=555, role="player", status="active"))
        db.commit()
    with token_client() as c:
        r = c.post(
            "/api/payment/create-order",
            json={"dlc_codes": [], "receipt_email": "na@example.com"},
            headers=_auth(_token(555)),
        )
        assert r.status_code == 200
        assert r.json()["amount_rub"] == 300


def test_blocked_player_cannot_pay_subscription(monkeypatch):
    from tests.test_player_status import _auth, _seed_user, _token, token_client

    _enable_gateway(monkeypatch)
    _seed_user(123, status="blocked")
    with token_client() as c:
        r = c.post(
            "/api/payment/create-order",
            json={"dlc_codes": [], "receipt_email": "bl@example.com"},
            headers=_auth(_token(123)),
        )
        assert r.status_code == 403


def _set_block_after_expiry(vk_id=123, enabled=True):
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        u.block_after_expiry = enabled
        s.commit()


def test_renewal_blocked_outside_window(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=10, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 403
    assert "Продление станет доступно" in r.json()["detail"]

    with TestingSessionLocal() as db:
        assert db.query(PaymentOrder).count() == 0


def test_renewal_allowed_at_4_days_left(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=4, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    assert r.json()["kind"] == "subscription"


def test_renewal_allowed_after_expiry(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    _activate_subscription(days=-1, codes="")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    assert r.json()["amount_rub"] == 300


def test_renewal_only_once_per_period(player_client, monkeypatch, db):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=4, codes="")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    body = _sign({"transaction_id": "farm-order-1", "game_id": "farm", "vk_id": 123,
                  "amount_kop": 30000, "status": "success"})
    assert player_client.post("/api/payment/webhook", **body).status_code == 200

    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        assert u.subscription_until - _utcnow() > timedelta(days=29)

    r2 = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r2.status_code == 403
    assert "Продление станет доступно" in r2.json()["detail"]


def test_dlc_topup_allowed_outside_window(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=10, codes="infirmary")

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary", "brewery"], "receipt_email": "player@example.com"})
    assert r.status_code == 200
    assert r.json()["kind"] == "dlc_topup"


def test_block_after_expiry_blocks_renewal_in_window(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=4, codes="infirmary")
    _set_block_after_expiry()

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Продление подписки недоступно"


def test_block_after_expiry_blocks_dlc_topup(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=10, codes="infirmary")
    _set_block_after_expiry()

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary", "brewery"], "receipt_email": "player@example.com"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Продление подписки недоступно"


def test_block_after_expiry_blocks_new_purchase(player_client, monkeypatch):
    player_client.get("/api/me")
    _expire_trial()
    _enable_gateway(monkeypatch)
    _set_block_after_expiry()

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Продление подписки недоступно"


def test_block_after_expiry_removed_allows_renewal(player_client, monkeypatch):
    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    _activate_subscription(days=4, codes="")
    _set_block_after_expiry()
    _set_block_after_expiry(enabled=False)

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 200
