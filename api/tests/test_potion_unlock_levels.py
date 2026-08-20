import io

from tests.conftest import TestingSessionLocal, make_user_client


def _img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _make_plant(admin_client, category, level, name, emoji="🌱"):
    r = admin_client.post("/api/admin/catalog/plants", json={
        "name": name, "emoji": emoji, "category": category, "level": level,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _make_bed_field(admin_client, name="Поле грядок"):
    r = admin_client.post("/api/admin/fields", json={"name": name, "cols": 3, "rows": 2})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    rr = admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 1, "row": 1}], "kind": "bed"})
    assert rr.status_code == 200, rr.text
    return fid


def _make_orchard_slot(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Сад бонусов", "plant_category": "orchard", "cols": 4, "rows": 3,
    })
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/plant-beds", data={"col1": 0, "row1": 0, "col2": 1, "row2": 0})
    assert r.status_code == 201, r.text
    return fid, r.json()["id"]


def _give_potion(vk_id, bonus_code):
    from models import UserPotion
    s = TestingSessionLocal()
    try:
        up = UserPotion(user_id=vk_id, potion_recipe_id=1, bonus_code=bonus_code, activated=False, used=False)
        s.add(up)
        s.commit()
        s.refresh(up)
        return up.id
    finally:
        s.close()


def _activate(c, bonus_code):
    _give_potion(123, bonus_code)
    potion_id = c.get("/api/potions").json()[0]["id"]
    r = c.post(f"/api/potions/{potion_id}/activate")
    assert r.status_code == 200, r.text
    return r.json()


def test_me_returns_unlock_levels(admin_client):
    with make_user_client(123, "player") as c:
        me = c.get("/api/me").json()
    assert me["unlocked_plot_level"] >= 1
    assert me["unlocked_garden_level"] >= 0


def test_unlock_garden_l3_potion_opens_beds(admin_client):
    fid = _make_bed_field(admin_client)
    pid = _make_plant(admin_client, "garden_beds", 3, "Трёхуровневый корешок")
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    with make_user_client(123, "player") as c:
        res = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": pid, "qty": 2})
        assert res.status_code == 403, res.text

        _activate(c, "unlock_garden_l3")
        assert c.get("/api/me").json()["unlocked_plot_level"] == 3

        res = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": pid, "qty": 2})
        assert res.status_code == 201, res.text


def test_unlock_orchard_l3_potion_opens_garden(admin_client):
    fid, pb_id = _make_orchard_slot(admin_client)
    pid = _make_plant(admin_client, "orchard", 3, "Древо-загадка", "🌳")
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    with make_user_client(123, "player") as c:
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid, "qty": 2})
        assert res.status_code == 403, res.text

        _activate(c, "unlock_orchard_l3")
        assert c.get("/api/me").json()["unlocked_garden_level"] == 3

        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid, "qty": 2})
        assert res.status_code == 201, res.text
