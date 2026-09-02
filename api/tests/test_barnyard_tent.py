import io

from PIL import Image

import config

from tests.conftest import make_user_client

PLAYER_VK = 123


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _report(client, monkeypatch, amount, context_type, context_id):
    tmp = __import__("tempfile").mkdtemp(prefix="farm_barn_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    return client.post(
        "/api/stitches/reports",
        data={"amount": str(amount), "context_type": context_type, "context_id": str(context_id)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _sheep_id(admin_client):
    animals = admin_client.get("/api/admin/catalog/animals").json()
    return next(a["id"] for a in animals if a["code"] == "wool_sheep")


def _make_barnyard_pair(admin_client):
    animal_id = _sheep_id(admin_client)
    wool = admin_client.post("/api/admin/catalog/products", json={
        "name": "Радужная шерсть", "animal_id": animal_id, "stars": 1, "production_kind": "sewing",
    }).json()
    fabric = admin_client.post("/api/admin/catalog/products", json={
        "name": "Радужная ткань", "animal_id": animal_id, "stars": 2, "production_kind": "barnyard",
    }).json()
    return wool["id"], fabric["id"]


def _make_production(vk_id: int, kind: str = "barnyard"):
    from models import Production, PRODUCTION_NAMES
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        pr = Production(
            user_id=vk_id, kind=kind, name=PRODUCTION_NAMES.get(kind, kind),
            status="installed", accumulated=0, required=500,
        )
        s.add(pr)
        s.commit()
        s.refresh(pr)
        return pr.id
    finally:
        s.close()


def _seed_product_inventory(vk_id: int, product_id: int, qty: int):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=vk_id, product_id=product_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_studied_product_recipe(vk_id: int, source_product_id: int, product_id: int, level: int = 2):
    from models import Recipe, UserRecipe
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        r = s.query(Recipe).filter(
            Recipe.source_product_id == source_product_id,
            Recipe.product_id == product_id,
        ).first()
        if r is None:
            r = Recipe(source_product_id=source_product_id, product_id=product_id, level=level)
            s.add(r)
            s.commit()
            s.refresh(r)
        existing_ur = s.query(UserRecipe).filter(
            UserRecipe.user_id == vk_id, UserRecipe.recipe_id == r.id
        ).first()
        if existing_ur is None:
            s.add(UserRecipe(user_id=vk_id, recipe_id=r.id, status="studied"))
            s.commit()
        return r.id
    finally:
        s.close()


# ── Шаблон шатра ──

def test_barnyard_template_seeded(admin_client):
    rows = admin_client.get("/api/admin/catalog/production-templates").json()
    barn = next(t for t in rows if t["code"] == "barnyard")
    assert barn["name"] == "Шатёр скотного двора"
    assert barn["cards_to_draw"] == 2


# ── Админ: рецепты из продукции животного ──

def test_admin_create_recipe_from_animal_product(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    res = admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 2,
    })
    assert res.status_code == 201, res.text
    d = res.json()
    assert d["source_product_name"] == "Радужная шерсть"
    assert d["product_name"] == "Радужная ткань"
    assert d["plant_id"] is None


def test_admin_recipe_requires_exactly_one_source(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    res = admin_client.post("/api/admin/catalog/recipes", json={
        "product_id": fabric_id, "level": 1,
    })
    assert res.status_code == 400

    animals = admin_client.get("/api/admin/catalog/animals").json()
    animal_id = next(a["id"] for a in animals if a["code"] == "wool_sheep")
    second_product = admin_client.post("/api/admin/catalog/products", json={
        "name": "Товар 2", "animal_id": animal_id, "production_kind": "barnyard",
    }).json()["id"]

    created = admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 1,
    })
    assert created.status_code == 201

    res = admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": second_product, "level": 1,
    })
    assert res.status_code == 409


def test_admin_recipe_rejects_plant_source_as_animal_product(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    poison = next(p for p in admin_client.get("/api/admin/catalog/products").json() if p["code"] == "poison")
    res = admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": poison["id"], "product_id": fabric_id, "level": 1,
    })
    assert res.status_code == 400
    assert "продукцией животного" in res.json()["detail"]


# ── Библиотека ──

def test_library_hides_animal_product_recipe(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 2,
    })

    with make_user_client(PLAYER_VK, "player") as c:
        rows = c.get("/api/library").json()
    assert all(x["source_product_id"] != wool_id for x in rows)


def test_library_study_rejects_animal_product_recipe(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    rid = admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 2,
    }).json()["id"]

    with make_user_client(PLAYER_VK, "player") as c:
        res = c.post(f"/api/library/{rid}/study")
        assert res.status_code == 403
        assert "скотного двора" in res.json()["detail"]


# ── Крафт в шатре скотного двора ──

def test_craft_info_from_animal_product(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 2,
    })
    _seed_product_inventory(PLAYER_VK, wool_id, 4)

    with make_user_client(PLAYER_VK, "player") as c:
        res = c.get(f"/api/farm/products/{fabric_id}/craft-info")
    assert res.status_code == 200
    d = res.json()
    assert d["source_kind"] == "animal_product"
    assert d["source_product_id"] == wool_id
    assert d["source_product_name"] == "Радужная шерсть"
    assert d["stock_qty"] == 4
    assert d["norm_per_unit"] == 200
    assert d["base_norm"] == 200
    assert d["tent_bonus"] is None
    assert d["plant_level"] is None


def test_craft_in_barnyard_tent(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 2,
    })
    _seed_studied_product_recipe(PLAYER_VK, wool_id, fabric_id, level=2)
    _seed_product_inventory(PLAYER_VK, wool_id, 5)
    pr_id = _make_production(PLAYER_VK, "barnyard")

    with make_user_client(PLAYER_VK, "player") as c:
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={
            "product_id": fabric_id, "qty": 3,
        })
        assert res.status_code == 200, res.text
        d = res.json()
        assert d["required"] == 600
    assert d["source_product_name"] == "Радужная шерсть"


def test_craft_in_barnyard_insufficient_produce(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 1,
    })
    _seed_studied_product_recipe(PLAYER_VK, wool_id, fabric_id, level=1)
    _seed_product_inventory(PLAYER_VK, wool_id, 1)
    pr_id = _make_production(PLAYER_VK, "barnyard")

    with make_user_client(PLAYER_VK, "player") as c:
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={
            "product_id": fabric_id, "qty": 3,
        })
        assert res.status_code == 400
        assert "продукции животного" in res.json()["detail"]


def test_craft_in_barnyard_no_study_required(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 1,
    })
    _seed_product_inventory(PLAYER_VK, wool_id, 5)
    pr_id = _make_production(PLAYER_VK, "barnyard")

    with make_user_client(PLAYER_VK, "player") as c:
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={
            "product_id": fabric_id, "qty": 1,
        })
        assert res.status_code == 200, res.text
        assert res.json()["craft_session_id"] > 0


def test_products_craftable_barnyard_requires_source_stock(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 1,
    })

    with make_user_client(PLAYER_VK, "player") as c:
        rows = c.get("/api/farm/products").json()
        fabric = next(r for r in rows if r["id"] == fabric_id)
        assert fabric["craftable"] is False

    _seed_product_inventory(PLAYER_VK, wool_id, 3)

    with make_user_client(PLAYER_VK, "player") as c:
        rows = c.get("/api/farm/products").json()
        fabric = next(r for r in rows if r["id"] == fabric_id)
        assert fabric["craftable"] is True


def test_craft_in_wrong_tent_rejected(admin_client):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 1,
    })
    _seed_studied_product_recipe(PLAYER_VK, wool_id, fabric_id, level=1)
    _seed_product_inventory(PLAYER_VK, wool_id, 5)
    pr_id = _make_production(PLAYER_VK, "alchemy")

    with make_user_client(PLAYER_VK, "player") as c:
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={
            "product_id": fabric_id, "qty": 1,
        })
        assert res.status_code == 400
        assert "другом производстве" in res.json()["detail"]


def test_craft_report_deducts_produce_and_credits_product(admin_client, monkeypatch):
    wool_id, fabric_id = _make_barnyard_pair(admin_client)
    admin_client.post("/api/admin/catalog/recipes", json={
        "source_product_id": wool_id, "product_id": fabric_id, "level": 1,
    })
    _seed_studied_product_recipe(PLAYER_VK, wool_id, fabric_id, level=1)
    _seed_product_inventory(PLAYER_VK, wool_id, 5)
    pr_id = _make_production(PLAYER_VK, "barnyard")

    with make_user_client(PLAYER_VK, "player") as c:
        cs_id = c.post(f"/api/farm/productions/{pr_id}/craft", json={
            "product_id": fabric_id, "qty": 3,
        }).json()["craft_session_id"]

        res = _report(c, monkeypatch, 300, "production", cs_id)
        assert res.status_code == 201

        inv = c.get("/api/farm/inventory").json()
    wool = [i for i in inv if i["item_kind"] == "product" and i["item_id"] == wool_id]
    fabric = [i for i in inv if i["item_kind"] == "product" and i["item_id"] == fabric_id]
    assert wool[0]["qty"] == 2
    assert fabric[0]["qty"] == 3
