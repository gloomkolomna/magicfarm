import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _field_with_bed(admin_client, name="Тестовое поле", code="test_p0"):
    r = admin_client.post("/api/admin/fields", json={
        "name": name, "code": code, "cols": 3, "rows": 2,
    })
    assert r.status_code == 201
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={
        "cells": [{"col": 1, "row": 1}], "kind": "bed",
    })
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={
        "plant_ids": [1],
    })
    return fid


def _two_bed_field(admin_client, name="Две грядки", code="test_p0_2"):
    r = admin_client.post("/api/admin/fields", json={
        "name": name, "code": code, "cols": 3, "rows": 2,
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


def _credit(client, amount):
    img = _real_img()
    r = client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])
    if r.status_code == 201 and r.json().get("status") == "accepted":
        return


def test_plant_with_qty(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 5,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["plant_id"] == 1
        plot = data["plot"]
        assert plot["qty"] == 5
        assert plot["status"] == "planted"
        assert plot["required"] > 0
        assert plot["drawn_cards_json"] is not None


def test_plant_default_qty(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1})
        assert r.status_code == 201
        assert r.json()["plot"]["qty"] == 1


def test_plant_qty_out_of_range(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 0,
        })
        assert r.status_code == 400
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 21,
        })
        assert r.status_code == 400


def test_plant_not_in_field(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 999, "qty": 1,
        })
        assert r.status_code == 400


def test_plant_cell_locked_after_first_plant(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 201
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 2, "qty": 1,
        })
        assert r.status_code == 409


def test_plant_unique_per_player(admin_client):
    fid = _two_bed_field(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 201
        r = c.post(f"/api/fields/{fid}/cells/2/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 409


def test_harvest_resets_plot_not_frees_cell(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 2,
        })
        assert r.status_code == 201
        pid = r.json()["plot"]["id"]
        req = r.json()["plot"]["required"]

        r = c.post(f"/api/farm/plots/{pid}/invest", json={"amount": req})
        assert r.status_code == 200
        assert r.json()["status"] == "grown"

        r = c.post(f"/api/fields/{fid}/cells/1/1/harvest")
        assert r.status_code == 200
        data = r.json()
        assert data["plant_id"] == 1
        plot = data["plot"]
        assert plot["status"] == "await_replant"
        assert plot["accumulated"] == 0

        r = c.post(f"/api/fields/{fid}/cells/1/1/replant", json={"qty": 2})
        assert r.status_code == 200
        assert r.json()["plot"]["status"] == "planted"
        assert r.json()["plot"]["qty"] == 2


def test_harvest_not_grown(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={
            "plant_id": 1, "qty": 1,
        })
        assert r.status_code == 201
        r = c.post(f"/api/fields/{fid}/cells/1/1/harvest")
        assert r.status_code == 400


def test_harvest_empty_cell(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/harvest")
        assert r.status_code == 404


def test_stitch_report_before_after(admin_client, uploads_tmp):
    img = _real_img()
    r = admin_client.post("/api/stitches/reports", data={"amount": "100"}, files=[
        ("photo_after", ("after.png", img, "image/png")),
        ("photo_before", ("before.png", img, "image/png")),
    ])
    assert r.status_code == 201
    data = r.json()
    assert data["photo_after_url"] is not None
    assert data["photo_before_url"] is not None


def test_stitch_report_with_context(admin_client, uploads_tmp):
    img = _real_img()
    r = admin_client.post("/api/stitches/reports", data={
        "amount": "200",
        "context_type": "plant_grow",
        "context_id": "5",
    }, files=[
        ("photo_after", ("after.png", img, "image/png")),
    ])
    assert r.status_code == 201
    data = r.json()
    assert data["context_type"] == "plant_grow"
    assert data["context_id"] == 5


def test_stitch_report_invalid_context_type(admin_client, uploads_tmp):
    img = _real_img()
    r = admin_client.post("/api/stitches/reports", data={
        "amount": "100",
        "context_type": "invalid_type",
    }, files=[
        ("photo_after", ("after.png", img, "image/png")),
    ])
    assert r.status_code == 400


def test_stitch_report_after_required(admin_client, uploads_tmp):
    img = _real_img()
    r = admin_client.post("/api/stitches/reports", data={"amount": "100"}, files=[
        ("photo_before", ("before.png", img, "image/png")),
    ])
    assert r.status_code == 422


def test_tent_build_uses_card_draw(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Поле с шатром", "code": "tent_p0", "cols": 3, "rows": 2,
    })
    assert r.status_code == 201
    fid = r.json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/tents", data={
        "name": "Шатёр зельеварения", "kind": "alchemy", "col1": "1", "row1": "1", "col2": "2", "row2": "1",
    })
    assert r.status_code == 201
    tid = r.json()["id"]
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        assert data["drawn_cards_json"] is not None
        assert data["crystal_color"] is None
        assert data["crystal_count"] is None
        assert data["required"] > 0
