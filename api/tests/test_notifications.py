from tests.conftest import TestingSessionLocal, make_user_client
from models import User


def _add_user(vk_id):
    s = TestingSessionLocal()
    try:
        if s.query(User).filter(User.vk_id == vk_id).first() is None:
            s.add(User(vk_id=vk_id, role="player", display_name=f"Игрок{vk_id}"))
            s.commit()
    finally:
        s.close()


def _give_plant(vk_id, plant_id, qty):
    from models import Inventory
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == vk_id, Inventory.plant_id == plant_id).first()
        if row is None:
            row = Inventory(user_id=vk_id, plant_id=plant_id, qty=0)
            s.add(row)
        row.qty += qty
        s.commit()
    finally:
        s.close()


def test_notifications_require_auth(client):
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.post("/api/notifications/read").status_code == 401


def test_notifications_empty(player_client):
    assert player_client.get("/api/notifications").json() == []
    assert player_client.get("/api/notifications/unread-count").json()["count"] == 0


def test_mark_read(player_client):
    from models import Notification
    s = TestingSessionLocal()
    try:
        s.add(Notification(user_id=123, text="Тест"))
        s.commit()
    finally:
        s.close()
    assert player_client.get("/api/notifications/unread-count").json()["count"] == 1
    assert len(player_client.get("/api/notifications").json()) == 1
    assert player_client.post("/api/notifications/read").json()["ok"] is True
    assert player_client.get("/api/notifications/unread-count").json()["count"] == 0
    listed = player_client.get("/api/notifications").json()
    assert listed[0]["read"] is True


def test_trade_accept_notifies_offerer():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json={
            "to_user_id": 7002,
            "items": [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}],
        }).json()["id"]
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/trades/{oid}/accept").status_code == 200
    with make_user_client(7001, "player") as a:
        notifs = a.get("/api/notifications").json()
        assert len(notifs) == 1
        assert "принял" in notifs[0]["text"]
        assert notifs[0]["peer_vk_id"] == 7002


def test_gift_notifies_with_peer():
    _add_user(7001)
    _give_plant(123, 1, 2)
    with make_user_client(123, "player") as a:
        assert a.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 1}).status_code == 201
    with make_user_client(7001, "player") as b:
        notifs = b.get("/api/notifications").json()
        assert len(notifs) == 1
        assert "подарок" in notifs[0]["text"]
        assert notifs[0]["peer_vk_id"] == 123


def test_trade_reject_notifies_offerer():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json={
            "to_user_id": 7002,
            "items": [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}],
        }).json()["id"]
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/trades/{oid}/reject").status_code == 200
    with make_user_client(7001, "player") as a:
        notifs = a.get("/api/notifications").json()
        assert len(notifs) == 1
        assert "отклонил" in notifs[0]["text"]


def test_trade_cancel_notifies_recipient():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json={
            "to_user_id": 7002,
            "items": [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}],
        }).json()["id"]
        assert a.post(f"/api/trades/{oid}/cancel").status_code == 200
    with make_user_client(7002, "player") as b:
        notifs = b.get("/api/notifications").json()
        assert len(notifs) == 1
        assert "отменил" in notifs[0]["text"]
