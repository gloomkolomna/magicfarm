import io
import tempfile

from PIL import Image

import config

from tests.conftest import make_user_client, TestingSessionLocal


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(c, monkeypatch, amount):
    monkeypatch.setattr(config, "UPLOADS_DIR", tempfile.mkdtemp(prefix="farm_kassa_"))
    c.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _product_id(client):
    for p in client.get("/api/farm/products").json():
        if p["code"] == "poison":
            return p["id"]
    raise AssertionError("product poison not seeded")


def _open_order_id(admin_client):
    pid = _product_id(admin_client)
    res = admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1})
    assert res.status_code == 201
    return res.json()["id"]


def _remove_kassa(vk_id):
    from models import KASSA_KIND, Production
    s = TestingSessionLocal()
    try:
        for pr in s.query(Production).filter(
            Production.user_id == vk_id, Production.kind == KASSA_KIND
        ).all():
            s.delete(pr)
        s.commit()
    finally:
        s.close()


def _make_kassa_slot(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Поле", "cols": 4, "rows": 3}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Касса", "kind": "kassa", "col1": "0", "row1": "0", "col2": "1", "row2": "1"},
    )
    assert res.status_code == 201
    return fid, res.json()["id"]


def test_take_order_forbidden_without_kassa(admin_client):
    oid = _open_order_id(admin_client)
    with make_user_client(3001, "player") as c:
        c.get("/api/me")
        _remove_kassa(3001)
        res = c.post(f"/api/orders/{oid}/take")
        assert res.status_code == 403
        assert "касс" in res.json()["detail"].lower()


def test_available_orders_empty_without_kassa(admin_client):
    _open_order_id(admin_client)
    with make_user_client(3003, "player") as c:
        c.get("/api/me")
        _remove_kassa(3003)
        assert c.get("/api/orders/available").json() == []


def test_take_order_ok_with_kassa(admin_client):
    oid = _open_order_id(admin_client)
    with make_user_client(3004, "player") as c:
        res = c.post(f"/api/orders/{oid}/take")
        assert res.status_code == 200
        assert c.get("/api/orders/available").json() == []


def test_available_orders_ok_with_kassa(admin_client):
    pid = _product_id(admin_client)
    _open_order_id(admin_client)
    with make_user_client(3005, "player") as c:
        available = c.get("/api/orders/available").json()
        assert len(available) == 1
        assert available[0]["product_id"] == pid


def test_build_kassa_tent_unlocks_orders(admin_client, monkeypatch):
    fid, tid = _make_kassa_slot(admin_client)
    oid = _open_order_id(admin_client)
    with make_user_client(3010, "player") as c:
        c.get("/api/me")
        _remove_kassa(3010)
        assert c.post(f"/api/orders/{oid}/take").status_code == 403

        started = c.post(f"/api/fields/{fid}/tents/{tid}/start-build").json()
        _credit(c, monkeypatch, started["required"])
        built = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": started["required"]}).json()
        assert built["build_status"] == "built"

        assert c.post(f"/api/orders/{oid}/take").status_code == 200


def test_create_second_kassa_conflict(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Поле2", "cols": 4, "rows": 3}).json()["id"]
    r1 = admin_client.post(f"/api/admin/fields/{fid}/tents", data={"name": "Касса 1", "kind": "kassa", "col1": "0", "row1": "0", "col2": "1", "row2": "1"})
    assert r1.status_code == 201
    r2 = admin_client.post(f"/api/admin/fields/{fid}/tents", data={"name": "Касса 2", "kind": "kassa", "col1": "2", "row1": "0", "col2": "3", "row2": "1"})
    assert r2.status_code == 409


def test_mark_existing_tent_as_kassa(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Поле3", "cols": 4, "rows": 3}).json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/tents", data={"name": "Стол", "kind": "alchemy", "col1": "0", "row1": "0", "col2": "1", "row2": "1"})
    tid = r.json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}/tents/{tid}", json={"kind": "kassa"})
    assert res.status_code == 200
    assert res.json()["kind"] == "kassa"

    r2 = admin_client.post(f"/api/admin/fields/{fid}/tents", data={"name": "Касса 2", "kind": "kassa", "col1": "2", "row1": "0", "col2": "3", "row2": "1"})
    assert r2.status_code == 409


def test_mark_existing_tent_as_kassa_second_conflict(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Поле4", "cols": 4, "rows": 3}).json()["id"]
    admin_client.post(f"/api/admin/fields/{fid}/tents", data={"name": "Касса", "kind": "kassa", "col1": "0", "row1": "0", "col2": "1", "row2": "1"})
    r = admin_client.post(f"/api/admin/fields/{fid}/tents", data={"name": "Стол", "kind": "alchemy", "col1": "2", "row1": "0", "col2": "3", "row2": "1"})
    tid = r.json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}/tents/{tid}", json={"kind": "kassa"})
    assert res.status_code == 409


def test_tent_update_requires_admin(client):
    assert client.put("/api/admin/fields/1/tents/1", json={"kind": "kassa"}).status_code == 401
