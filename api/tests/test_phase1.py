import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _field_with_bed(admin_client, name="СкладТест", code="wh_test"):
    r = admin_client.post("/api/admin/fields", json={
        "name": name, "code": code, "cols": 3, "rows": 2,
    })
    assert r.status_code == 201
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={
        "plant_ids": [1],
    })
    return fid


def _credit(client, amount):
    img = _real_img()
    client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])


def test_harvest_adds_plant_to_inventory(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 3,
        })
        assert r.status_code == 201
        pid = r.json()["plot"]["id"]
        req = r.json()["plot"]["required"]

        r = c.post(f"/api/farm/plots/{pid}/invest", json={"amount": req})
        assert r.status_code == 200

        inv_before = c.get("/api/farm/inventory?item_kind=plant").json()
        assert len(inv_before) == 0

        r = c.post(f"/api/fields/{fid}/cells/1/1/harvest")
        assert r.status_code == 200

        inv_after = c.get("/api/farm/inventory?item_kind=plant").json()
        assert len(inv_after) == 1
        assert inv_after[0]["item_kind"] == "plant"
        assert inv_after[0]["qty"] == 3
        assert inv_after[0]["ingredient_type"] == "plant_garden"


def test_inventory_filter_by_kind(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 2,
        })
        pid = r.json()["plot"]["id"]
        req = r.json()["plot"]["required"]
        c.post(f"/api/farm/plots/{pid}/invest", json={"amount": req})
        c.post(f"/api/fields/{fid}/cells/1/1/harvest")

        plants = c.get("/api/farm/inventory?item_kind=plant").json()
        assert len(plants) == 1
        assert plants[0]["item_kind"] == "plant"

        products = c.get("/api/farm/inventory?item_kind=product").json()
        assert len(products) == 0

        all_items = c.get("/api/farm/inventory").json()
        assert len(all_items) == 1


def test_inventory_shows_ingredient_icon(admin_client):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        inv = Inventory(user_id=123, product_id=1, qty=5)
        s.add(inv)
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        items = c.get("/api/farm/inventory").json()
        assert len(items) == 1
        assert items[0]["item_kind"] == "product"
        assert items[0]["ingredient_type"] == "tent_alchemy"
        assert items[0]["ingredient_icon"] == "⚗️"


def test_library_list_recipes(admin_client):
    r = admin_client.get("/api/admin/catalog/products").json()
    prod_id = r[0]["id"]
    plant_id = 1

    from models import Recipe
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        if s.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == prod_id).first() is None:
            rcp = Recipe(plant_id=plant_id, product_id=prod_id, level=1)
            s.add(rcp)
            s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        recipes = c.get("/api/library").json()
        assert len(recipes) >= 1
        for r in recipes:
            assert r["status"] == "locked"


def test_library_study_recipe(admin_client):
    r = admin_client.get("/api/admin/catalog/products").json()
    prod_id = r[0]["id"]
    plant_id = 1

    from models import Recipe
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        rcp = s.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == prod_id).first()
        if rcp is None:
            rcp = Recipe(plant_id=plant_id, product_id=prod_id, level=1)
            s.add(rcp)
            s.commit()
            s.refresh(rcp)
        recipe_id = rcp.id
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/library/{recipe_id}/study")
        assert r.status_code == 201
        assert r.json()["status"] == "studying"

        recipes = c.get("/api/library").json()
        studied = [r for r in recipes if r["id"] == recipe_id]
        assert len(studied) == 1
        assert studied[0]["status"] == "studying"


def test_recipe_study_completes_on_report_accept(admin_client):
    r = admin_client.get("/api/admin/catalog/products").json()
    prod_id = r[0]["id"]
    plant_id = 1

    from models import Recipe
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        rcp = s.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == prod_id).first()
        if rcp is None:
            rcp = Recipe(plant_id=plant_id, product_id=prod_id, level=1)
            s.add(rcp)
            s.commit()
            s.refresh(rcp)
        recipe_id = rcp.id
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/library/{recipe_id}/study")
        assert r.status_code == 201

        img = _real_img()
        r = c.post("/api/stitches/reports", data={
            "amount": "500",
            "context_type": "recipe_study",
            "context_id": str(recipe_id),
        }, files=[
            ("photo_after", ("after.png", img, "image/png")),
        ])
        assert r.status_code == 201
        assert r.json()["status"] == "accepted"

        recipes = c.get("/api/library").json()
        studied = [r for r in recipes if r["id"] == recipe_id]
        assert len(studied) == 1
        assert studied[0]["status"] == "studied"


def test_craft_creates_session_and_fulfills_on_report(admin_client):
    fid = _field_with_bed(admin_client)
    prod_id = None
    plant_id = 1

    r = admin_client.get("/api/admin/catalog/products").json()
    prod_id = r[0]["id"]

    from models import Recipe, UserRecipe, Inventory, CraftSession
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        rcp = s.query(Recipe).filter(Recipe.plant_id == plant_id, Recipe.product_id == prod_id).first()
        if rcp is None:
            rcp = Recipe(plant_id=plant_id, product_id=prod_id, level=1)
            s.add(rcp)
            s.commit()
            s.refresh(rcp)
        ur = UserRecipe(user_id=123, recipe_id=rcp.id, status="studied")
        s.add(ur)
        s.commit()
    finally:
        s.close()

    def _make_prod(player_vk):
        from models import Production, PRODUCTION_NAMES
        s = TestingSessionLocal()
        try:
            pr = Production(user_id=player_vk, kind="alchemy", name=PRODUCTION_NAMES["alchemy"], status="installed", accumulated=0, required=500)
            s.add(pr)
            s.commit()
            s.refresh(pr)
            return pr.id
        finally:
            s.close()

    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": plant_id, "qty": 5})
        assert r.status_code == 201
        pid_plot = r.json()["plot"]["id"]
        req = r.json()["plot"]["required"]
        c.post(f"/api/farm/plots/{pid_plot}/invest", json={"amount": req})
        c.post(f"/api/fields/{fid}/cells/1/1/harvest")

        pr_id = _make_prod(123)
        r = c.post(f"/api/farm/productions/{pr_id}/craft", json={
            "plant_id": plant_id, "product_id": prod_id, "qty": 2,
        })
        assert r.status_code == 200
        cs_id = r.json()["craft_session_id"]
        assert r.json()["required"] == 200

        img = _real_img()
        r = c.post("/api/stitches/reports", data={
            "amount": "200",
            "context_type": "production",
            "context_id": str(cs_id),
        }, files=[
            ("photo_after", ("after.png", img, "image/png")),
        ])
        assert r.status_code == 201

        inv = c.get("/api/farm/inventory").json()
        products = [i for i in inv if i["item_kind"] == "product"]
        assert len(products) == 1
        assert products[0]["qty"] == 2

        plants = [i for i in inv if i["item_kind"] == "plant"]
        assert plants[0]["qty"] == 3
