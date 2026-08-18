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


def test_no_auto_order_on_plant(admin_client):
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
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": 1, "qty": 3}).json()["id"]
    with make_user_client(123, "player") as c:
        _credit(c, 10000)
        c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1, "qty": 1})
        c.post(f"/api/orders/{oid}/take")

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
