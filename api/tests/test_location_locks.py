from tests.conftest import TestingSessionLocal, make_user_client


def _lock(codes):
    from routes.settings import set_locked_locations

    s = TestingSessionLocal()
    try:
        set_locked_locations(s, codes)
    finally:
        s.close()


def _unlock():
    _lock([])


def _seed_user(vk_id: int, role: str = "player"):
    from models import User

    s = TestingSessionLocal()
    try:
        if s.query(User).filter(User.vk_id == vk_id).first() is None:
            s.add(User(vk_id=vk_id, role=role))
            s.commit()
    finally:
        s.close()


def _potion_recipe_id():
    from models import PotionRecipe

    s = TestingSessionLocal()
    try:
        return s.query(PotionRecipe).filter(PotionRecipe.code == "sonnoe_prorochestvo").first().id
    finally:
        s.close()


def _seed_potion(vk_id: int):
    from models import UserPotion

    s = TestingSessionLocal()
    try:
        s.add(UserPotion(user_id=vk_id, potion_recipe_id=_potion_recipe_id()))
        s.commit()
    finally:
        s.close()


def _seed_ingredient(vk_id: int):
    from models import Ingredient, UserIngredient

    s = TestingSessionLocal()
    try:
        ing = s.query(Ingredient).first()
        if ing is None:
            ing = Ingredient(code="test_herb", name="Тестовая трава")
            s.add(ing)
            s.commit()
            s.refresh(ing)
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ing.id, qty=3))
        s.commit()
    finally:
        s.close()


def _seed_potion_order():
    from models import OrderReq

    s = TestingSessionLocal()
    try:
        o = OrderReq(
            product_id=None, potion_recipe_id=_potion_recipe_id(), qty=1,
            reward_coins=100, customer="Леди Бейлин", status="open",
        )
        s.add(o)
        s.commit()
        return o.id
    finally:
        s.close()


def test_put_locked_locations_admin(admin_client, db):
    res = admin_client.put("/api/admin/settings/locked-locations", json={"codes": ["infirmary"]})
    assert res.status_code == 200
    assert res.json()["codes"] == ["infirmary"]

    res = admin_client.get("/api/settings/locked-locations")
    assert res.status_code == 200
    assert res.json()["codes"] == ["infirmary"]
    _unlock()


def test_put_locked_locations_invalid_code(admin_client):
    res = admin_client.put("/api/admin/settings/locked-locations", json={"codes": ["casino"]})
    assert res.status_code == 400


def test_put_locked_locations_forbidden_for_player(player_client):
    res = player_client.put("/api/admin/settings/locked-locations", json={"codes": ["infirmary"]})
    assert res.status_code == 403


def test_me_locked_locations(admin_client):
    _lock(["infirmary", "brewery"])
    try:
        with make_user_client(123, "player") as c:
            res = c.get("/api/me")
            assert res.status_code == 200
            assert res.json()["locked_locations"] == ["brewery", "infirmary"]

        res = admin_client.get("/api/me")
        assert res.status_code == 200
        assert res.json()["locked_locations"] == []
    finally:
        _unlock()

    with make_user_client(123, "player") as c:
        assert c.get("/api/me").json()["locked_locations"] == []


def test_infirmary_locked_for_player_but_not_admin(admin_client):
    _lock(["infirmary"])
    try:
        with make_user_client(123, "player") as c:
            assert c.get("/api/infirmary").status_code == 403
            assert c.get("/api/infirmary/1").status_code == 403
            assert c.get("/api/collection").status_code == 403
            assert c.get("/api/remedy-lab/1").status_code == 403
            assert c.get("/api/meadow/1").status_code == 403

        assert admin_client.get("/api/infirmary").status_code == 200
        assert admin_client.get("/api/collection").status_code == 200
    finally:
        _unlock()

    with make_user_client(123, "player") as c:
        assert c.get("/api/infirmary").status_code == 200


def test_brewery_locked_for_player_but_not_admin(admin_client):
    _lock(["brewery"])
    try:
        with make_user_client(123, "player") as c:
            assert c.get("/api/potions").status_code == 403
            assert c.get("/api/potions/recipes").status_code == 403

        assert admin_client.get("/api/potions").status_code == 200
        assert admin_client.get("/api/potions/recipes").status_code == 200
    finally:
        _unlock()


def test_dlc_grant_and_revoke(admin_client):
    _seed_user(123)
    _lock(["infirmary"])
    try:
        with make_user_client(123, "player") as c:
            assert c.get("/api/infirmary").status_code == 403
            assert c.get("/api/me").json()["locked_locations"] == ["infirmary"]

        res = admin_client.post("/api/admin/players/123/dlc", json={"location_code": "infirmary"})
        assert res.status_code == 201

        with make_user_client(123, "player") as c:
            assert c.get("/api/infirmary").status_code == 200
            assert c.get("/api/me").json()["locked_locations"] == []

        detail = admin_client.get("/api/admin/players/123").json()
        assert detail["dlc_locations"] == ["infirmary"]

        res = admin_client.delete("/api/admin/players/123/dlc/infirmary")
        assert res.status_code == 204

        with make_user_client(123, "player") as c:
            assert c.get("/api/infirmary").status_code == 403
            assert c.get("/api/me").json()["locked_locations"] == ["infirmary"]
    finally:
        _unlock()


def test_dlc_endpoints_validation(admin_client):
    _seed_user(123)
    res = admin_client.post("/api/admin/players/123/dlc", json={"location_code": "casino"})
    assert res.status_code == 400

    res = admin_client.post("/api/admin/players/999999/dlc", json={"location_code": "infirmary"})
    assert res.status_code == 404

    res = admin_client.post("/api/admin/players/123/dlc", json={"location_code": "infirmary"})
    assert res.status_code == 201
    res = admin_client.post("/api/admin/players/123/dlc", json={"location_code": "infirmary"})
    assert res.status_code == 409

    res = admin_client.delete("/api/admin/players/123/dlc/brewery")
    assert res.status_code == 404
    res = admin_client.delete("/api/admin/players/123/dlc/infirmary")
    assert res.status_code == 204


def test_dlc_forbidden_for_player(player_client):
    res = player_client.post("/api/admin/players/123/dlc", json={"location_code": "infirmary"})
    assert res.status_code == 403


def test_inventory_hides_potions_when_brewery_locked(player_client):
    _seed_potion(123)

    items = player_client.get("/api/farm/inventory").json()
    assert any(i["item_kind"] == "potion" for i in items)

    _lock(["brewery"])
    try:
        items = player_client.get("/api/farm/inventory").json()
        assert not any(i["item_kind"] == "potion" for i in items)

        items = player_client.get("/api/farm/inventory", params={"item_kind": "potion"}).json()
        assert items == []
    finally:
        _unlock()


def test_potion_orders_hidden_when_brewery_locked(player_client):
    order_id = _seed_potion_order()

    ids = [o["id"] for o in player_client.get("/api/orders/available").json()]
    assert order_id in ids

    _lock(["brewery"])
    try:
        ids = [o["id"] for o in player_client.get("/api/orders/available").json()]
        assert order_id not in ids

        res = player_client.post(f"/api/orders/{order_id}/take")
        assert res.status_code == 403
    finally:
        _unlock()


def test_apothecary_hidden_only_when_both_locked(player_client):
    _seed_ingredient(123)

    assert len(player_client.get("/api/apothecary").json()) > 0

    _lock(["infirmary"])
    try:
        assert len(player_client.get("/api/apothecary").json()) > 0
        _lock(["infirmary", "brewery"])
        assert player_client.get("/api/apothecary").json() == []
        _lock(["brewery"])
        assert len(player_client.get("/api/apothecary").json()) > 0
    finally:
        _unlock()
