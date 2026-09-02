import io

from PIL import Image

from tests.conftest import make_user_client, make_user_client_no_onboarding, TestingSessionLocal


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _report(client, amount, context_type, context_id):
    return client.post(
        "/api/stitches/reports",
        data={"amount": str(amount), "context_type": context_type, "context_id": str(context_id)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _recipe_id(client):
    rows = client.get("/api/library").json()
    assert rows, "рецепты не засеяны"
    return rows[0]["id"]


def _alchemy_template_id(admin_client):
    rows = admin_client.get("/api/admin/catalog/production-templates").json()
    for r in rows:
        if r["code"] == "alchemy":
            return r["id"]
    raise AssertionError("шаблон alchemy не найден")


def _set_processing_crystal(admin_client, value):
    pt_id = _alchemy_template_id(admin_client)
    res = admin_client.put(
        f"/api/admin/catalog/production-templates/{pt_id}",
        json={"processing_crystal": value},
    )
    assert res.status_code == 200, res.text
    assert res.json()["processing_crystal"] == value


def _make_production(vk_id: int, kind: str = "alchemy"):
    from models import Production, PRODUCTION_NAMES
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


def _product_and_plant(client, code="poison"):
    prod_id = None
    for p in client.get("/api/farm/products").json():
        if p["code"] == code:
            prod_id = p["id"]
            break
    assert prod_id is not None
    info = client.get(f"/api/farm/products/{prod_id}/craft-info").json()
    return prod_id, info["plant_id"]


def _seed_craft_prereqs(vk_id: int, plant_id: int, product_id: int):
    from models import Inventory, Recipe, UserRecipe
    s = TestingSessionLocal()
    try:
        inv = Inventory(user_id=vk_id, plant_id=plant_id, qty=10)
        s.add(inv)
        r = s.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == product_id).first()
        if r is None:
            r = Recipe(plant_id=plant_id, product_id=product_id, level=1)
            s.add(r)
            s.commit()
            s.refresh(r)
        s.add(UserRecipe(user_id=vk_id, recipe_id=r.id, status="studied"))
        s.commit()
    finally:
        s.close()


# ===== /mine: нормы уровней =====

def test_mine_returns_level_norms(player_client):
    res = player_client.get("/api/crystal-norms/mine")
    assert res.status_code == 200
    data = res.json()
    assert data["study_norms"] == {"level1": 500, "level2": 1000, "level3": 1500}
    assert data["production_norms"] == {"level1": 100, "level2": 200, "level3": 300}


def test_set_my_norms_with_levels(player_client):
    res = player_client.put("/api/crystal-norms/mine", json={
        "norms": {
            "green": {"norm": 10, "treasure": 0},
            "blue": {"norm": 20, "treasure": 0},
            "violet": {"norm": 30, "treasure": 0},
        },
        "dice_norm": 200,
        "study_norms": {"level1": 400, "level2": None, "level3": None},
        "production_norms": {"level1": 90, "level2": 180, "level3": 270},
    })
    assert res.status_code == 200
    assert res.json()["study_norms"]["level1"] == 400
    assert res.json()["production_norms"]["level2"] == 180

    res2 = player_client.get("/api/crystal-norms/mine")
    assert res2.json()["study_norms"]["level1"] == 400
    assert res2.json()["production_norms"]["level2"] == 180


def test_set_my_norms_invalid_level_value(player_client):
    res = player_client.put("/api/crystal-norms/mine", json={
        "norms": {
            "green": {"norm": 10, "treasure": 0},
            "blue": {"norm": 20, "treasure": 0},
            "violet": {"norm": 30, "treasure": 0},
        },
        "dice_norm": 200,
        "production_norms": {"level1": 0, "level2": None, "level3": None},
    })
    assert res.status_code == 400


# ===== Изучение рецептов =====

def test_study_blocked_without_personal_norm(admin_client):
    rid = _recipe_id(admin_client)
    with make_user_client_no_onboarding(310, "player") as c:
        res = c.post(f"/api/library/{rid}/study")
    assert res.status_code == 403
    assert "нормы изучения" in res.json()["detail"]


def test_study_fixes_required_and_report_checks_it(admin_client):
    rid = _recipe_id(admin_client)
    with make_user_client(311, "player") as c:
        res = c.post(f"/api/library/{rid}/study")
        assert res.status_code == 201

        from models import UserRecipe
        s = TestingSessionLocal()
        try:
            ur = s.query(UserRecipe).filter(
                UserRecipe.user_id == 311, UserRecipe.recipe_id == rid
            ).first()
            assert ur.required == 500
        finally:
            s.close()

        bad = _report(c, 499, "recipe_study", rid)
        assert bad.status_code == 400
        assert "Недостаточно крестиков" in bad.json()["detail"]

        good = _report(c, 500, "recipe_study", rid)
        assert good.status_code == 201

        rows = c.get("/api/library").json()
        row = [r for r in rows if r["id"] == rid][0]
        assert row["status"] == "studied"


# ===== Крафт =====

def test_craft_blocked_without_personal_norm(admin_client):
    pr_id = _make_production(320)
    with make_user_client_no_onboarding(320, "player") as c:
        prod_id, plant_id = _product_and_plant(c)
        _seed_craft_prereqs(320, plant_id, prod_id)
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={"product_id": prod_id, "qty": 2})
    assert res.status_code == 403
    assert "нормы производства" in res.json()["detail"]


def test_craft_formula_with_processing_crystal(admin_client):
    _set_processing_crystal(admin_client, 2)
    pr_id = _make_production(330)
    with make_user_client(330, "player") as c:
        prod_id, plant_id = _product_and_plant(c)
        _seed_craft_prereqs(330, plant_id, prod_id)
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={"product_id": prod_id, "qty": 3})
    assert res.status_code == 200
    assert res.json()["required"] == (2 + 1) * 100 * 3


def test_craft_formula_without_crystal(admin_client):
    _set_processing_crystal(admin_client, 0)
    pr_id = _make_production(331)
    with make_user_client(331, "player") as c:
        prod_id, plant_id = _product_and_plant(c)
        _seed_craft_prereqs(331, plant_id, prod_id)
        res = c.post(f"/api/farm/productions/{pr_id}/craft", json={"product_id": prod_id, "qty": 3})
    assert res.status_code == 200
    assert res.json()["required"] == 1 * 100 * 3


def test_craft_info_with_production_kind(admin_client):
    _set_processing_crystal(admin_client, 2)
    with make_user_client(332, "player") as c:
        prod_id, _ = _product_and_plant(c)
        res = c.get(f"/api/farm/products/{prod_id}/craft-info", params={"production_kind": "alchemy"})
    assert res.status_code == 200
    assert res.json()["norm_per_unit"] == (2 + 1) * 100


def test_craft_info_breakdown_fields_with_production_kind(admin_client):
    _set_processing_crystal(admin_client, 2)
    with make_user_client(334, "player") as c:
        prod_id, _ = _product_and_plant(c)
        res = c.get(f"/api/farm/products/{prod_id}/craft-info", params={"production_kind": "alchemy"})
    assert res.status_code == 200
    data = res.json()
    assert data["norm_per_unit"] == (2 + 1) * 100
    assert data["base_norm"] == 100
    assert data["tent_bonus"] == 2
    assert data["plant_level"] == 1


def test_craft_info_breakdown_without_production_kind(admin_client):
    _set_processing_crystal(admin_client, 2)
    with make_user_client(335, "player") as c:
        prod_id, _ = _product_and_plant(c)
        res = c.get(f"/api/farm/products/{prod_id}/craft-info")
    assert res.status_code == 200
    data = res.json()
    assert data["norm_per_unit"] == 100
    assert data["base_norm"] == 100
    assert data["tent_bonus"] is None
    assert data["plant_level"] == 1


def test_craft_info_without_norm_returns_zero(admin_client):
    with make_user_client_no_onboarding(333, "player") as c:
        prod_id, _ = _product_and_plant(c)
        res = c.get(f"/api/farm/products/{prod_id}/craft-info")
    assert res.status_code == 200
    assert res.json()["norm_per_unit"] == 0


# ===== Админ: кристалл переработки =====

def test_admin_can_update_processing_crystal(admin_client):
    _set_processing_crystal(admin_client, 3)
    rows = admin_client.get("/api/admin/catalog/production-templates").json()
    alchemy = [r for r in rows if r["code"] == "alchemy"][0]
    assert alchemy["processing_crystal"] == 3


def test_update_processing_crystal_requires_admin(player_client):
    pt_id = None
    rows = player_client.get("/api/admin/catalog/production-templates")
    assert rows.status_code == 403
