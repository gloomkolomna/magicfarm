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
    # reward = (база растения ур.1 = 5 + надбавка alchemy = 40) * 3 = 135.
    assert data["reward_coins"] == 135


def test_generate_order_without_customer(player_client):
    pid = _poison_id(player_client)
    res = player_client.post("/api/orders/generate", json={"product_id": pid, "qty": 1})
    assert res.status_code == 201
    assert res.json()["customer"] is None


def test_list_customer_names(player_client):
    data = player_client.get("/api/orders/customers").json()
    assert isinstance(data, list)
    assert data == ["Леди Бейлин", "Русалка Марин", "Маг Годвин"]


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
    assert me["coins"] == 90  # (5 + 40) * 2

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
    assert data["reward_coins"] == 135


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


def test_admin_generate_order_with_phrase(admin_client):
    pid = _poison_id(admin_client)
    res = admin_client.post("/api/admin/orders/generate", json={
        "product_id": pid, "qty": 2, "customer": "Русалка Марин",
        "customer_phrase": "Мне нужны три склянки яда до заката!",
    })
    assert res.status_code == 201, res.text
    assert res.json()["customer_phrase"] == "Мне нужны три склянки яда до заката!"


def test_admin_update_order_phrase(admin_client):
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    res = admin_client.put(f"/api/admin/orders/{oid}", json={"customer_phrase": "Первая реплика"})
    assert res.status_code == 200
    assert res.json()["customer_phrase"] == "Первая реплика"

    res = admin_client.put(f"/api/admin/orders/{oid}", json={"customer_phrase": "Другая реплика"})
    assert res.json()["customer_phrase"] == "Другая реплика"

    res = admin_client.put(f"/api/admin/orders/{oid}", json={"customer_phrase": ""})
    assert res.json()["customer_phrase"] is None


def test_order_customer_phrase_and_image_visible_to_player(admin_client, uploads_tmp):
    import io as _io

    img = _img_bytes()
    cid = admin_client.get("/api/admin/customers").json()[0]["id"]
    assert admin_client.put(f"/api/admin/customers/{cid}/image", files=[
        ("image", ("a.png", _io.BytesIO(img), "image/png")),
    ]).status_code == 200
    cust_name = admin_client.get("/api/admin/customers").json()[0]["name"]

    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={
        "product_id": pid, "qty": 2, "customer": cust_name,
        "customer_phrase": "Жду заказ к полнолунию!",
    }).json()["id"]

    from tests.conftest import make_user_client
    with make_user_client(123, "player") as player:
        assert player.post(f"/api/orders/{oid}/take").status_code == 200
        mine = player.get("/api/orders").json()
        o = next(x for x in mine if x["id"] == oid)
        assert o["customer_phrase"] == "Жду заказ к полнолунию!"
        assert o["customer_image_url"]

    pid2 = pid
    oid2 = admin_client.post("/api/admin/orders/generate", json={"product_id": pid2, "qty": 1}).json()["id"]
    with make_user_client(123, "player") as player:
        assert player.post(f"/api/orders/{oid2}/take").status_code == 200
        o2 = next(x for x in player.get("/api/orders").json() if x["id"] == oid2)
        assert o2["customer_phrase"] is None
        assert o2["customer_image_url"] is None


def test_order_product_image_url_visible_to_player(admin_client):
    from models import Product
    from tests.conftest import TestingSessionLocal

    pid = _poison_id(admin_client)
    s = TestingSessionLocal()
    try:
        p = s.query(Product).filter(Product.id == pid).first()
        p.image_url = "/api/uploads/product_test.png"
        s.commit()
    finally:
        s.close()

    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]

    from tests.conftest import make_user_client
    with make_user_client(123, "player") as player:
        assert player.post(f"/api/orders/{oid}/take").status_code == 200
        mine = player.get("/api/orders").json()
        o = next(x for x in mine if x["id"] == oid)
        assert o["product_image_url"] == "/api/uploads/product_test.png"


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
# Каталог свободных заказов и взятие
# ═══════════════════════════════════════════════════════════════


def test_available_orders_empty(player_client):
    assert player_client.get("/api/orders/available").json() == []


def test_global_order_not_in_my_list_but_in_available(admin_client):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2})
    with make_user_client(123, "player") as player:
        assert player.get("/api/orders").json() == []
        available = player.get("/api/orders/available").json()
        assert len(available) == 1
        assert available[0]["product_id"] == pid
        assert available[0]["status"] == "open"


def test_take_order_success(admin_client):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as player:
        res = player.post(f"/api/orders/{oid}/take")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "open"

        mine = player.get("/api/orders").json()
        assert [o["id"] for o in mine] == [oid]
        assert player.get("/api/orders/available").json() == []


def test_take_order_already_taken(admin_client):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    with make_user_client(123, "player") as player:
        assert player.post(f"/api/orders/{oid}/take").status_code == 200
    with make_user_client(999, "player") as other:
        res = other.post(f"/api/orders/{oid}/take")
        assert res.status_code == 409
        assert other.get("/api/orders").json() == []


def test_take_order_not_open(admin_client):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    admin_client.post(f"/api/admin/orders/{oid}/cancel")
    with make_user_client(123, "player") as player:
        res = player.post(f"/api/orders/{oid}/take")
        assert res.status_code == 409


def test_take_order_not_found(player_client):
    res = player_client.post("/api/orders/9999/take")
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════
# Выполнил заказ — больше не может взять/выполнить его снова
# ═══════════════════════════════════════════════════════════════


def _return_order_to_pool(order_id: int):
    from models import OrderReq
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        o = s.query(OrderReq).filter(OrderReq.id == order_id).first()
        o.user_id = None
        o.status = "open"
        s.commit()
    finally:
        s.close()


def test_fulfill_sets_fulfilled_by(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    from models import OrderReq
    from tests.conftest import TestingSessionLocal
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=3)
        player.post(f"/api/orders/{oid}/take")
        assert player.post(f"/api/orders/{oid}/fulfill").status_code == 200
    s = TestingSessionLocal()
    try:
        o = s.query(OrderReq).filter(OrderReq.id == oid).first()
        assert o.fulfilled_by == 123
    finally:
        s.close()


def test_fulfilled_order_not_retakeable_by_same_player(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=3)
        player.post(f"/api/orders/{oid}/take")
        player.post(f"/api/orders/{oid}/fulfill")

        _return_order_to_pool(oid)
        available = player.get("/api/orders/available").json()
        assert all(a["id"] != oid for a in available)
        res = player.post(f"/api/orders/{oid}/take")
        assert res.status_code == 409
        assert res.json()["detail"] == "Вы уже выполняли этот заказ"


def test_fulfilled_order_takeable_by_other_player(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=3)
        player.post(f"/api/orders/{oid}/take")
        player.post(f"/api/orders/{oid}/fulfill")

    _return_order_to_pool(oid)
    with make_user_client(999, "player") as other:
        available = other.get("/api/orders/available").json()
        assert any(a["id"] == oid for a in available)
        res = other.post(f"/api/orders/{oid}/take")
        assert res.status_code == 200


def test_refulfill_after_reopen_forbidden(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    from models import OrderReq
    from tests.conftest import TestingSessionLocal
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=5)
        player.post(f"/api/orders/{oid}/take")
        player.post(f"/api/orders/{oid}/fulfill")

        s = TestingSessionLocal()
        try:
            o = s.query(OrderReq).filter(OrderReq.id == oid).first()
            o.status = "open"
            s.commit()
        finally:
            s.close()

        res = player.post(f"/api/orders/{oid}/fulfill")
        assert res.status_code == 409
        assert res.json()["detail"] == "Вы уже выполняли этот заказ"


def test_taken_order_fulfill(admin_client, monkeypatch):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as player:
        _craft_poison(player, monkeypatch, cycles=1, qty=3)
        assert player.post(f"/api/orders/{oid}/take").status_code == 200
        res = player.post(f"/api/orders/{oid}/fulfill")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "fulfilled"
        me = player.get("/api/me").json()
        assert me["coins"] == 90  # (5 + 40) * 2


def test_untaken_global_order_fulfill_forbidden(admin_client):
    from tests.conftest import make_user_client
    pid = _poison_id(admin_client)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1}).json()["id"]
    with make_user_client(123, "player") as player:
        res = player.post(f"/api/orders/{oid}/fulfill")
        assert res.status_code == 403


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


def test_reward_includes_tent_surcharge(player_client):
    """Лунная фасоль ур.1 (5 монет) + шатёр 30 → 35/шт; 10 шт → 350.

    Сценарий из правил: цена товара = база уровня растения + надбавка шатра.
    """
    from models import Plant, Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        plant = Plant(code="moon_bean", name="Лунная фасоль", emoji="🫘",
                      category="garden", level=1, norm_per_crystal=100)
        s.add(plant)
        s.flush()
        prod = Product(code="magic_energy", name="Волшебный энергетик", emoji="⚡",
                       plant_id=plant.id, stars=1, production_kind="sewing")
        s.add(prod)
        s.commit()
        s.refresh(prod)
        prod_id = prod.id
    finally:
        s.close()

    res = player_client.post("/api/orders/generate", json={"product_id": prod_id, "qty": 10})
    assert res.status_code == 201
    assert res.json()["reward_coins"] == 350


def test_reward_plant_level_scales(player_client):
    """Растение ур.2 (10 монет) в том же шатре (30) → 40/шт."""
    from models import Plant, Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        plant = Plant(code="gold_bean", name="Золотая фасоль", emoji="🌟",
                      category="garden", level=2, norm_per_crystal=100)
        s.add(plant)
        s.flush()
        prod = Product(code="gold_cloth", name="Золотая ткань", emoji="🧵", plant_id=plant.id,
                       stars=1, production_kind="sewing")
        s.add(prod)
        s.commit()
        s.refresh(prod)
        prod_id = prod.id
    finally:
        s.close()

    res = player_client.post("/api/orders/generate", json={"product_id": prod_id, "qty": 3})
    assert res.status_code == 201
    assert res.json()["reward_coins"] == 120  # (10 + 30) * 3


def test_reward_product_without_plant_uses_level1_base(player_client):
    """Товар без растения (продукт животного): база ур.1 (5) + надбавка производства."""
    from models import Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        prod = Product(code="rainbow_wool", name="Радужная шерсть", emoji="🧶",
                       stars=1, production_kind="workshop")
        s.add(prod)
        s.commit()
        s.refresh(prod)
        prod_id = prod.id
    finally:
        s.close()

    res = player_client.post("/api/orders/generate", json={"product_id": prod_id, "qty": 4})
    assert res.status_code == 201
    assert res.json()["reward_coins"] == 160  # (5 + 35) * 4


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


# ── Доступность заказов по уровню ──

def _make_plant(code: str, category: str = "garden", level: int = 1) -> int:
    from models import Plant
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        p = Plant(code=code, name=code, emoji="🌿", category=category, level=level, norm_per_crystal=100)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id
    finally:
        s.close()


def _make_plant_product(plant_id: int, code: str) -> int:
    from models import Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        p = Product(code=code, name=code, emoji="🎁", plant_id=plant_id, stars=1, production_kind="alchemy")
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id
    finally:
        s.close()


def _make_animal_product(code: str) -> int:
    from models import Animal, Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        animal = s.query(Animal).filter(Animal.code == "wool_sheep").first()
        p = Product(code=code, name=code, emoji="🧶", animal_id=animal.id, stars=1, production_kind="sewing")
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id
    finally:
        s.close()


def _make_field_with_plant(field_code: str, plant_id: int, min_level: int, plant_category: str | None = None) -> None:
    from models import Field, FieldPlant
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        f = Field(code=field_code, name=field_code, min_level=min_level, plant_category=plant_category)
        s.add(f)
        s.flush()
        s.add(FieldPlant(field_id=f.id, plant_id=plant_id))
        s.commit()
    finally:
        s.close()


def _set_user(vk_id: int, **kwargs) -> None:
    from models import User
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        for k, v in kwargs.items():
            setattr(u, k, v)
        s.commit()
    finally:
        s.close()


def _available_order(player_client, product_id: int) -> dict:
    data = player_client.get("/api/orders/available").json()
    return next(o for o in data if o["product_id"] == product_id)


def _admin_generate(product_id: int, qty: int) -> None:
    from tests.conftest import make_user_client
    with make_user_client(400977, "admin") as admin:
        assert admin.post("/api/admin/orders/generate", json={"product_id": product_id, "qty": qty}).status_code == 201


def test_available_order_locked_by_plant_level(player_client):
    plant = _make_plant("shtuchnyy_cvetok", category="orchard", level=2)
    prod = _make_plant_product(plant, "cvetok_tovar")
    _admin_generate(prod, 3)

    o = _available_order(player_client, prod)
    assert o["available"] is False
    assert "сады" in o["lock_reason"]
    assert player_client.post(f"/api/orders/{o['id']}/take").status_code == 403

    _set_user(123, unlocked_garden_level=2)
    o = _available_order(player_client, prod)
    assert o["available"] is True
    assert o["lock_reason"] is None
    assert player_client.post(f"/api/orders/{o['id']}/take").status_code == 200


def test_available_order_locked_by_field_min_level(player_client):
    plant = _make_plant("gornyy_travnik", category="garden", level=1)
    prod = _make_plant_product(plant, "travnik_tovar")
    _make_field_with_plant("gornaya_dolina", plant, min_level=3, plant_category="garden")
    _admin_generate(prod, 2)

    o = _available_order(player_client, prod)
    assert o["available"] is False
    assert o["lock_reason"] == "Локация откроется на 3 уровне"
    assert player_client.post(f"/api/orders/{o['id']}/take").status_code == 403

    _make_field_with_plant("ravnina", plant, min_level=0, plant_category="garden")
    o = _available_order(player_client, prod)
    assert o["available"] is True
    assert player_client.post(f"/api/orders/{o['id']}/take").status_code == 200


def test_available_order_without_fields_is_available(player_client):
    pid = _poison_id(player_client)
    _admin_generate(pid, 2)
    o = _available_order(player_client, pid)
    assert o["available"] is True
    assert o["lock_reason"] is None


def test_available_order_animal_product_is_available(player_client):
    prod = _make_animal_product("sherstyanye_noski")
    _admin_generate(prod, 1)
    o = _available_order(player_client, prod)
    assert o["available"] is True
    assert o["lock_reason"] is None
