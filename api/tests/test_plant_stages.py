import io

from PIL import Image


def _img_bytes(w: int = 200, h: int = 200):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 80, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _plant_id(admin_client, code="jackobob"):
    for p in admin_client.get("/api/admin/catalog/plants").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"plant {code} not seeded")


# ===== Загрузка стадий (admin) =====

def test_upload_plant_image_young(admin_client, uploads_tmp):
    pid = _plant_id(admin_client)
    res = admin_client.put(
        f"/api/admin/catalog/plants/{pid}/image-young",
        files={"image": ("y.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["image_young_url"] is not None
    assert data["image_young_url"].startswith("/api/uploads/plant_")


def test_upload_plant_image_grown(admin_client, uploads_tmp):
    pid = _plant_id(admin_client)
    res = admin_client.put(
        f"/api/admin/catalog/plants/{pid}/image-grown",
        files={"image": ("g.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["image_grown_url"] is not None
    assert data["image_grown_url"].startswith("/api/uploads/plant_")


def test_upload_plant_stage_requires_admin(player_client, uploads_tmp):
    res = player_client.put(
        "/api/admin/catalog/plants/1/image-young",
        files={"image": ("y.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 403


def test_upload_plant_stage_not_found(admin_client, uploads_tmp):
    res = admin_client.put(
        "/api/admin/catalog/plants/9999/image-young",
        files={"image": ("y.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 404


# ===== Публичный эндпоинт отдаёт стадии =====

def test_public_plants_have_stage_fields(player_client):
    rows = player_client.get("/api/plants").json()
    assert len(rows) >= 1
    assert "image_young_url" in rows[0]
    assert "image_grown_url" in rows[0]


def test_public_plants_reflect_uploaded_stages(admin_client, uploads_tmp):
    pid = _plant_id(admin_client)
    admin_client.put(
        f"/api/admin/catalog/plants/{pid}/image-grown",
        files={"image": ("g.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    rows = admin_client.get("/api/plants").json()
    plant = [p for p in rows if p["id"] == pid][0]
    assert plant["image_grown_url"] is not None


# ===== Cell detail на поле отдаёт стадии =====

def _field_with_bed_and_plant(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 2, "rows": 1}).json()["id"]
    pid = _plant_id(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 0, "row": 0}], "kind": "bed"},
    )
    return fid, pid


def test_field_cell_has_plant_stage_images(admin_client, uploads_tmp):
    fid, pid = _field_with_bed_and_plant(admin_client)
    admin_client.put(
        f"/api/admin/catalog/plants/{pid}/image-young",
        files={"image": ("y.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    admin_client.put(
        f"/api/admin/catalog/plants/{pid}/image-grown",
        files={"image": ("g.png", io.BytesIO(_img_bytes()), "image/png")},
    )

    from tests.conftest import make_user_client
    with make_user_client(12345, "player") as c:
        c.post("/api/crystal-norms/mine/preset/1")
        c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
        detail = c.get(f"/api/fields/{fid}").json()

    cell = [x for x in detail["cells"] if x["col"] == 0 and x["row"] == 0][0]
    assert cell["plant_image_young"] is not None
    assert cell["plant_image_grown"] is not None
