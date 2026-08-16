import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _field_with_bed(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "ЗаказыТест", "code": "ord_test", "cols": 3, "rows": 2,
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


def _credit(client, amount):
    img = _real_img()
    client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])


def test_admin_crud_templates(admin_client):
    r = admin_client.get("/api/admin/order-templates")
    assert r.status_code == 200
    assert r.json() == []

    r = admin_client.post("/api/admin/order-templates", json={
        "source_kind": "plant", "source_id": 1, "product_id": 1,
        "qty": 3, "reward_coins": 15, "customer": "Маг", "name": "Заказ на яд",
    })
    assert r.status_code == 201
    tid = r.json()["id"]
    assert r.json()["source_kind"] == "plant"
    assert r.json()["qty"] == 3

    r = admin_client.get("/api/admin/order-templates")
    assert len(r.json()) == 1

    r = admin_client.put(f"/api/admin/order-templates/{tid}", json={
        "source_kind": "plant", "source_id": 1, "product_id": 1,
        "qty": 5, "reward_coins": 25, "customer": "Маг", "name": "Обновлён",
    })
    assert r.status_code == 200
    assert r.json()["qty"] == 5

    r = admin_client.delete(f"/api/admin/order-templates/{tid}")
    assert r.status_code == 204

    r = admin_client.get("/api/admin/order-templates")
    assert r.json() == []


def test_template_validation(admin_client):
    r = admin_client.post("/api/admin/order-templates", json={
        "source_kind": "invalid", "source_id": 1, "product_id": 1, "qty": 1,
    })
    assert r.status_code == 400

    r = admin_client.post("/api/admin/order-templates", json={
        "source_kind": "plant", "source_id": 1, "product_id": 1, "qty": 0,
    })
    assert r.status_code == 400

    r = admin_client.post("/api/admin/order-templates", json={
        "source_kind": "plant", "source_id": 1, "product_id": 9999, "qty": 1,
    })
    assert r.status_code == 404


def test_template_player_forbidden(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/admin/order-templates")
        assert r.status_code == 403


def test_template_image_upload(admin_client, monkeypatch):
    import tempfile
    import config
    monkeypatch.setattr(config, "UPLOADS_DIR", tempfile.mkdtemp(prefix="farm_tpl_up_"))

    r = admin_client.post("/api/admin/order-templates", json={
        "source_kind": "plant", "source_id": 1, "product_id": 1,
        "qty": 2, "reward_coins": 10, "customer": "Маг",
    })
    tid = r.json()["id"]
    assert r.json()["image_url"] is None

    img = _real_img()
    r = admin_client.put(f"/api/admin/order-templates/{tid}/image", files=[
        ("image", ("a.png", img, "image/png")),
    ])
    assert r.status_code == 200
    assert r.json()["image_url"]

    listed = admin_client.get("/api/admin/order-templates").json()
    assert listed[0]["image_url"]

    with make_user_client(123, "player") as c:
        r = c.put(f"/api/admin/order-templates/{tid}/image", files=[
            ("image", ("a.png", img, "image/png")),
        ])
        assert r.status_code == 403


def test_template_image_not_found(admin_client):
    img = _real_img()
    r = admin_client.put("/api/admin/order-templates/9999/image", files=[
        ("image", ("a.png", img, "image/png")),
    ])
    assert r.status_code == 404


def test_no_auto_order_on_plant(admin_client):
    admin_client.post("/api/admin/order-templates", json={
        "source_kind": "plant", "source_id": 1, "product_id": 1,
        "qty": 2, "reward_coins": 10, "customer": "Маг",
    })
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 10000)
        orders_before = c.get("/api/orders").json()
        assert len(orders_before) == 0

        c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})

        orders_after = c.get("/api/orders").json()
        assert orders_after == []
        assert c.get("/api/orders/available").json() == []


def test_no_duplicate_order_on_replant(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 20000)
        c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert len(c.get("/api/orders").json()) == 0
        c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        assert len(c.get("/api/orders").json()) == 0


def test_fulfill_order_shows_have_need(admin_client):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 10000)
        c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        oid = c.post("/api/orders/generate", json={"product_id": 1, "qty": 3}).json()["id"]

        r = c.post(f"/api/orders/{oid}/fulfill")
        assert r.status_code == 400

        from models import Inventory
        from tests.conftest import TestingSessionLocal
        s = TestingSessionLocal()
        try:
            inv = Inventory(user_id=123, product_id=1, qty=5)
            s.add(inv)
            s.commit()
        finally:
            s.close()

        r = c.post(f"/api/orders/{oid}/fulfill")
        assert r.status_code == 200
        assert r.json()["status"] == "fulfilled"
