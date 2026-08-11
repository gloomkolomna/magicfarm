import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(client, amount):
    img = _real_img()
    client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])


def _seed_user_with_level(vk_id: int, level: int):
    from tests.conftest import TestingSessionLocal
    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        if u is not None:
            u.level = level
            s.commit()
    finally:
        s.close()


def test_admin_create_field_with_category(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Сад", "code": "sad_test", "plant_category": "orchard", "min_level": 3,
    })
    assert r.status_code == 201
    assert r.json()["plant_category"] == "orchard"
    assert r.json()["min_level"] == 3


def test_admin_update_field_category(admin_client):
    r = admin_client.post("/api/admin/fields", json={"name": "Тест"})
    fid = r.json()["id"]
    r = admin_client.put(f"/api/admin/fields/{fid}", json={
        "plant_category": "orchard", "min_level": 5,
    })
    assert r.status_code == 200
    assert r.json()["plant_category"] == "orchard"
    assert r.json()["min_level"] == 5


def test_plant_wrong_category_rejected(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Сад", "code": "sad_2", "plant_category": "orchard",
    })
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [1]})

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 400


def test_plant_level_too_low(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Элита", "code": "elite", "min_level": 5,
    })
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [1]})

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 403


def test_plant_level_ok(admin_client):
    from models import User
    from tests.conftest import TestingSessionLocal
    r = admin_client.post("/api/admin/fields", json={
        "name": "Элита2", "code": "elite2", "min_level": 3,
    })
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [1]})

    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 123).first()
        if u is None:
            u = User(vk_id=123, role="player", onboarding_done=True, level=5)
            s.add(u)
            s.commit()
        elif u.level < 3:
            u.level = 5
            s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 201
