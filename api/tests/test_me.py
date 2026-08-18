def test_me_requires_auth(client):
    res = client.get("/api/me")
    assert res.status_code == 401


def test_me_admin(admin_client):
    res = admin_client.get("/api/me")
    assert res.status_code == 200
    data = res.json()
    assert data["vk_id"] == 400977
    assert data["role"] == "admin"
    assert data["crosses_balance"] == 0
    assert data["crosses_total"] == 0
    assert data["coins"] == 0
    assert data["round"] == 1
    assert data["onboarding_done"] is True


def test_me_player(player_client):
    res = player_client.get("/api/me")
    assert res.status_code == 200
    data = res.json()
    assert data["vk_id"] == 123
    assert data["role"] == "player"
    assert data["crosses_balance"] == 0
    assert data["round"] == 1
    assert data["onboarding_done"] is True


def test_me_onboarding_false_for_new_user():
    from tests.conftest import make_user_client_no_onboarding
    with make_user_client_no_onboarding(321, "player") as c:
        data = c.get("/api/me").json()
    assert data["onboarding_done"] is False


def test_me_plots_placed_counts_beds_and_orchard(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "ПрофильСад", "plant_category": "orchard", "cols": 4, "rows": 3,
    })
    fid = r.json()["id"]
    pr = admin_client.post("/api/admin/catalog/plants", json={
        "name": "ЯблоняП", "emoji": "🍎", "category": "orchard", "level": 1,
    })
    orchard_pid = pr.json()["id"]
    pr2 = admin_client.post("/api/admin/catalog/plants", json={
        "name": "ГрядкаП", "emoji": "🥬", "category": "garden", "level": 1,
    })
    bed_pid = pr2.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [orchard_pid]})
    br = admin_client.post(f"/api/admin/fields/{fid}/plant-beds", data={
        "col1": 0, "row1": 0, "col2": 1, "row2": 0,
    })
    pb_id = br.json()["id"]

    r = admin_client.post("/api/admin/fields", json={
        "name": "ПрофильПоле", "cols": 3, "rows": 2,
    })
    bed_fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{bed_fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{bed_fid}/plants", json={"plant_ids": [bed_pid]})

    from tests.conftest import make_user_client, TestingSessionLocal
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        from models import User
        s = TestingSessionLocal()
        try:
            u = s.query(User).filter(User.vk_id == 123).first()
            u.unlocked_garden_level = 1
            s.commit()
        finally:
            s.close()

        res = c.post(f"/api/fields/{bed_fid}/cells/1/1/plant", json={"plant_id": bed_pid, "qty": 1})
        assert res.status_code == 201, res.text
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": orchard_pid, "qty": 1})
        assert res.status_code == 201, res.text

        from models import Plot
        s = TestingSessionLocal()
        try:
            s.add(Plot(user_id=123, plant_id=bed_pid, qty=1, required=0))
            s.commit()
        finally:
            s.close()

        data = c.get("/api/me").json()
        assert data["plots_placed"] == 2
