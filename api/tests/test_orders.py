import io

from PIL import Image

import config


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _poison_id(player_client):
    for p in player_client.get("/api/farm/products").json():
        if p["code"] == "poison":
            return p["id"]
    raise AssertionError("product poison not seeded")


def _credit(player_client, monkeypatch, amount):
    tmp = __import__("tempfile").mkdtemp(prefix="farm_ord_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    player_client.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _craft_poison(player_client, monkeypatch, cycles=2, qty=3):
    _credit(player_client, monkeypatch, cycles * 500)
    pid = _poison_id(player_client)
    _seed_product_inventory(123, pid, cycles * qty)
    return pid


def _seed_product_inventory(vk_id: int, product_id: int, qty: int):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        inv = s.query(Inventory).filter(
            Inventory.user_id == vk_id, Inventory.product_id == product_id
        ).first()
        if inv is None:
            inv = Inventory(user_id=vk_id, product_id=product_id, qty=qty)
            s.add(inv)
        else:
            inv.qty = qty
        s.commit()
    finally:
        s.close()


def _make_production(vk_id: int, kind: str = "alchemy", required: int = 500):
    from models import Production, PRODUCTION_NAMES
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        pr = Production(
            user_id=vk_id, kind=kind, name=PRODUCTION_NAMES.get(kind, kind),
            status="installed", accumulated=0, required=required,
        )
        s.add(pr)
        s.commit()
        s.refresh(pr)
        return pr.id
    finally:
        s.close()


def test_list_orders_empty(player_client):
    assert player_client.get("/api/orders").json() == []


def test_generate_order(player_client):
    pid = _poison_id(player_client)
    res = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 3, "customer": "Леди Бейлин"})
    assert res.status_code == 201
    data = res.json()
    assert data["product_id"] == pid
    assert data["qty"] == 3
    assert data["status"] == "open"
    assert data["customer"] == "Леди Бейлин"
    # reward = qty * order_reward (default 5) = 15.
    assert data["reward_coins"] == 15


def test_generate_order_without_customer(player_client):
    pid = _poison_id(player_client)
    res = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1})
    assert res.status_code == 201
    assert res.json()["customer"] is None


def test_list_customer_names(player_client):
    data = player_client.get("/api/orders/customers").json()
    assert isinstance(data, list)
    assert len(data) == 67
    assert "Леди Бейлин" in data
    assert "Профессор Кларисса" in data
    assert "Мышиный воин Осборт" in data
    assert "Ледяная Сванекильда" in data


def test_generate_order_default_qty(player_client):
    pid = _poison_id(player_client)
    res = player_client.post("/api/orders/generate", json={"product_id": pid})
    assert res.status_code == 201
    assert res.json()["qty"] == 7


def test_generate_order_invalid_qty(player_client):
    pid = _poison_id(player_client)
    res = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 0})
    assert res.status_code == 400
    res = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 99})
    assert res.status_code == 400


def test_generate_order_unknown_product(player_client):
    res = player_client.post("/api/orders/generate", json={"product_id": 9999})
    assert res.status_code == 404


def test_fulfill_order_success(player_client, monkeypatch):
    # Крафтим 3 яда (1 цикл, qty=3) → выполняем заказ на 2.
    pid = _craft_poison(player_client, monkeypatch, cycles=1, qty=3)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]

    res = player_client.post(f"/api/orders/{oid}/fulfill")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "fulfilled"
    assert data["fulfilled_at"] is not None

    me = player_client.get("/api/me").json()
    assert me["coins"] == 10  # 2 * 5

    inv = player_client.get("/api/farm/inventory").json()
    assert inv[0]["qty"] == 1  # 3 - 2


def test_fulfill_insufficient_stock(player_client):
    pid = _poison_id(player_client)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = player_client.post(f"/api/orders/{oid}/fulfill")
    assert res.status_code == 400


def test_fulfill_already_fulfilled(player_client, monkeypatch):
    pid = _craft_poison(player_client, monkeypatch, cycles=1, qty=5)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    assert player_client.post(f"/api/orders/{oid}/fulfill").status_code == 200
    res = player_client.post(f"/api/orders/{oid}/fulfill")
    assert res.status_code == 409


def test_cancel_order(player_client):
    pid = _poison_id(player_client)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = player_client.post(f"/api/orders/{oid}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_cancel_already_fulfilled(player_client, monkeypatch):
    pid = _craft_poison(player_client, monkeypatch, cycles=1, qty=5)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    player_client.post(f"/api/orders/{oid}/fulfill")
    res = player_client.post(f"/api/orders/{oid}/cancel")
    assert res.status_code == 409


def test_fulfill_other_user_order(player_client):
    pid = _poison_id(player_client)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    from tests.conftest import make_user_client
    with make_user_client(999, "player") as other:
        res = other.post(f"/api/orders/{oid}/fulfill")
        assert res.status_code == 403


def test_fulfill_not_found(player_client):
    res = player_client.post("/api/orders/9999/fulfill")
    assert res.status_code == 404


def test_list_orders_filter(player_client):
    pid = _poison_id(player_client)
    a = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    b = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    player_client.post(f"/api/orders/{a}/cancel")
    open_orders = player_client.get("/api/orders?status_filter=open").json()
    assert len(open_orders) == 1
    assert open_orders[0]["id"] == b


# ═══════════════════════════════════════════════════════════════
# Admin: создание глобального заказа
# ═══════════════════════════════════════════════════════════════


def test_admin_generate_order(admin_client):
    pid = _poison_id(admin_client)
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 3})
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["user_id"] is None
    assert data["product_id"] == pid
    assert data["qty"] == 3
    assert data["status"] == "open"
    assert data["customer"] is None
    assert data["reward_coins"] == 15


def test_admin_generate_order_default_qty(admin_client):
    pid = _poison_id(admin_client)
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": pid})
    assert res.status_code == 201, res.text
    assert res.json()["qty"] == 7


def test_admin_generate_order_with_customer(admin_client):
    pid = _poison_id(admin_client)
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2, "customer": "Леди Бейлин"})
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["customer"] == "Леди Бейлин"


def test_admin_generate_order_unknown_product(admin_client):
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": 9999})
    assert res.status_code == 404


def test_admin_generate_order_invalid_qty(admin_client):
    pid = _poison_id(admin_client)
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 0})
    assert res.status_code == 400
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 99})
    assert res.status_code == 400


def test_admin_generate_order_forbidden(player_client):
    pid = _poison_id(player_client)
    res = player_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1})
    assert res.status_code == 403


# ═══════════════════════════════════════════════════════════════
# Глобальные заказы: игрок видит, выполняет
# ═══════════════════════════════════════════════════════════════


def test_global_order_visible_to_player(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2})
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=3)
        orders = player.get("/api/orders").json()
        assert len(orders) == 1
        assert orders[0]["product_id"] == pid
        assert orders[0]["status"] == "open"


def test_global_order_fulfill(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2})
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=3)
        oid = player.get("/api/orders").json()[-1]["id"]
        res = player.post(f"/api/orders/{oid}/fulfill")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "open"
        me = player.get("/api/me").json()
        assert me["coins"] == 10


def test_global_order_fulfilled_by_both_players(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1})
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=5)
        oid = player.get("/api/orders").json()[0]["id"]
        res = player.post(f"/api/orders/{oid}/fulfill")
        assert res.status_code == 200, res.text
    with make_user_client(999, "player") as other:
        oid2 = other.get("/api/orders").json()[0]["id"]
        assert other.get("/api/orders").json()[0]["status"] == "open"
        res2 = other.post(f"/api/orders/{oid2}/fulfill")
        assert res2.status_code == 400  # нет товара на складе


def test_global_order_cancel_forbidden(admin_client):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    with make_user_client(123, "player") as player:
        res = player.post(f"/api/orders/{oid}/cancel")
        assert res.status_code == 403


def test_global_order_admin_cancel(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.post(f"/api/admin/orders/{oid}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


# ═══════════════════════════════════════════════════════════════
# Admin: редактирование заказа
# ═══════════════════════════════════════════════════════════════


def test_admin_update_order_qty(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"qty": 5})
    assert res.status_code == 200
    assert res.json()["qty"] == 5


def test_admin_update_order_customer(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"customer": "Таинственный гость"})
    assert res.status_code == 200
    assert res.json()["customer"] == "Таинственный гость"


def test_admin_update_order_status(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"status": "fulfilled"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "fulfilled"
    assert data["fulfilled_at"] is not None


def test_admin_update_order_reward(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"reward_coins": 42})
    assert res.status_code == 200
    assert res.json()["reward_coins"] == 42


def test_admin_update_order_name(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"name": "Особый заказ"})
    assert res.status_code == 200
    assert res.json()["name"] == "Особый заказ"


def test_admin_update_order_all_fields(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={
        "qty": 10, "customer": "Гость", "reward_coins": 100,
        "status": "fulfilled", "name": "Тест",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["qty"] == 10
    assert data["customer"] == "Гость"
    assert data["reward_coins"] == 100
    assert data["status"] == "fulfilled"
    assert data["name"] == "Тест"


def test_admin_update_order_not_found(admin_client):
    res = admin_client.put("/api/admin/orders/9999", json={"qty": 1})
    assert res.status_code == 404


def test_admin_update_order_invalid_status(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"status": "unknown"})
    assert res.status_code == 400


def test_admin_update_order_invalid_qty(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"qty": 99})
    assert res.status_code == 400


def test_admin_update_order_forbidden(player_client):
    pid = _poison_id(player_client)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = player_client.put(f"/api/admin/orders/{oid}", json={"qty": 5})
    assert res.status_code == 403


def test_upload_own_order_image(player_client, monkeypatch):
    import tempfile
    tmp = tempfile.mkdtemp(prefix="farm_ord_img_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    pid = _poison_id(player_client)
    oid = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = player_client.post(
        f"/api/orders/{oid}/image",
        files={"image": ("test.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["image_url"] is not None
    assert data["image_url"].startswith("/api/uploads/order_")


def test_upload_order_image_not_found(player_client, monkeypatch):
    import tempfile
    tmp = tempfile.mkdtemp(prefix="farm_ord_img_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    res = player_client.post(
        "/api/orders/99999/image",
        files={"image": ("test.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 404


def test_upload_order_image_other_user(player_client, monkeypatch):
    from tests.conftest import make_user_client
    import tempfile
    tmp = tempfile.mkdtemp(prefix="farm_ord_img_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    pid = _poison_id(player_client)
    with make_user_client(99999001, "player") as other:
        oid = other.post("/api/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = player_client.post(
        f"/api/orders/{oid}/image",
        files={"image": ("test.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 403
