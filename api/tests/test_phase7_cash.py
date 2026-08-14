import io

from tests.conftest import make_user_client


def _seed_product_inventory(vk_id: int, product_id: int, qty: int):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        inv = Inventory(user_id=vk_id, product_id=product_id, qty=qty)
        s.add(inv)
        s.commit()
    finally:
        s.close()


def _seed_plant_inventory(vk_id: int, plant_id: int, qty: int):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        inv = Inventory(user_id=vk_id, plant_id=plant_id, qty=qty)
        s.add(inv)
        s.commit()
    finally:
        s.close()


def test_sell_product_surplus(admin_client):
    _seed_product_inventory(123, 1, 10)
    with make_user_client(123, "player") as c:
        r = c.post("/api/farm/sell-surplus", json={
            "item_kind": "product", "item_id": 1, "qty": 3,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["coins_earned"] == 67  # (5 + 40) * 3 * 0.5 = 67
        assert data["qty_sold"] == 3

        inv = c.get("/api/farm/inventory?item_kind=product").json()
        assert inv[0]["qty"] == 7


def test_sell_plant_surplus(admin_client):
    _seed_plant_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/farm/sell-surplus", json={
            "item_kind": "plant", "item_id": 1, "qty": 2,
        })
        assert r.status_code == 200
        assert r.json()["qty_sold"] == 2

        inv = c.get("/api/farm/inventory?item_kind=plant").json()
        assert inv[0]["qty"] == 3


def test_sell_all_removes_inventory(admin_client):
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/farm/sell-surplus", json={
            "item_kind": "product", "item_id": 1, "qty": 5,
        })
        assert r.status_code == 200

        inv = c.get("/api/farm/inventory?item_kind=product").json()
        assert inv == []


def test_sell_insufficient(admin_client):
    _seed_product_inventory(123, 1, 2)
    with make_user_client(123, "player") as c:
        r = c.post("/api/farm/sell-surplus", json={
            "item_kind": "product", "item_id": 1, "qty": 5,
        })
        assert r.status_code == 400


def test_sell_invalid_kind(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/farm/sell-surplus", json={
            "item_kind": "animal", "item_id": 1, "qty": 1,
        })
        assert r.status_code == 400
