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


def _give_coins(vk_id: int, amount: int):
    from tests.conftest import TestingSessionLocal
    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        if u:
            u.coins = (u.coins or 0) + amount
            s.commit()
    finally:
        s.close()


def _field_with_bed(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "УровниТест", "code": "lvl_test", "cols": 3, "rows": 2,
    })
    assert r.status_code == 201
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}, {"col": 2, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={
        "plant_ids": [1, 2],
    })
    return fid


def test_levels_list(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/levels")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 4
        assert data[0]["level"] == 0
        assert data[0]["coins_required"] == 0
        assert data[1]["coins_required"] == 800


def test_advance_level_insufficient(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/levels/advance")
        assert r.status_code == 400


def test_advance_level_requires_plots(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r.status_code == 201
        pid = r.json()["plot"]["id"]
        req = r.json()["plot"]["required"]
        c.post(f"/api/farm/plots/{pid}/invest", json={"amount": req})
        c.post(f"/api/fields/{fid}/cells/1/1/harvest")
        r = c.post(f"/api/fields/{fid}/cells/2/1/plant", json={"plant_id": 2, "qty": 1})
        assert r.status_code == 201
        pid2 = r.json()["plot"]["id"]
        req2 = r.json()["plot"]["required"]
        c.post(f"/api/farm/plots/{pid2}/invest", json={"amount": req2})

        r = c.post("/api/levels/advance")
        assert r.status_code == 400


def test_admin_crud_levels(admin_client):
    r = admin_client.get("/api/admin/levels")
    assert r.status_code == 200
    assert len(r.json()) == 4

    r = admin_client.put("/api/admin/levels", params={
        "level": 4, "coins_required": 500, "plots_required": 1,
        "unlock_type": "Животноводство +2",
    })
    assert r.status_code == 200
    assert r.json()["coins_required"] == 500
    assert r.json()["unlock_type"] == "Животноводство +2"

    r = admin_client.get("/api/admin/levels")
    assert len(r.json()) == 5

    r = admin_client.delete("/api/admin/levels/4")
    assert r.status_code == 204

    r = admin_client.get("/api/admin/levels")
    assert len(r.json()) == 4


def test_admin_levels_validation(admin_client):
    r = admin_client.put("/api/admin/levels", params={
        "level": -1, "coins_required": 100, "plots_required": 1,
    })
    assert r.status_code == 400

    r = admin_client.put("/api/admin/levels", params={
        "level": 0, "coins_required": 0, "plots_required": 0,
    })
    assert r.status_code == 200

    r = admin_client.put("/api/admin/levels", params={
        "level": 17, "coins_required": 100, "plots_required": 1,
    })
    assert r.status_code == 400


def test_admin_levels_invalid_unlock(admin_client):
    r = admin_client.put("/api/admin/levels", params={
        "level": 5, "coins_required": 100, "plots_required": 1,
        "unlock_type": "Непонятно что",
    })
    assert r.status_code == 400


def test_admin_upload_level_image(admin_client):
    img = _real_img()
    r = admin_client.post("/api/admin/levels/1/image", files=[
        ("image", ("level1.png", img, "image/png")),
    ])
    assert r.status_code == 200
    data = r.json()
    assert data["image_url"] is not None
    assert data["image_url"].startswith("/api/uploads/level_1_")


def test_admin_levels_player_forbidden(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/admin/levels")
        assert r.status_code == 403


def test_advance_unlocks_barnyard(admin_client):
    admin_client.put("/api/admin/levels", params={
        "level": 1, "coins_required": 100, "plots_required": 0,
        "unlock_type": "Животноводство +2",
    })
    with make_user_client(2001, "player") as c:
        c.get("/api/me")
        _give_coins(2001, 50000)
        r = c.post("/api/levels/advance")
        assert r.status_code == 200, r.text
        me = c.get("/api/me").json()
        assert me["unlocked_barnyard"] == 10


def test_advance_unlocks_pets(admin_client):
    admin_client.put("/api/admin/levels", params={
        "level": 1, "coins_required": 100, "plots_required": 0,
        "unlock_type": "Питомец-помощник +1",
    })
    with make_user_client(2002, "player") as c:
        c.get("/api/me")
        _give_coins(2002, 50000)
        r = c.post("/api/levels/advance")
        assert r.status_code == 200, r.text
        me = c.get("/api/me").json()
        assert me["unlocked_pets"] == 6


def test_advance_unlocks_garden(admin_client):
    admin_client.put("/api/admin/levels", params={
        "level": 1, "coins_required": 100, "plots_required": 0,
        "unlock_type": "Сад 1 уровня",
    })
    with make_user_client(2003, "player") as c:
        c.get("/api/me")
        _give_coins(2003, 50000)
        r = c.post("/api/levels/advance")
        assert r.status_code == 200, r.text
        me = c.get("/api/me").json()
        assert me["unlocked_garden_level"] == 1


def test_advance_unlocks_plot_level(admin_client):
    admin_client.put("/api/admin/levels", params={
        "level": 1, "coins_required": 100, "plots_required": 0,
        "unlock_type": "Грядка 2 уровня",
    })
    with make_user_client(2004, "player") as c:
        c.get("/api/me")
        _give_coins(2004, 50000)
        r = c.post("/api/levels/advance")
        assert r.status_code == 200, r.text
        me = c.get("/api/me").json()
        assert me["unlocked_plot_level"] == 2
