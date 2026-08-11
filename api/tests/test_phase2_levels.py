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


def test_levels_empty_when_no_variant(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/levels")
        assert r.status_code == 200
        assert r.json() == []


def test_set_route_variant(admin_client):
    with make_user_client(123, "player") as c:
        r = c.put("/api/levels/route-variant", json={"variant": 1})
        assert r.status_code == 200
        assert r.json()["route_variant"] == 1

        r = c.get("/api/levels")
        assert len(r.json()) == 3


def test_route_variant_immutable(admin_client):
    with make_user_client(123, "player") as c:
        c.put("/api/levels/route-variant", json={"variant": 1})
        r = c.put("/api/levels/route-variant", json={"variant": 2})
        assert r.status_code == 409


def test_set_route_variant_invalid(admin_client):
    with make_user_client(123, "player") as c:
        r = c.put("/api/levels/route-variant", json={"variant": 5})
        assert r.status_code == 400
        r = c.put("/api/levels/route-variant", json={"variant": 0})
        assert r.status_code == 400


def test_set_route_variant_no_gates(admin_client):
    with make_user_client(123, "player") as c:
        r = c.put("/api/levels/route-variant", json={"variant": 4})
        assert r.status_code == 400


def test_advance_level_insufficient(admin_client):
    with make_user_client(123, "player") as c:
        c.put("/api/levels/route-variant", json={"variant": 1})
        r = c.post("/api/levels/advance")
        assert r.status_code == 400


def test_advance_level_requires_plots(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        c.put("/api/levels/route-variant", json={"variant": 1})
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
    r = admin_client.get("/api/admin/levels?variant=1")
    assert r.status_code == 200
    assert len(r.json()) == 3

    r = admin_client.put("/api/admin/levels", json={
        "variant": 3, "level": 1, "coins_required": 500, "plots_required": 1,
    })
    assert r.status_code == 200
    assert r.json()["coins_required"] == 500

    r = admin_client.get("/api/admin/levels?variant=3")
    assert len(r.json()) == 1

    r = admin_client.delete("/api/admin/levels/3/1")
    assert r.status_code == 204

    r = admin_client.get("/api/admin/levels?variant=3")
    assert len(r.json()) == 0


def test_admin_levels_validation(admin_client):
    r = admin_client.put("/api/admin/levels", json={
        "variant": 5, "level": 1, "coins_required": 100, "plots_required": 1,
    })
    assert r.status_code == 400

    r = admin_client.put("/api/admin/levels", json={
        "variant": 1, "level": 17, "coins_required": 100, "plots_required": 1,
    })
    assert r.status_code == 400


def test_admin_levels_player_forbidden(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/admin/levels")
        assert r.status_code == 403
