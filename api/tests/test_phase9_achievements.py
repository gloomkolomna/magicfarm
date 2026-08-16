import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_achievement(db, code, name, condition_kind, value=1, production_code=None):
    from models import Achievement
    a = db.query(Achievement).filter(Achievement.code == code).first()
    if a is None:
        a = Achievement(code=code, name=name, condition_kind=condition_kind, condition_value=value, production_code=production_code)
        db.add(a)
        db.commit()
        db.refresh(a)
    return a


def _seed_plant_inventory(db, vk_id, plant_id, qty):
    from models import Inventory
    inv = Inventory(user_id=vk_id, plant_id=plant_id, qty=qty)
    db.add(inv)
    db.commit()


def _seed_studied_recipe(db, vk_id, plant_id, product_id):
    from models import Recipe, UserRecipe
    r = db.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == product_id).first()
    if r is None:
        r = Recipe(plant_id=plant_id, product_id=product_id, level=1)
        db.add(r)
        db.commit()
        db.refresh(r)
    ur = UserRecipe(user_id=vk_id, recipe_id=r.id, status="studied")
    db.add(ur)
    db.commit()


def _make_production(db, vk_id, kind="alchemy"):
    from models import Production, PRODUCTION_NAMES
    pr = Production(user_id=vk_id, kind=kind, name=PRODUCTION_NAMES.get(kind, kind),
                    status="installed", accumulated=0, required=500)
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr.id


def _field_with_bed(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "АчивТест", "code": "ach_test", "cols": 3, "rows": 2,
    })
    assert r.status_code == 201
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [1]})
    return fid


def _credit(client, amount):
    img = _real_img()
    r = client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])
    assert r.status_code == 201


# ── Unit tests for check_and_award ──

def test_first_plant_achievement(db):
    _seed_achievement(db, "first_plant", "Первое растение", "first_plant", 1)
    from services.achievements import check_and_award
    from models import Plot, UserAchievement
    plot = Plot(user_id=123, plant_id=1, qty=1, status="planted", required=100, cell_id=1)
    db.add(plot)
    db.commit()
    count = check_and_award(123, "first_plant", db)
    assert count == 1
    count2 = check_and_award(123, "first_plant", db)
    assert count2 == 0


def test_coins_reached_achievement(db):
    _seed_achievement(db, "coins_1000", "1000 монет", "coins_reached", 1000)
    from services.achievements import check_and_award
    from models import User
    u = db.query(User).filter(User.vk_id == 123).first()
    if u is None:
        u = User(vk_id=123, role="player", onboarding_done=True)
        db.add(u)
        db.commit()
    u.coins = 500
    db.commit()
    assert check_and_award(123, "coins_reached", db) == 0
    u.coins = 1500
    db.commit()
    assert check_and_award(123, "coins_reached", db) == 1


def test_animals_count_achievement(db):
    _seed_achievement(db, "first_animal", "Первое животное", "animals_count", 1)
    from services.achievements import check_and_award
    from models import BarnyardSlot
    slot = BarnyardSlot(user_id=123, animal_id=1, status="ready")
    db.add(slot)
    db.commit()
    assert check_and_award(123, "animals_count", db) == 1


def test_tents_count_achievement(db):
    _seed_achievement(db, "first_tent", "Первый шатёр", "tents_count", 1)
    from services.achievements import check_and_award
    from models import Tent, TentBuild
    t = Tent(field_id=1, name="Шатёр", kind="alchemy", col1=0, row1=0, col2=0, row2=0,
             build_status="slot", accumulated=0, required=500)
    db.add(t)
    db.commit()
    db.add(TentBuild(user_id=123, tent_id=t.id, build_status="built",
                     accumulated=500, required=500))
    db.commit()
    assert check_and_award(123, "tents_count", db) == 1


def test_tents_count_achievement_specific_production(db):
    _seed_achievement(db, "alchemy_tent", "Алхимический шатёр", "tents_count", 1, production_code="alchemy")
    from services.achievements import check_and_award
    from models import Tent, TentBuild
    t = Tent(field_id=1, name="Стол", kind="alchemy", col1=0, row1=0, col2=0, row2=0,
             build_status="slot", accumulated=0, required=500)
    db.add(t)
    db.commit()
    db.add(TentBuild(user_id=123, tent_id=t.id, build_status="built",
                     accumulated=500, required=500))
    db.commit()
    assert check_and_award(123, "tents_count", db) == 1


def test_tents_count_achievement_specific_production_wrong_kind(db):
    _seed_achievement(db, "alchemy_tent2", "Алхимический шатёр", "tents_count", 1, production_code="alchemy")
    from services.achievements import check_and_award
    from models import Tent, TentBuild
    t = Tent(field_id=1, name="Шатёр", kind="sewing", col1=0, row1=0, col2=0, row2=0,
             build_status="slot", accumulated=0, required=500)
    db.add(t)
    db.commit()
    db.add(TentBuild(user_id=123, tent_id=t.id, build_status="built",
                     accumulated=500, required=500))
    db.commit()
    assert check_and_award(123, "tents_count", db) == 0


def test_level_reached_achievement(db):
    _seed_achievement(db, "level_5", "Уровень 5", "level_reached", 5)
    from services.achievements import check_and_award
    from models import User
    u = db.query(User).filter(User.vk_id == 123).first()
    if u is None:
        u = User(vk_id=123, role="player", onboarding_done=True)
        db.add(u)
        db.commit()
    u.level = 3
    db.commit()
    assert check_and_award(123, "level_reached", db) == 0
    u.level = 5
    db.commit()
    assert check_and_award(123, "level_reached", db) == 1


def test_potions_count_achievement(db):
    _seed_achievement(db, "first_potion", "Первое зелье", "potions_count", 1)
    from services.achievements import check_and_award
    from models import UserPotion
    up = UserPotion(user_id=123, potion_recipe_id=1, bonus_code="skip_plant_stitch")
    db.add(up)
    db.commit()
    assert check_and_award(123, "potions_count", db) == 1


def test_pets_count_achievement(db):
    _seed_achievement(db, "first_pet", "Первый питомец", "pets_count", 1)
    from services.achievements import check_and_award
    from models import UserPet
    up = UserPet(user_id=123, pet_id=1)
    db.add(up)
    db.commit()
    assert check_and_award(123, "pets_count", db) == 1


def test_plots_count_achievement(db):
    _seed_achievement(db, "plots_5", "5 грядок", "plots_count", 5)
    from services.achievements import check_and_award
    from models import Plot
    for i in range(5):
        db.add(Plot(user_id=123, plant_id=1, qty=1, status="planted", required=100, cell_id=i + 1))
    db.commit()
    assert check_and_award(123, "plots_count", db) == 1


def test_achievement_not_duplicated(db):
    _seed_achievement(db, "dup_test", "Дубль-тест", "plots_count", 1)
    from services.achievements import check_and_award
    from models import Plot, UserAchievement
    db.add(Plot(user_id=123, plant_id=1, qty=1, status="planted", required=100, cell_id=1))
    db.commit()
    c1 = check_and_award(123, "plots_count", db)
    c2 = check_and_award(123, "plots_count", db)
    assert c1 == 1
    assert c2 == 0
    count = db.query(UserAchievement).filter(UserAchievement.user_id == 123).count()
    assert count == 1


# ── Integration tests ──

def test_plant_triggers_achievement(admin_client):
    faith = _field_with_bed(admin_client)
    from models import Achievement
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        _seed_achievement(s, "ach_plant", "Первая посадка", "first_plant", 1)
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        _credit(c, 10000)
        r = c.post(f"/api/fields/{faith}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r.status_code == 201

        achievements = c.get("/api/achievements").json()
        earned = [a for a in achievements if a["code"] == "ach_plant"]
        assert len(earned) == 1
        assert earned[0]["earned"] is True


def test_fulfill_trigger_coin_achievement(admin_client):
    from models import Achievement, OrderReq, Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        _seed_achievement(s, "ach_coin", "Монеты 100", "coins_reached", 100)
        inv = Inventory(user_id=123, product_id=1, qty=10)
        s.add(inv)
        o = OrderReq(user_id=123, product_id=1, qty=2, reward_coins=200, status="open")
        s.add(o)
        s.commit()
        s.refresh(o)
        oid = o.id
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/orders/{oid}/fulfill")
        assert r.status_code == 200

        achievements = c.get("/api/achievements").json()
        earned = [a for a in achievements if a["code"] == "ach_coin"]
        assert len(earned) == 1
        assert earned[0]["earned"] is True


def test_admin_create_achievement(admin_client):
    res = admin_client.post("/api/admin/achievements", json={
        "name": "Test Create",
        "condition_kind": "plots_count",
        "condition_value": 1,
    })
    assert res.status_code == 201, f"POST failed: {res.status_code} {res.text}"
    data = res.json()
    assert data["code"]


def test_admin_create_achievement_with_production(admin_client):
    res = admin_client.post("/api/admin/achievements", json={
        "name": "Алхимический шатёр",
        "condition_kind": "tents_count",
        "condition_value": 1,
        "production_code": "alchemy",
    })
    assert res.status_code == 201, res.text
    assert res.json()["production_code"] == "alchemy"


def test_admin_create_achievement_invalid_production(admin_client):
    res = admin_client.post("/api/admin/achievements", json={
        "name": "Bad",
        "condition_kind": "tents_count",
        "condition_value": 1,
        "production_code": "nonexistent",
    })
    assert res.status_code == 400


def test_admin_achievement_kinds(admin_client):
    r = admin_client.get("/api/admin/achievements/kinds")
    assert r.status_code == 200
    kinds = r.json()
    assert isinstance(kinds, list) and len(kinds) > 0
    ks = [k["kind"] for k in kinds]
    assert "plots_count" in ks
    assert "coins_reached" in ks
    for k in kinds:
        assert k["kind"] and k["label"]


def test_admin_achievement_kinds_requires_admin(player_client):
    r = player_client.get("/api/admin/achievements/kinds")
    assert r.status_code == 403


def test_admin_create_achievement_invalid_kind(admin_client):
    res = admin_client.post("/api/admin/achievements", json={
        "name": "Bad",
        "condition_kind": "does_not_exist",
        "condition_value": 1,
    })
    assert res.status_code == 400


def test_admin_update_achievement_invalid_kind(admin_client):
    create = admin_client.post("/api/admin/achievements", json={
        "name": "To Update",
        "condition_kind": "plots_count",
        "condition_value": 1,
    })
    assert create.status_code == 201
    ach_id = create.json()["id"]

    res = admin_client.put(f"/api/admin/achievements/{ach_id}", json={
        "name": "To Update",
        "condition_kind": "does_not_exist",
        "condition_value": 1,
    })
    assert res.status_code == 400


def test_admin_achievement_image_upload(admin_client, uploads_tmp):
    res = admin_client.post("/api/admin/achievements", json={
        "name": "First Plant",
        "condition_kind": "plots_count",
        "condition_value": 1,
    })
    assert res.status_code == 201
    ach_id = res.json()["id"]

    from PIL import Image
    img_buf = io.BytesIO()
    Image.new("RGB", (100, 100), color="red").save(img_buf, format="JPEG")
    img_buf.seek(0)

    res = admin_client.put(
        f"/api/admin/achievements/{ach_id}/image",
        files={"image": ("test.jpg", img_buf, "image/jpeg")},
    )
    assert res.status_code == 200
    assert res.json()["image_url"] is not None
    assert res.json()["image_url"].startswith("/api/uploads/")


def test_admin_achievement_image_upload_404(admin_client):
    img_buf = io.BytesIO(b"fake")
    res = admin_client.put(
        "/api/admin/achievements/99999/image",
        files={"image": ("test.jpg", img_buf, "image/jpeg")},
    )
    assert res.status_code == 404
