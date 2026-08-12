import io

from tests.conftest import TestingSessionLocal, make_user_client


def _img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(client, amount):
    client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", _img(), "image/png")),
    ])


def _unlock_garden(vk_id=123, level=1):
    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        if u is None:
            u = User(vk_id=vk_id, role="player", onboarding_done=True, unlocked_garden_level=level)
            s.add(u)
            s.commit()
        elif (u.unlocked_garden_level or 0) < level:
            u.unlocked_garden_level = level
            s.commit()
    finally:
        s.close()


def _make_orchard_field(admin_client, name="Сад"):
    r = admin_client.post("/api/admin/fields", json={
        "name": name, "plant_category": "orchard", "cols": 4, "rows": 3,
    })
    return r.json()["id"]


def _make_orchard_plant(admin_client, level=1, name="Яблоня"):
    r = admin_client.post("/api/admin/catalog/plants", json={
        "name": name, "emoji": "🍎", "category": "orchard", "level": level,
    })
    return r.json()["id"]


def _make_slot(admin_client, fid, col1=0, row1=0, col2=1, row2=0):
    r = admin_client.post(f"/api/admin/fields/{fid}/plant-beds", data={
        "col1": col1, "row1": row1, "col2": col2, "row2": row2,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _player():
    return make_user_client(123, "player")


def _setup_orchard(admin_client):
    fid = _make_orchard_field(admin_client)
    pid = _make_orchard_plant(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    pb_id = _make_slot(admin_client, fid, 0, 0, 1, 0)
    _unlock_garden(123, 1)
    return fid, pid, pb_id


# ===== Создание слота =====

def test_admin_create_plant_bed(admin_client):
    fid = _make_orchard_field(admin_client)
    pb_id = _make_slot(admin_client, fid, 0, 0, 1, 1)
    assert pb_id > 0
    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert len(d["plant_beds"]) == 1
    pb = d["plant_beds"][0]
    assert pb["col1"] == 0 and pb["col2"] == 1
    assert pb["plant_id"] is None
    assert pb["occupant_user_id"] is None
    beds = [c for c in d["cells"] if c["kind"] == "bed"]
    assert len(beds) == 4


# ===== Посадка дерева в слот =====

def test_plant_tree_in_slot(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid, "qty": 3})
    assert res.status_code == 201, res.text
    pb = res.json()
    assert pb["plant_id"] == pid
    assert pb["occupant_user_id"] == 123
    assert pb["plot"] is not None
    assert pb["plot"]["status"] == "planted"
    assert pb["plot"]["qty"] == 3
    assert pb["plot"]["required"] > 0
    assert pb["plant_name"] is not None


def test_plant_in_occupied_slot(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    pid2 = _make_orchard_plant(admin_client, name="Гранат")
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid, pid2]})
    with _player() as c:
        c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid2})
    assert res.status_code == 409


def test_same_plant_in_another_slot(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    pb2 = _make_slot(admin_client, fid, 2, 0, 3, 0)
    with _player() as c:
        c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb2}/plant", json={"plant_id": pid})
    assert res.status_code == 409


def test_plant_in_slot_not_found(admin_client):
    fid, pid, _ = _setup_orchard(admin_client)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/plant-beds/9999/plant", json={"plant_id": pid})
    assert res.status_code == 404


def test_orchard_level_gate(admin_client):
    fid = _make_orchard_field(admin_client)
    pid = _make_orchard_plant(admin_client, level=2, name="Дракожар")
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    pb_id = _make_slot(admin_client, fid)
    _unlock_garden(123, 1)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
    assert res.status_code == 403


def test_plant_non_orchard_in_slot(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    from tests.conftest import TestingSessionLocal
    garden_pid = None
    s = TestingSessionLocal()
    try:
        from models import Plant
        row = s.query(Plant).filter(Plant.category == "garden").first()
        if row is not None:
            garden_pid = row.id
    finally:
        s.close()
    if garden_pid is None:
        return
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid, garden_pid]})
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": garden_pid})
    assert res.status_code == 400


def test_cell_plant_refused_in_orchard(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 400


# ===== Заказы от посадки дерева =====

def test_plant_tree_creates_orders(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    prod = admin_client.get("/api/admin/catalog/products").json()[0]["id"]
    admin_client.post("/api/admin/order-templates", json={
        "source_kind": "plant", "source_id": pid, "product_id": prod,
        "qty": 2, "reward_coins": 50, "customer": "Русалка",
    })
    with _player() as c:
        c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
        orders = c.get("/api/orders?status_filter=open").json()
    assert any(o["product_id"] == prod for o in orders)


# ===== Сбор урожая =====

def test_harvest_tree(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        r = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid, "qty": 2})
        required = r.json()["plot"]["required"]
        plot_id = r.json()["plot"]["id"]
        _credit(c, required)
        inv_before = c.get("/api/farm/inventory").json()
        before_qty = next((i["qty"] for i in inv_before if i["item_kind"] == "plant" and i["item_id"] == pid), 0)
        c.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": required})
        hres = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/harvest")
    assert hres.status_code == 200, hres.text
    pb = hres.json()
    assert pb["plot"]["status"] == "planted"
    assert pb["plot"]["accumulated"] == 0
    with _player() as c:
        inv_after = c.get("/api/farm/inventory").json()
        after_qty = next((i["qty"] for i in inv_after if i["item_kind"] == "plant" and i["item_id"] == pid), 0)
    assert after_qty >= before_qty + 2


def test_harvest_not_grown(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/harvest")
    assert res.status_code == 400


def test_harvest_empty_slot(admin_client):
    fid, _, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/harvest")
    assert res.status_code == 404


def test_harvest_other_user_tree(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
    with make_user_client(555, "player") as c2:
        res = c2.post(f"/api/fields/{fid}/plant-beds/{pb_id}/harvest")
    assert res.status_code == 403


# ===== Удаление слота и детали поля =====

def test_delete_slot_frees_cells(admin_client):
    fid, _, pb_id = _setup_orchard(admin_client)
    res = admin_client.delete(f"/api/admin/fields/{fid}/plant-beds/{pb_id}")
    assert res.status_code == 204
    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert len(d["plant_beds"]) == 0
    beds = [c for c in d["cells"] if c["kind"] == "bed"]
    assert len(beds) == 0


def test_get_field_returns_plant_beds(admin_client):
    fid, pid, pb_id = _setup_orchard(admin_client)
    with _player() as c:
        c.post(f"/api/fields/{fid}/plant-beds/{pb_id}/plant", json={"plant_id": pid})
        d = c.get(f"/api/fields/{fid}").json()
    assert len(d["plant_beds"]) == 1
    pb = d["plant_beds"][0]
    assert pb["occupant_user_id"] == 123
    assert pb["plant_id"] == pid
    assert pb["plot"] is not None
