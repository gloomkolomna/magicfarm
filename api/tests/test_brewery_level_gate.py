from tests.conftest import TestingSessionLocal, make_user_client


def _create_recipe(admin_client, name: str, level: str) -> int:
    r = admin_client.post("/api/admin/potion-recipes", json={
        "name": name, "level": level, "ingredient_slots": ["plant"],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_brewery_field(admin_client, recipe_ids: list[int]) -> int:
    r = admin_client.post("/api/admin/fields", json={
        "name": "Зельеварня уровня", "cols": 6, "rows": 4,
        "field_kind": "brewery",
    })
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    if recipe_ids:
        rr = admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": recipe_ids})
        assert rr.status_code == 200, rr.text
    return fid


def _brew_level(vk_id: int, level: str):
    from models import PotionRecipe, UserPotion

    s = TestingSessionLocal()
    try:
        ids = [r.id for r in s.query(PotionRecipe).filter(PotionRecipe.level == level).all()]
        assert ids, f"нет рецептов уровня {level}"
        for rid in ids:
            s.add(UserPotion(user_id=vk_id, potion_recipe_id=rid))
        s.commit()
    finally:
        s.close()


def _set_level(vk_id: int, level: int):
    from models import User

    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        assert u is not None
        u.level = level
        s.commit()
    finally:
        s.close()


def test_brewery_field_locked_until_prev_level_brewed(admin_client):
    _create_recipe(admin_client, "Зелье А", "green")
    _create_recipe(admin_client, "Зелье Б", "green")
    _create_recipe(admin_client, "Зелье В", "blue")
    blue1 = _create_recipe(admin_client, "Зелье В2", "blue")
    fid = _create_brewery_field(admin_client, [blue1])

    with make_user_client(123, "player") as c:
        r = c.get(f"/api/fields/{fid}")
        assert r.status_code == 403
        assert "простые" in r.json()["detail"]

        _brew_level(123, "green")
        r = c.get(f"/api/fields/{fid}")
        assert r.status_code == 200


def test_brewery_field_violet_needs_all_blue(admin_client):
    _create_recipe(admin_client, "Зелье Г", "blue")
    violet1 = _create_recipe(admin_client, "Зелье Д", "violet")
    fid = _create_brewery_field(admin_client, [violet1])

    with make_user_client(123, "player") as c:
        r = c.get(f"/api/fields/{fid}")
        assert r.status_code == 403
        assert "средние" in r.json()["detail"]

        _brew_level(123, "blue")
        assert c.get(f"/api/fields/{fid}").status_code == 200


def test_brewery_field_green_always_open(admin_client):
    green1 = _create_recipe(admin_client, "Зелье Е", "green")
    fid = _create_brewery_field(admin_client, [green1])

    with make_user_client(123, "player") as c:
        assert c.get(f"/api/fields/{fid}").status_code == 200


def test_fields_list_reports_locked_reason(admin_client):
    _create_recipe(admin_client, "Зелье Ж", "green")
    _create_recipe(admin_client, "Зелье З", "blue")
    blue2 = _create_recipe(admin_client, "Зелье З2", "blue")
    fid = _create_brewery_field(admin_client, [blue2])

    with make_user_client(123, "player") as c:
        items = {f["id"]: f for f in c.get("/api/fields").json()}
        assert "простые" in items[fid]["locked_reason"]


def test_player_level_does_not_open_brewery(admin_client):
    _create_recipe(admin_client, "Зелье И", "green")
    _create_recipe(admin_client, "Зелье И2", "green")
    blue1 = _create_recipe(admin_client, "Зелье К", "blue")
    fid = _create_brewery_field(admin_client, [blue1])

    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_level(123, 50)
        assert c.get(f"/api/fields/{fid}").status_code == 403


def test_admin_bypasses_brewery_lock(admin_client):
    _create_recipe(admin_client, "Зелье Л", "green")
    _create_recipe(admin_client, "Зелье Л2", "green")
    blue1 = _create_recipe(admin_client, "Зелье М", "blue")
    fid = _create_brewery_field(admin_client, [blue1])

    r = admin_client.get(f"/api/fields/{fid}")
    assert r.status_code == 200


def test_cauldron_follows_field_level_progression(admin_client):
    green1 = _create_recipe(admin_client, "Зелье Н", "green")
    blue1 = _create_recipe(admin_client, "Зелье О", "blue")
    fid = _create_brewery_field(admin_client, [green1, blue1])

    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": green1, "field_id": fid})
        assert r.status_code == 403

        _brew_level(123, "green")
        r = c.post("/api/potions/cauldrons", json={"recipe_id": green1, "field_id": fid})
        assert r.status_code == 201


def test_regular_field_not_affected_by_brewery_gate(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Поле грядок", "cols": 3, "rows": 2, "min_level": 3,
    })
    fid = r.json()["id"]
    with make_user_client(123, "player") as c:
        rr = c.get(f"/api/fields/{fid}")
        assert rr.status_code == 200
