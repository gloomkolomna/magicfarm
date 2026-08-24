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
                    status="pending", gateway_txn_id="farm-order-1")
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


def test_create_order_disabled(player_client):
    assert config.PAY_GATEWAY_ENABLED is False
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "player@example.com"})
    assert r.status_code == 503


def test_create_order_happy_path(player_client, monkeypatch):
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


def test_create_order_unknown_dlc(player_client, monkeypatch):
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["castle"], "receipt_email": "player@example.com"})
    assert r.status_code == 400


def test_create_order_requires_email(player_client, monkeypatch):
    _enable_gateway(monkeypatch)
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": []})
    assert r.status_code == 422
    r = player_client.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "not-an-email"})
    assert r.status_code == 400


def test_create_order_stores_email(player_client, monkeypatch):
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


def test_dlc_change_blocked_while_active(player_client, monkeypatch, db):
    from models import Setting

    player_client.get("/api/me")
    _enable_gateway(monkeypatch)
    db.add(Setting(key="dlc_change_immediate", value="0"))
    db.commit()
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        u.subscription_until = _utcnow() + timedelta(days=10)
        u.subscription_dlc_codes = "infirmary"
        s.commit()

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary", "brewery"], "receipt_email": "player@example.com"})
    assert r.status_code == 409

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["infirmary"], "receipt_email": "player@example.com"})
    assert r.status_code == 200


def test_dlc_change_immediate_mode(player_client, monkeypatch, db):
    from models import Setting

    player_client.get("/api/me")
    _enable_gateway(monkeypatch, txn="farm-order-imm")
    db.add(Setting(key="dlc_change_immediate", value="1"))
    db.commit()
    with TestingSessionLocal() as s:
        u = s.query(User).filter(User.vk_id == 123).first()
        u.subscription_until = _utcnow() + timedelta(days=10)
        u.subscription_dlc_codes = "infirmary"
        s.commit()

    r = player_client.post("/api/payment/create-order", json={"dlc_codes": ["brewery"], "receipt_email": "player@example.com"})
    assert r.status_code == 200


def test_expired_pending_cancelled_on_new_order(player_client, monkeypatch, db):
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
