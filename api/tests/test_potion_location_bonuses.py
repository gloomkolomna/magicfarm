from tests.conftest import TestingSessionLocal, make_user_client


def _make_plant(admin_client, category, level, name, emoji="🌱"):
    r = admin_client.post("/api/admin/catalog/plants", json={
        "name": name, "emoji": emoji, "category": category, "level": level,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _make_bed_field(admin_client, min_level: int):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Грядки бонуса", "cols": 3, "rows": 2,
        "plant_category": "garden", "field_kind": "garden_beds", "min_level": min_level,
    })
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    rr = admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    assert rr.status_code == 200, rr.text
    return fid


def _make_orchard_field(admin_client, min_level: int):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Сад бонуса", "cols": 4, "rows": 3,
        "plant_category": "orchard", "field_kind": "orchard", "min_level": min_level,
    })
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/plant-beds", data={"col1": 0, "row1": 0, "col2": 1, "row2": 0})
    assert r.status_code == 201, r.text
    return fid, r.json()["id"]


def _link_plant(admin_client, fid: int, pid: int):
    r = admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    assert r.status_code == 200, r.text


def _set_user_level(vk_id: int, level: int):
    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        assert u is not None
        u.level = level
        s.commit()
    finally:
        s.close()


def _activate_bonus(c, bonus_code: str):
    from models import UserPotion
    s = TestingSessionLocal()
    try:
        s.add(UserPotion(user_id=123, potion_recipe_id=1, bonus_code=bonus_code, activated=False, used=False))
        s.commit()
    finally:
        s.close()
    potion_id = c.get("/api/potions").json()[0]["id"]
    r = c.post(f"/api/potions/{potion_id}/activate")
    assert r.status_code == 200, r.text
    return r.json()


def test_garden_bed_location_locked_without_bonus(admin_client):
    fid = _make_bed_field(admin_client, min_level=12)
    pid = _make_plant(admin_client, "garden", 3, "Грядковый корешок-3")
    _link_plant(admin_client, fid, pid)
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_user_level(123, 6)
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": pid, "qty": 1})
        assert r.status_code == 403
        assert "недоступна" in r.json()["detail"]


def test_unlock_garden_l3_opens_locked_bed_location(admin_client):
    fid = _make_bed_field(admin_client, min_level=12)
    pid = _make_plant(admin_client, "garden", 3, "Грядковый корешок-3")
    _link_plant(admin_client, fid, pid)
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_user_level(123, 6)
        _activate_bonus(c, "unlock_garden_l3")
        assert c.get("/api/me").json()["unlocked_plot_level"] == 3
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": pid, "qty": 1})
        assert r.status_code == 201, r.text


def test_unlock_garden_l3_does_not_open_other_location_kinds(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Поле-не-грядки", "cols": 3, "rows": 2,
        "plant_category": "garden", "min_level": 12,
    })
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    pid = _make_plant(admin_client, "garden", 3, "Корешок обычный")
    _link_plant(admin_client, fid, pid)
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _activate_bonus(c, "unlock_garden_l3")
        rr = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": pid, "qty": 1})
        assert rr.status_code == 403


def test_orchard_location_locked_without_bonus(admin_client):
    fid, pb_id = _make_orchard_field(admin_client, min_level=15)
    pid = _make_plant(admin_client, "orchard", 3, "Яблоня-3")
    _link_plant(admin_client, fid, pid)
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_user_level(123, 6)
        r = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid, "qty": 1})
        assert r.status_code == 403
        assert "недоступна" in r.json()["detail"]


def test_unlock_orchard_l3_opens_locked_garden_location(admin_client):
    fid, pb_id = _make_orchard_field(admin_client, min_level=15)
    pid = _make_plant(admin_client, "orchard", 3, "Яблоня-3")
    _link_plant(admin_client, fid, pid)
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_user_level(123, 6)
        _activate_bonus(c, "unlock_orchard_l3")
        assert c.get("/api/me").json()["unlocked_garden_level"] == 3
        r = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid, "qty": 1})
        assert r.status_code == 201, r.text


def test_early_level_up_applies_level_unlock(admin_client):
    from models import LevelGate
    s = TestingSessionLocal()
    try:
        g = s.query(LevelGate).filter(LevelGate.level == 1).first()
        g.unlock_type = "Грядка 2 уровня"
        s.commit()
    finally:
        s.close()
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _activate_bonus(c, "early_level_up")
        me = c.get("/api/me").json()
        assert me["level"] == 1
        assert me["unlocked_plot_level"] == 2


def test_order_available_after_garden_bonus(admin_client):
    from tests.test_orders import _make_plant_product, _admin_generate
    pid = _make_plant(admin_client, "garden", 3, "Заказной корешок")
    prod = _make_plant_product(pid, "zakaznoy_tovar")
    fid = _make_bed_field(admin_client, min_level=12)
    _link_plant(admin_client, fid, pid)
    _admin_generate(prod, 2)

    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_user_level(123, 6)
        data = c.get("/api/orders/available").json()
        assert all(o["product_id"] != prod for o in data)

        _activate_bonus(c, "unlock_garden_l3")
        data2 = c.get("/api/orders/available").json()
        assert any(o["product_id"] == prod for o in data2)
