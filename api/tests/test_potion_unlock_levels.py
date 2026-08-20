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


def test_free_pet_grants_pet_when_catalog_has_free(admin_client):
    from models import Pet
    s = TestingSessionLocal()
    try:
        if s.query(Pet).count() == 0:
            s.add(Pet(code="wolf", name="Волк"))
            s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        before = c.get("/api/pets").json()
        _activate(c, "free_pet")
        after = c.get("/api/pets").json()
    assert len(after) == len(before) + 1


def test_free_pet_empty_catalog_400_and_potion_kept(admin_client):
    from models import Pet
    s = TestingSessionLocal()
    try:
        s.query(Pet).delete(synchronize_session=False)
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        _give_potion(123, "free_pet")
        potion_id = c.get("/api/potions").json()[0]["id"]
        r = c.post(f"/api/potions/{potion_id}/activate")
        assert r.status_code == 400
        assert "Каталог питомцев пуст" in r.json()["detail"]
        pot = next(p for p in c.get("/api/potions").json() if p["id"] == potion_id)
        assert pot["activated"] is False
        assert pot["used"] is False


def test_free_pet_all_owned_raises_slot(admin_client):
    from models import Pet, User, UserPet
    s = TestingSessionLocal()
    try:
        pets = s.query(Pet).all()
        if not pets:
            pets = [Pet(code="wolf2", name="Волк 2")]
            s.add(pets[0])
            s.flush()
        for p in pets:
            s.add(UserPet(user_id=123, pet_id=p.id))
        u = s.query(User).filter(User.vk_id == 123).first()
        if u is None:
            u = User(vk_id=123, role="player", unlocked_pets=5)
            s.add(u)
        else:
            u.unlocked_pets = 5
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        before = c.get("/api/me").json()["unlocked_pets"]
        _activate(c, "free_pet")
        after = c.get("/api/me").json()["unlocked_pets"]
    assert after == before + 1


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
