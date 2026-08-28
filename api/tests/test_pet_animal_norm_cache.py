from tests.conftest import make_user_client


def _make_pet_cell(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "cols": 2, "rows": 2, "field_kind": "lawn"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "pet"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    return fid, cell["id"]


def _make_barnyard_cell(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "cols": 2, "rows": 2, "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "barnyard"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    return fid, cell["id"]


def _pet_norm_rows(user_id):
    from models import UserPetNorm
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        return s.query(UserPetNorm).filter(UserPetNorm.user_id == user_id).all()
    finally:
        s.close()


def _animal_norm_rows(user_id):
    from models import UserAnimalNorm
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        return s.query(UserAnimalNorm).filter(UserAnimalNorm.user_id == user_id).all()
    finally:
        s.close()


# ===== Питомцы: норма заселения фиксируется после первого рандома =====

def test_settle_pet_same_norm_on_repeat(admin_client):
    with make_user_client(4001, "player") as c:
        r1 = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r1.status_code == 201, r1.text
        r2 = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r2.status_code == 201, r2.text
        assert r1.json()["required"] == r2.json()["required"]
        assert r1.json()["drawn_cards"] == r2.json()["drawn_cards"]

    rows = _pet_norm_rows(4001)
    assert len(rows) == 1
    assert rows[0].norm == r1.json()["required"]


def test_settle_pet_on_cell_same_norm_after_reopen(admin_client):
    fid, cell_id = _make_pet_cell(admin_client)
    with make_user_client(4002, "player") as c:
        r1 = c.post(f"/api/pets/cells/{cell_id}/settle", json={"pet_id": 1})
        assert r1.status_code == 201, r1.text
        r2 = c.post(f"/api/pets/cells/{cell_id}/settle", json={"pet_id": 1})
        assert r2.status_code == 201, r2.text
        assert r1.json()["required"] == r2.json()["required"]
        assert r1.json()["drawn_cards"] == r2.json()["drawn_cards"]


def test_pet_norm_is_per_pet(admin_client):
    with make_user_client(4003, "player") as c:
        r1 = c.post("/api/pets/settle", json={"pet_id": 1})
        r2 = c.post("/api/pets/settle", json={"pet_id": 2})
        assert r1.status_code == 201 and r2.status_code == 201

    rows = _pet_norm_rows(4003)
    assert len(rows) == 2
    assert {r.pet_id for r in rows} == {1, 2}


def test_pet_norm_is_per_player(admin_client):
    with make_user_client(4004, "player") as c1:
        r1 = c1.post("/api/pets/settle", json={"pet_id": 1})
        assert r1.status_code == 201
    with make_user_client(4005, "player") as c2:
        r2 = c2.post("/api/pets/settle", json={"pet_id": 1})
        assert r2.status_code == 201
        assert r2.json()["drawn_cards"] is not None

    assert len(_pet_norm_rows(4004)) == 1
    assert len(_pet_norm_rows(4005)) == 1


# ===== Животные: норма подготовки загона фиксируется после первого рандома =====

def test_prepare_pen_same_norm_on_new_cycle(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(4101, "player") as c:
        slot = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        p1 = c.post(f"/api/animals/pens/{slot['id']}/prepare").json()

        c.delete(f"/api/animals/pens/{slot['id']}")

        slot2 = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        p2 = c.post(f"/api/animals/pens/{slot2['id']}/prepare").json()

        assert p1["required"] == p2["required"]
        assert p1["drawn_cards_json"] == p2["drawn_cards_json"]

    rows = _animal_norm_rows(4101)
    assert len(rows) == 1
    assert rows[0].norm == p1["required"]


def test_animal_norm_is_per_animal(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    fid2, cell_id2 = _make_barnyard_cell(admin_client)
    with make_user_client(4102, "player") as c:
        slot1 = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        c.post(f"/api/animals/pens/{slot1['id']}/prepare")
        slot2 = c.post(f"/api/animals/cells/{cell_id2}/install", json={"animal_id": 2}).json()
        c.post(f"/api/animals/pens/{slot2['id']}/prepare")

    rows = _animal_norm_rows(4102)
    assert len(rows) == 2
    assert {r.animal_id for r in rows} == {1, 2}
