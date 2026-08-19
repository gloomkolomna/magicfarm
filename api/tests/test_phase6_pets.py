import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(client, amount):
    img = _real_img()
    r = client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])
    assert r.status_code == 201, f"Credit: {r.status_code}"


def test_list_pets_empty(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/pets")
        assert r.status_code == 200
        assert r.json() == []


def test_settle_pet_returns_cards(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 201
        data = r.json()
        assert data["pet_id"] == 1
        assert data["pet_name"] == "Дракон Эфир"
        assert len(data["drawn_cards"]) == 10
        assert data["required"] > 0


def test_settle_duplicate_pet(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 201
        required = r.json()["required"]
        img = _real_img()
        c.post("/api/stitches/reports", data={
            "amount": str(required),
            "context_type": "pet_settle", "context_id": "1",
        }, files=[("photo_after", ("a.png", img, "image/png"))])

        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 409


def test_settle_unknown_pet(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 999})
        assert r.status_code == 404


def test_pet_settled_on_report_accept(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 201
        required = r.json()["required"]

        img = _real_img()
        r = c.post("/api/stitches/reports", data={
            "amount": str(required),
            "context_type": "pet_settle",
            "context_id": "1",
        }, files=[
            ("photo_after", ("after.png", img, "image/png")),
        ])
        assert r.status_code == 201
        assert r.json()["status"] == "accepted"

        pets = c.get("/api/pets").json()
        assert len(pets) == 1
        assert pets[0]["pet_id"] == 1
        assert pets[0]["pet_name"] == "Дракон Эфир"


# ===== Поселение питомца на клетку локации =====

def _make_pet_cell(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "cols": 2, "rows": 2, "field_kind": "lawn"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "pet"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    return fid, cell["id"]


def _report_settle(c, pet_id, cell_id=None, amount=1):
    img = _real_img()
    data = {"amount": str(amount), "context_type": "pet_settle", "context_id": str(pet_id)}
    if cell_id is not None:
        data["cell_id"] = str(cell_id)
    return c.post("/api/stitches/reports", data=data, files=[("photo_after", ("a.png", img, "image/png"))])


def test_settle_pet_on_cell(admin_client):
    fid, cell_id = _make_pet_cell(admin_client)
    from models import Pet
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        pet = s.query(Pet).filter(Pet.id == 1).first()
        pet.image_url = "/uploads/pet_dragon.png"
        s.commit()
    finally:
        s.close()
    with make_user_client(3001, "player") as c:
        r = c.post(f"/api/pets/cells/{cell_id}/settle", json={"pet_id": 1})
        assert r.status_code == 201, r.text
        assert r.json()["pet_id"] == 1

        rep = _report_settle(c, 1, cell_id=cell_id)
        assert rep.status_code == 201

        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["pet"]["pet_id"] == 1
        assert cell["pet"]["pet_name"] == "Дракон Эфир"
        assert cell["pet"]["pet_image_url"] == "/uploads/pet_dragon.png"


def test_settle_pet_on_cell_occupied(admin_client):
    fid, cell_id = _make_pet_cell(admin_client)
    with make_user_client(3002, "player") as c:
        c.post(f"/api/pets/cells/{cell_id}/settle", json={"pet_id": 1})
        _report_settle(c, 1, cell_id=cell_id)
        r = c.post(f"/api/pets/cells/{cell_id}/settle", json={"pet_id": 2})
        assert r.status_code == 409


def test_settle_pet_on_cell_wrong_kind(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 2, "rows": 2}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "bed"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    with make_user_client(3003, "player") as c:
        r = c.post(f"/api/pets/cells/{cell['id']}/settle", json={"pet_id": 1})
        assert r.status_code == 404


def test_field_detail_pet_zone_with_settled_pet(admin_client):
    fid, cell_id = _make_pet_cell(admin_client)
    r = admin_client.post(f"/api/admin/fields/{fid}/pet-zones", data={"col1": 0, "row1": 0, "col2": 1, "row2": 1})
    assert r.status_code == 201, r.text

    from models import Pet
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        pet = s.query(Pet).filter(Pet.id == 1).first()
        pet.image_url = "/uploads/pet_dragon.png"
        s.commit()
    finally:
        s.close()

    with make_user_client(3005, "player") as c:
        c.post(f"/api/pets/cells/{cell_id}/settle", json={"pet_id": 1})
        _report_settle(c, 1, cell_id=cell_id)

        detail = c.get(f"/api/fields/{fid}").json()
        zones = detail["pet_zones"]
        assert len(zones) == 1
        assert zones[0]["col1"] == 0 and zones[0]["col2"] == 1
        assert zones[0]["pet_id"] == 1
        assert zones[0]["pet_name"] == "Дракон Эфир"
        assert zones[0]["pet_image_url"] == "/uploads/pet_dragon.png"


def test_pet_zone_survives_shrink_then_new_zone(admin_client):
    """Баг: большая карта → уменьшили → новая зона питомца должна отдаваться в игре."""
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "cols": 10, "rows": 10, "field_kind": "lawn"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 4, "rows": 4})

    r = admin_client.post(f"/api/admin/fields/{fid}/pet-zones", data={"col1": 1, "row1": 1, "col2": 2, "row2": 2})
    assert r.status_code == 201, r.text

    with make_user_client(3100, "player") as c:
        detail = c.get(f"/api/fields/{fid}").json()
        assert detail["cols"] == 4 and detail["rows"] == 4
        assert len(detail["pet_zones"]) == 1
        z = detail["pet_zones"][0]
        assert (z["col1"], z["row1"], z["col2"], z["row2"]) == (1, 1, 2, 2)
        pet_cells = [c for c in detail["cells"] if c["kind"] == "pet"]
        assert len(pet_cells) == 4


def test_admin_places_pet_cell_player_sees_it(admin_client):
    """Точечное размещение питомца на клетке: игрок должен видеть клетку питомца."""
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "cols": 10, "rows": 10, "field_kind": "lawn"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 4, "rows": 4})

    r = admin_client.put(f"/api/admin/fields/{fid}/cell/1/1", json={"kind": "pet"})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "pet"

    with make_user_client(3400, "player") as c:
        detail = c.get(f"/api/fields/{fid}").json()
        cells = {f"{x['col']},{x['row']}": x for x in detail["cells"]}
        assert cells["1,1"]["kind"] == "pet"


def test_pet_zone_settle_pet_after_shrink(admin_client):
    """Баг: после уменьшения карты новая зона питомца + заселение питомца должны работать в игре."""
    from models import Pet
    from tests.conftest import TestingSessionLocal
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "cols": 10, "rows": 10, "field_kind": "lawn"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 4, "rows": 4})
    r = admin_client.post(f"/api/admin/fields/{fid}/pet-zones", data={"col1": 1, "row1": 1, "col2": 2, "row2": 2})
    assert r.status_code == 201, r.text

    s = TestingSessionLocal()
    try:
        pet = s.query(Pet).filter(Pet.id == 1).first()
        pet.image_url = "/uploads/pet_dragon.png"
        s.commit()
    finally:
        s.close()

    with make_user_client(3200, "player") as c:
        detail = c.get(f"/api/fields/{fid}").json()
        assert detail["pet_zones"][0]["pet_id"] is None
        cell = [x for x in detail["cells"] if x["kind"] == "pet"][0]
        assert c.post(f"/api/pets/cells/{cell['id']}/settle", json={"pet_id": 1}).status_code == 201
        _report_settle(c, 1, cell_id=cell["id"])
        detail = c.get(f"/api/fields/{fid}").json()
        assert detail["pet_zones"][0]["pet_id"] == 1
        assert detail["pet_zones"][0]["pet_name"] == "Дракон Эфир"
