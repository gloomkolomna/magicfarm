from tests.conftest import make_user_client


def _field_with_bed(admin_client, name, code, plant_ids=(1,)):
    r = admin_client.post("/api/admin/fields", json={"name": name, "code": code, "cols": 3, "rows": 2})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": list(plant_ids)})
    return fid


def _cache_rows(user_id):
    from models import UserPlantNorm
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        return s.query(UserPlantNorm).filter(UserPlantNorm.user_id == user_id).all()
    finally:
        s.close()


def test_first_plant_draws_cards_and_second_uses_cache(admin_client):
    fid1 = _field_with_bed(admin_client, "Поле А", "cache_a")
    fid2 = _field_with_bed(admin_client, "Поле Б", "cache_b")
    with make_user_client(123, "player") as c:
        r1 = c.post(f"/api/fields/{fid1}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r1.status_code == 201, r1.text
        plot1 = r1.json()["plot"]
        assert plot1["drawn_cards_json"] is not None
        unit = plot1["required"] // 2
        assert plot1["required"] == unit * 2

        r2 = c.post(f"/api/fields/{fid2}/cells/1/1/plant", json={"plant_id": 1, "qty": 3})
        assert r2.status_code == 201, r2.text
        plot2 = r2.json()["plot"]
        assert plot2["drawn_cards_json"] is None
        assert plot2["required"] == unit * 3

    rows = _cache_rows(123)
    assert len(rows) == 1
    assert rows[0].norm_per_unit == unit


def test_cache_is_per_plant(admin_client):
    fid1 = _field_with_bed(admin_client, "Поле A", "cache_p1", plant_ids=(1,))
    fid2 = _field_with_bed(admin_client, "Поле B", "cache_p2", plant_ids=(2,))
    with make_user_client(125, "player") as c:
        r1 = c.post(f"/api/fields/{fid1}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        r2 = c.post(f"/api/fields/{fid2}/cells/1/1/plant", json={"plant_id": 2, "qty": 1})
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["plot"]["drawn_cards_json"] is not None
        assert r2.json()["plot"]["drawn_cards_json"] is not None

    rows = _cache_rows(125)
    assert len(rows) == 2
    assert {r.plant_id for r in rows} == {1, 2}


def test_cache_is_per_player(admin_client):
    fid1 = _field_with_bed(admin_client, "Поле A", "cache_u1")
    fid2 = _field_with_bed(admin_client, "Поле B", "cache_u2")
    with make_user_client(126, "player") as c1:
        r1 = c1.post(f"/api/fields/{fid1}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r1.status_code == 201
    with make_user_client(127, "player") as c2:
        r2 = c2.post(f"/api/fields/{fid2}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r2.status_code == 201
        assert r2.json()["plot"]["drawn_cards_json"] is not None

    assert len(_cache_rows(126)) == 1
    assert len(_cache_rows(127)) == 1


def test_admin_reset_norm_updates_cache(admin_client):
    fid = _field_with_bed(admin_client, "Поле сброса", "cache_reset")
    with make_user_client(128, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r.status_code == 201
        plot_id = r.json()["plot"]["id"]

    res = admin_client.post(f"/api/admin/players/128/plots/{plot_id}/reset-norm")
    assert res.status_code == 200, res.text
    new_required = res.json()["required"]
    assert new_required > 0
    assert res.json()["drawn_cards_json"] is not None

    rows = _cache_rows(128)
    assert len(rows) == 1
    assert rows[0].norm_per_unit * 2 == new_required
