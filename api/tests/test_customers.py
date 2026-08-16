import io

from PIL import Image

from tests.conftest import make_user_client


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def test_list_customers_seeded(admin_client):
    data = admin_client.get("/api/admin/customers").json()
    names = [c["name"] for c in data]
    assert names == ["Леди Бейлин", "Русалка Марин", "Маг Годвин"]
    assert all(c["image_url"] is None for c in data)


def test_list_customers_player_forbidden(player_client):
    assert player_client.get("/api/admin/customers").status_code == 403


def test_create_customer(admin_client):
    res = admin_client.post("/api/admin/customers", json={"name": "Тролль Гослин"})
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == "Тролль Гослин"
    assert data["image_url"] is None

    names = [c["name"] for c in admin_client.get("/api/admin/customers").json()]
    assert "Тролль Гослин" in names


def test_create_customer_duplicate(admin_client):
    assert admin_client.post("/api/admin/customers", json={"name": "Леди Бейлин"}).status_code == 409


def test_create_customer_empty_name(admin_client):
    assert admin_client.post("/api/admin/customers", json={"name": "   "}).status_code == 400


def test_rename_customer(admin_client):
    cid = admin_client.post("/api/admin/customers", json={"name": "Старец"}).json()["id"]
    res = admin_client.put(f"/api/admin/customers/{cid}", json={"name": "Старец Эдрик"})
    assert res.status_code == 200
    assert res.json()["name"] == "Старец Эдрик"


def test_rename_customer_to_existing_name(admin_client):
    cid = admin_client.post("/api/admin/customers", json={"name": "Старец"}).json()["id"]
    res = admin_client.put(f"/api/admin/customers/{cid}", json={"name": "Русалка Марин"})
    assert res.status_code == 409


def test_rename_customer_not_found(admin_client):
    assert admin_client.put("/api/admin/customers/9999", json={"name": "Никто"}).status_code == 404


def test_delete_customer(admin_client):
    cid = admin_client.post("/api/admin/customers", json={"name": "Временно"}).json()["id"]
    assert admin_client.delete(f"/api/admin/customers/{cid}").status_code == 204
    assert admin_client.delete(f"/api/admin/customers/{cid}").status_code == 404
    names = [c["name"] for c in admin_client.get("/api/admin/customers").json()]
    assert "Временно" not in names


def test_customer_image_upload(admin_client, uploads_tmp):
    cid = admin_client.get("/api/admin/customers").json()[0]["id"]
    res = admin_client.put(f"/api/admin/customers/{cid}/image", files=[
        ("image", ("a.png", io.BytesIO(_img_bytes()), "image/png")),
    ])
    assert res.status_code == 200, res.text
    assert res.json()["image_url"]

    listed = admin_client.get("/api/admin/customers").json()
    assert next(c for c in listed if c["id"] == cid)["image_url"]


def test_customer_image_upload_not_found(admin_client, uploads_tmp):
    res = admin_client.put("/api/admin/customers/9999/image", files=[
        ("image", ("a.png", io.BytesIO(_img_bytes()), "image/png")),
    ])
    assert res.status_code == 404


def test_customer_image_upload_player_forbidden(player_client, uploads_tmp):
    with make_user_client(123, "player") as c:
        res = c.put("/api/admin/customers/1/image", files=[
            ("image", ("a.png", io.BytesIO(_img_bytes()), "image/png")),
        ])
        assert res.status_code == 403


def test_customer_names_reflect_edits(admin_client):
    assert admin_client.post("/api/admin/customers", json={"name": "Новый NPC"}).status_code == 201
    with make_user_client(123, "player") as c:
        names = c.get("/api/orders/customers").json()
        assert "Новый NPC" in names


def _orders_data(admin_client):
    return {c["name"]: c["open_orders_count"] for c in admin_client.get("/api/admin/customers").json()}


def test_open_orders_count(admin_client):
    pid = admin_client.get("/api/farm/products").json()[0]["id"]
    for _ in range(3):
        admin_client.post("/api/admin/orders/generate", json={"product_id": pid, "qty": 1, "customer": "Маг Годвин"})

    counts = _orders_data(admin_client)
    assert counts["Маг Годвин"] == 3
    assert counts["Леди Бейлин"] == 0

    oid = admin_client.get("/api/admin/orders").json()[0]["id"]
    admin_client.post(f"/api/admin/orders/{oid}/cancel")
    assert _orders_data(admin_client)["Маг Годвин"] == 2


def test_customer_max_orders_setting_default(admin_client):
    res = admin_client.get("/api/settings/customer_max_orders")
    assert res.status_code == 200
    assert res.json()["value"] == "3"


def test_customer_max_orders_setting_update(admin_client):
    res = admin_client.put("/api/admin/settings/customer_max_orders", json={"value": "5"})
    assert res.status_code == 200
    assert res.json()["value"] == "5"
    assert admin_client.get("/api/settings/customer_max_orders").json()["value"] == "5"


def test_customer_max_orders_setting_clamped(admin_client):
    res = admin_client.put("/api/admin/settings/customer_max_orders", json={"value": "999"})
    assert res.status_code == 200
    assert res.json()["value"] == "50"
