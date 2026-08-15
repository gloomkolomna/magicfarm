import io

from PIL import Image

import config


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(client, monkeypatch, amount):
    tmp = __import__("tempfile").mkdtemp(prefix="farm_craft_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    client.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _report(client, monkeypatch, amount, context_type, context_id):
    tmp = __import__("tempfile").mkdtemp(prefix="farm_craft_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    return client.post(
        "/api/stitches/reports",
        data={"amount": str(amount), "context_type": context_type, "context_id": str(context_id)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _product_id(client, code="poison"):
    for p in client.get("/api/farm/products").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"product {code} not seeded")


def _plant_id_of_product(client, code="poison"):
    prod_id = _product_id(client, code)
    info = client.get(f"/api/farm/products/{prod_id}/craft-info")
    assert info.status_code == 200
    return info.json()["plant_id"]


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


def _seed_studied_recipe(vk_id: int, plant_id: int, product_id: int):
    from models import Recipe, UserRecipe
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        r = s.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == product_id).first()
        if r is None:
            r = Recipe(plant_id=plant_id, product_id=product_id, level=1)
            s.add(r)
            s.commit()
            s.refresh(r)
        ur = UserRecipe(user_id=vk_id, recipe_id=r.id, status="studied")
        s.add(ur)
        s.commit()
    finally:
        s.close()


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


def _make_craft_session(client, qty=3):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(client)
    plant_id = _plant_id_of_product(client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 10)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)
    r = client.post(f"/api/farm/productions/{pr_id}/craft", json={"product_id": prod_id, "qty": qty})
    assert r.status_code == 200
    return r.json()["craft_session_id"], prod_id, plant_id


PLAYER_VK = 123


def test_list_products(player_client):
    rows = player_client.get("/api/farm/products").json()
    assert len(rows) >= 1
    assert any(r["code"] == "poison" for r in rows)


def test_list_productions_empty(player_client):
    assert player_client.get("/api/farm/productions").json() == []


def test_list_inventory_empty(player_client):
    assert player_client.get("/api/farm/inventory").json() == []


def test_craft_info_returns_stock_and_norm(player_client):
    prod_id = _product_id(player_client)
    plant_id = _plant_id_of_product(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)

    res = player_client.get(f"/api/farm/products/{prod_id}/craft-info")
    assert res.status_code == 200
    data = res.json()
    assert data["plant_id"] == plant_id
    assert data["plant_name"]
    assert data["stock_qty"] == 5
    assert data["norm_per_unit"] == 100


def test_craft_info_empty_stock(player_client):
    prod_id = _product_id(player_client)

    res = player_client.get(f"/api/farm/products/{prod_id}/craft-info")
    assert res.status_code == 200
    assert res.json()["stock_qty"] == 0


def test_craft_info_unknown_product(player_client):
    res = player_client.get("/api/farm/products/9999/craft-info")
    assert res.status_code == 404


def test_craft_produces_product(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_of_product(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": prod_id, "qty": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["craft_session_id"] > 0
    assert data["required"] == 300


def test_craft_insufficient_plants(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_of_product(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 1)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": prod_id, "qty": 3},
    )
    assert res.status_code == 400


def test_craft_recipe_not_studied(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_of_product(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 400


def test_craft_wrong_production_kind(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "sewing")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_of_product(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 400


def test_craft_product_without_plant(player_client, monkeypatch):
    from models import Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        s.add(Product(code="no_plant_prod", name="Товар без растения", emoji="📦", stars=1, production_kind="alchemy"))
        s.commit()
        prod_id = s.query(Product).filter(Product.code == "no_plant_prod").first().id
    finally:
        s.close()

    pr_id = _make_production(PLAYER_VK, "alchemy")
    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 400

    res = player_client.get(f"/api/farm/products/{prod_id}/craft-info")
    assert res.status_code == 400


def test_craft_unknown_product(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": 9999, "qty": 1},
    )
    assert res.status_code == 404


def test_craft_other_user_production(player_client, monkeypatch):
    pr_id = _make_production(999, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_of_product(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 403


def test_craft_not_found(player_client):
    prod_id = _product_id(player_client)

    res = player_client.post(
        "/api/farm/productions/9999/craft",
        json={"product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 404


def test_craft_sessions_empty(player_client):
    assert player_client.get("/api/farm/craft-sessions").json() == []


def test_craft_sessions_list_pending(player_client, monkeypatch):
    cs_id, prod_id, plant_id = _make_craft_session(player_client, qty=2)

    rows = player_client.get("/api/farm/craft-sessions").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == cs_id
    assert row["product_id"] == prod_id
    assert row["product_name"] == "Яд"
    assert row["plant_name"]
    assert row["qty"] == 2
    assert row["required"] == 200
    assert row["production_kind"] == "alchemy"
    assert row["status"] == "pending"


def test_craft_sessions_completed_not_in_pending(player_client, monkeypatch):
    cs_id, _, _ = _make_craft_session(player_client, qty=1)

    res = _report(player_client, monkeypatch, 100, "production", cs_id)
    assert res.status_code == 201

    rows = player_client.get("/api/farm/craft-sessions").json()
    assert rows == []

    rows_all = player_client.get("/api/farm/craft-sessions?status=all").json()
    assert len(rows_all) == 1
    assert rows_all[0]["status"] == "completed"


def test_craft_sessions_bad_status_filter(player_client):
    res = player_client.get("/api/farm/craft-sessions?status=wat")
    assert res.status_code == 400


def test_cancel_craft_session(player_client, monkeypatch):
    cs_id, _, _ = _make_craft_session(player_client, qty=2)

    res = player_client.delete(f"/api/farm/craft-sessions/{cs_id}")
    assert res.status_code == 200
    assert player_client.get("/api/farm/craft-sessions").json() == []


def test_cancel_craft_session_unknown(player_client):
    res = player_client.delete("/api/farm/craft-sessions/9999")
    assert res.status_code == 404


def test_cancel_craft_session_foreign(player_client, monkeypatch):
    cs_id, _, _ = _make_craft_session(player_client, qty=2)

    from tests.conftest import make_user_client
    with make_user_client(124, "player") as other:
        res = other.delete(f"/api/farm/craft-sessions/{cs_id}")
    assert res.status_code == 403


def test_cancel_craft_session_completed(player_client, monkeypatch):
    cs_id, _, _ = _make_craft_session(player_client, qty=1)
    res = _report(player_client, monkeypatch, 100, "production", cs_id)
    assert res.status_code == 201

    res = player_client.delete(f"/api/farm/craft-sessions/{cs_id}")
    assert res.status_code == 409


def test_report_below_norm_rejected(player_client, monkeypatch):
    cs_id, _, _ = _make_craft_session(player_client, qty=3)

    res = _report(player_client, monkeypatch, 299, "production", cs_id)
    assert res.status_code == 400
    assert "Недостаточно крестиков" in res.json()["detail"]

    rows = player_client.get("/api/farm/craft-sessions").json()
    assert len(rows) == 1


def test_report_unknown_session(player_client, monkeypatch):
    res = _report(player_client, monkeypatch, 500, "production", 9999)
    assert res.status_code == 404


def test_report_completed_session_rejected(player_client, monkeypatch):
    cs_id, _, _ = _make_craft_session(player_client, qty=1)
    res = _report(player_client, monkeypatch, 100, "production", cs_id)
    assert res.status_code == 201

    res = _report(player_client, monkeypatch, 150, "production", cs_id)
    assert res.status_code == 409


def test_report_full_norm_completes_and_credits(player_client, monkeypatch):
    cs_id, prod_id, plant_id = _make_craft_session(player_client, qty=3)

    res = _report(player_client, monkeypatch, 300, "production", cs_id)
    assert res.status_code == 201

    inv = player_client.get("/api/farm/inventory").json()
    products = [i for i in inv if i["item_kind"] == "product" and i["item_id"] == prod_id]
    assert len(products) == 1
    assert products[0]["qty"] == 3

    plants = [i for i in inv if i["item_kind"] == "plant" and i["item_id"] == plant_id]
    assert len(plants) == 1
    assert plants[0]["qty"] == 7

    assert player_client.get("/api/farm/craft-sessions").json() == []
