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


def _norm_row(user_id, plant_id):
    from models import UserPlantNorm
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        return s.query(UserPlantNorm).filter(
            UserPlantNorm.user_id == user_id, UserPlantNorm.plant_id == plant_id
        ).first()
    finally:
        s.close()


def _img():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def test_player_lists_own_plant_norms(admin_client):
    fid = _field_with_bed(admin_client, "Поле игрока", "myprice_a")
    with make_user_client(140, "player") as c:
        assert c.get("/api/me").status_code == 200
    with make_user_client(140, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r.status_code == 201, r.text
        assert r.json()["plot"]["required"] > 0

        d = c.get("/api/farm/plant-norms")
        assert d.status_code == 200, d.text
        items = d.json()["items"]
        assert len(items) == 1
        assert items[0]["plant_id"] == 1
        assert items[0]["norm_per_unit"] > 0
        assert items[0]["plot_count"] == 1


def test_player_sets_plant_norm_updates_cache_and_active_plots(admin_client):
    fid = _field_with_bed(admin_client, "Поле игрока 2", "myprice_b")
    with make_user_client(141, "player") as c:
        assert c.get("/api/me").status_code == 200
    with make_user_client(141, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 3})
        assert r.status_code == 201, r.text
        plot_id = r.json()["plot"]["id"]

        res = c.put("/api/farm/plant-norms/1", json={"norm_per_unit": 100})
        assert res.status_code == 200, res.text
        items = res.json()["items"]
        assert any(i["plant_id"] == 1 and i["norm_per_unit"] == 100 for i in items)

    row = _norm_row(141, 1)
    assert row is not None
    assert row.norm_per_unit == 100

    with make_user_client(141, "player") as c:
        d = c.get(f"/api/fields/{fid}").json()
    cell = next(x for x in d["cells"] if x.get("plot") and x["plot"]["id"] == plot_id)
    assert cell["plot"]["required"] == 300
    assert cell["plot"]["norm_per_unit"] == 100
    assert cell["plot"]["norm_revealed"] is True


def test_player_set_norm_used_by_future_planting(admin_client):
    fid = _field_with_bed(admin_client, "Поле игрока 3", "myprice_c")
    with make_user_client(142, "player") as c:
        assert c.get("/api/me").status_code == 200
    with make_user_client(142, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r.status_code == 201, r.text

        res = c.put("/api/farm/plant-norms/1", json={"norm_per_unit": 55})
        assert res.status_code == 200, res.text

    fid2 = _field_with_bed(admin_client, "Поле игрока 4", "myprice_d")
    with make_user_client(142, "player") as c:
        r2 = c.post(f"/api/fields/{fid2}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r2.status_code == 201, r2.text
        assert r2.json()["plot"]["required"] == 110
        assert r2.json()["plot"]["norm_per_unit"] == 55


def test_player_set_norm_grows_plot_when_accumulated_enough(admin_client):
    fid = _field_with_bed(admin_client, "Поле игрока 5", "myprice_e")
    with make_user_client(143, "player") as c:
        assert c.get("/api/me").status_code == 200
    with make_user_client(143, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r.status_code == 201, r.text
        plot_id = r.json()["plot"]["id"]
        c.post("/api/stitches/reports", data={"amount": "500"},
               files=[("photo_after", ("a.png", _img(), "image/png"))])
        r_inv = c.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 50})
        assert r_inv.status_code == 200, r_inv.text

        res = c.put("/api/farm/plant-norms/1", json={"norm_per_unit": 25})
        assert res.status_code == 200, res.text

    with make_user_client(143, "player") as c:
        d = c.get(f"/api/fields/{fid}").json()
    cell = next(x for x in d["cells"] if x.get("plot") and x["plot"]["id"] == plot_id)
    assert cell["plot"]["status"] == "grown"


def test_player_set_norm_does_not_touch_other_players(admin_client):
    fid = _field_with_bed(admin_client, "Поле игрока 6", "myprice_f")
    with make_user_client(144, "player") as c:
        assert c.get("/api/me").status_code == 200
    with make_user_client(145, "player") as c:
        assert c.get("/api/me").status_code == 200
    with make_user_client(144, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r.status_code == 201, r.text
        c.put("/api/farm/plant-norms/1", json={"norm_per_unit": 7})
        assert _norm_row(144, 1).norm_per_unit == 7

    assert _norm_row(145, 1) is None
    with make_user_client(145, "player") as c:
        r2 = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r2.status_code == 201, r2.text
        assert r2.json()["plot"]["norm_per_unit"] != 7
        assert _norm_row(145, 1).norm_per_unit != 7


def test_player_set_norm_negative_400(admin_client):
    with make_user_client(146, "player") as c:
        res = c.put("/api/farm/plant-norms/1", json={"norm_per_unit": -5})
        assert res.status_code == 400
        res0 = c.put("/api/farm/plant-norms/1", json={"norm_per_unit": 0})
        assert res0.status_code == 400


def test_player_set_norm_unknown_plant_404(admin_client):
    with make_user_client(147, "player") as c:
        res = c.put("/api/farm/plant-norms/99999", json={"norm_per_unit": 10})
        assert res.status_code == 404


def test_player_set_norm_without_assigned_price_404(admin_client):
    with make_user_client(148, "player") as c:
        res = c.put("/api/farm/plant-norms/1", json={"norm_per_unit": 10})
        assert res.status_code == 404


def test_player_plant_norms_unauthorized(client):
    r = client.get("/api/farm/plant-norms")
    assert r.status_code == 401
    r = client.put("/api/farm/plant-norms/1", json={"norm_per_unit": 10})
    assert r.status_code == 401
