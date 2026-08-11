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


def _product_id(client, code="poison"):
    for p in client.get("/api/farm/products").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"product {code} not seeded")


def _plant_id_from_code(client, code="khlebozlak"):
    for p in client.get("/api/plants").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"plant {code} not seeded")


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


PLAYER_VK = 123


def test_list_products(player_client):
    rows = player_client.get("/api/farm/products").json()
    assert len(rows) >= 1
    assert any(r["code"] == "poison" for r in rows)


def test_list_productions_empty(player_client):
    assert player_client.get("/api/farm/productions").json() == []


def test_list_inventory_empty(player_client):
    assert player_client.get("/api/farm/inventory").json() == []


def test_craft_produces_product(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_from_code(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"plant_id": plant_id, "product_id": prod_id, "qty": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["craft_session_id"] > 0
    assert data["required"] == 300


def test_craft_insufficient_plants(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_from_code(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 1)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"plant_id": plant_id, "product_id": prod_id, "qty": 3},
    )
    assert res.status_code == 400


def test_craft_recipe_not_studied(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_from_code(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"plant_id": plant_id, "product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 400


def test_craft_wrong_production_kind(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "sewing")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_from_code(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"plant_id": plant_id, "product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 400


def test_craft_unknown_product(player_client, monkeypatch):
    pr_id = _make_production(PLAYER_VK, "alchemy")
    plant_id = _plant_id_from_code(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"plant_id": plant_id, "product_id": 9999, "qty": 1},
    )
    assert res.status_code == 404


def test_craft_other_user_production(player_client, monkeypatch):
    pr_id = _make_production(999, "alchemy")
    prod_id = _product_id(player_client)
    plant_id = _plant_id_from_code(player_client)
    _seed_plant_inventory(PLAYER_VK, plant_id, 5)
    _seed_studied_recipe(PLAYER_VK, plant_id, prod_id)

    res = player_client.post(
        f"/api/farm/productions/{pr_id}/craft",
        json={"plant_id": plant_id, "product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 403


def test_craft_not_found(player_client):
    prod_id = _product_id(player_client)
    plant_id = _plant_id_from_code(player_client)

    res = player_client.post(
        "/api/farm/productions/9999/craft",
        json={"plant_id": plant_id, "product_id": prod_id, "qty": 1},
    )
    assert res.status_code == 404
