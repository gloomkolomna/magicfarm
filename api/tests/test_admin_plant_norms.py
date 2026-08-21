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


def test_set_plant_norm_updates_cache_and_active_plots(admin_client):
    fid = _field_with_bed(admin_client, "Поле цен", "price_a")
    with make_user_client(130, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 3})
        assert r.status_code == 201, r.text

    res = admin_client.put("/api/admin/players/130/plant-norms/1", json={"norm_per_unit": 100})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["plant_id"] == 1
    assert body["norm_per_unit"] == 100
    assert len(body["plots"]) == 1
    assert body["plots"][0]["required"] == 300
    assert body["plots"][0]["norm_per_unit"] == 100

    row = _norm_row(130, 1)
    assert row is not None
    assert row.norm_per_unit == 100

    with make_user_client(130, "player") as c:
        d = c.get(f"/api/fields/{fid}").json()
    cell = next(x for x in d["cells"] if x.get("plot"))
    assert cell["plot"]["required"] == 300
    assert cell["plot"]["norm_per_unit"] == 100
    assert cell["plot"]["norm_revealed"] is True


def test_set_plant_norm_used_by_future_planting(admin_client):
    fid = _field_with_bed(admin_client, "Поле цен 2", "price_b")
    with make_user_client(131, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r.status_code == 201

    res = admin_client.put("/api/admin/players/131/plant-norms/1", json={"norm_per_unit": 55})
    assert res.status_code == 200, res.text

    fid2 = _field_with_bed(admin_client, "Поле цен 3", "price_c")
    with make_user_client(131, "player") as c:
        r2 = c.post(f"/api/fields/{fid2}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r2.status_code == 201, r2.text
        assert r2.json()["plot"]["required"] == 110
        assert r2.json()["plot"]["norm_per_unit"] == 55


def test_set_plant_norm_grows_plot_when_accumulated_enough(admin_client):
    fid = _field_with_bed(admin_client, "Поле цен 4", "price_d")
    with make_user_client(132, "player") as c:
        assert c.get("/api/me").status_code == 200
    pre = admin_client.put("/api/admin/players/132/plant-norms/1", json={"norm_per_unit": 100})
    assert pre.status_code == 200, pre.text
    with make_user_client(132, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 2})
        assert r.status_code == 201
        assert r.json()["plot"]["required"] == 200
        plot_id = r.json()["plot"]["id"]
        c.post("/api/stitches/reports", data={"amount": "500"},
               files=[("photo_after", ("a.png", _img(), "image/png"))])
        r_inv = c.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 50})
        assert r_inv.status_code == 200, r_inv.text

    res = admin_client.put("/api/admin/players/132/plant-norms/1", json={"norm_per_unit": 25})
    assert res.status_code == 200, res.text
    assert res.json()["plots"][0]["status"] == "grown"


def _img():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def test_set_plant_norm_forbidden_for_player(admin_client):
    with make_user_client(133, "player") as c:
        res = c.put("/api/admin/players/133/plant-norms/1", json={"norm_per_unit": 10})
    assert res.status_code == 403


def test_set_plant_norm_negative_400(admin_client):
    res = admin_client.put("/api/admin/players/133/plant-norms/1", json={"norm_per_unit": -5})
    assert res.status_code == 400


def test_set_plant_norm_unknown_plant_404(admin_client):
    res = admin_client.put("/api/admin/players/133/plant-norms/99999", json={"norm_per_unit": 10})
    assert res.status_code == 404


def test_player_detail_lists_plant_norms(admin_client):
    fid = _field_with_bed(admin_client, "Поле цен 5", "price_e")
    with make_user_client(134, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert r.status_code == 201

    d = admin_client.get("/api/admin/players/134").json()
    assert any(n["plant_id"] == 1 and n["norm_per_unit"] > 0 for n in d["plant_norms"])
    assert any(p["norm_per_unit"] is not None for p in d["plots"])
