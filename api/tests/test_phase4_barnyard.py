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
    assert r.status_code == 201, f"Credit failed: {r.status_code} {r.text}"


def _seed_barnyard_slot(vk_id: int, status="empty"):
    from models import BarnyardSlot
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        slot = BarnyardSlot(user_id=vk_id, status=status)
        s.add(slot)
        s.commit()
        s.refresh(slot)
        return slot.id
    finally:
        s.close()


def test_list_pens_empty(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/animals/pens")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 8
        for pen in data:
            assert pen["status"] == "empty"


def test_install_animal(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "building"
        assert data["animal_id"] == 1
        assert data["required"] > 0
        assert data["accumulated"] == 0


def test_install_sets_opening_order(admin_client):
    sid1 = _seed_barnyard_slot(123)
    sid2 = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/animals/pens/{sid1}/install", json={"animal_id": 1})
        assert r.json()["opening_order"] == 1
        r = c.post(f"/api/animals/pens/{sid2}/install", json={"animal_id": 2})
        assert r.json()["opening_order"] == 2


def test_install_duplicate_animal(admin_client):
    sid1 = _seed_barnyard_slot(123)
    sid2 = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        c.post(f"/api/animals/pens/{sid1}/install", json={"animal_id": 1})
        r = c.post(f"/api/animals/pens/{sid2}/install", json={"animal_id": 1})
        assert r.status_code == 409


def test_install_unknown_animal(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 999})
        assert r.status_code == 404


def test_invest_builds_pen(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        required = r.json()["required"]
        r = c.post(f"/api/animals/pens/{sid}/invest", json={"amount": required})
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


def test_invest_partial(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        required = r.json()["required"]
        half = max(1, required // 2)
        c.post(f"/api/animals/pens/{sid}/invest", json={"amount": half})
        r = c.post(f"/api/animals/pens/{sid}/invest", json={"amount": required - half})
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


def test_produce_rolls_die(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        required = r.json()["required"]
        c.post(f"/api/animals/pens/{sid}/invest", json={"amount": required})
        r = c.post(f"/api/animals/pens/{sid}/produce")
        assert r.status_code == 200
        data = r.json()
        assert 1 <= data["die"] <= 6
        assert data["required"] == 200 * data["die"]


def test_produce_returns_product_coins(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        required = r.json()["required"]
        c.post(f"/api/animals/pens/{sid}/invest", json={"amount": required})
        r = c.post(f"/api/animals/pens/{sid}/produce")
        assert r.json()["product_coins"] == 5


def test_second_animal_coins_higher(admin_client):
    sid1 = _seed_barnyard_slot(123)
    sid2 = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/animals/pens/{sid1}/install", json={"animal_id": 1})
        assert r.json()["opening_order"] == 1
        req1 = r.json()["required"]
        c.post(f"/api/animals/pens/{sid1}/invest", json={"amount": req1})
        r = c.post(f"/api/animals/pens/{sid2}/install", json={"animal_id": 2})
        assert r.json()["opening_order"] == 2
        req2 = r.json()["required"]
        c.post(f"/api/animals/pens/{sid2}/invest", json={"amount": req2})
        r = c.post(f"/api/animals/pens/{sid2}/produce")
        assert r.json()["product_coins"] == 10


def test_produce_not_ready(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/animals/pens/{sid}/produce")
        assert r.status_code == 409


def test_list_pens_shows_data(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        r = c.get("/api/animals/pens")
        data = r.json()
        assert len(data) == 8
        filled = [p for p in data if p["animal_id"] is not None]
        assert len(filled) == 1
        assert filled[0]["animal_name"] == "Ватная овечка"


def test_other_user_pen_forbidden(admin_client):
    sid = _seed_barnyard_slot(999)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        assert r.status_code == 404


# ===== Установка животного на клетку локации =====

def _make_barnyard_cell(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "cols": 2, "rows": 2, "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "barnyard"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    return fid, cell["id"]


def test_install_animal_on_cell(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2001, "player") as c:
        r = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["animal_id"] == 1
        assert data["cell_id"] == cell_id

        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["barnyard"]["animal_id"] == 1
        assert cell["barnyard"]["status"] == "building"


def test_install_animal_on_cell_locked(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    from models import User
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 2002).first()
        if u is None:
            u = User(vk_id=2002, role="player", unlocked_barnyard=0, unlocked_pets=0)
            s.add(u)
            s.commit()
    finally:
        s.close()

    with make_user_client(2002, "player") as c:
        r = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
        assert r.status_code == 403


def test_install_animal_on_cell_wrong_kind(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 2, "rows": 2}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "bed"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    with make_user_client(2003, "player") as c:
        r = c.post(f"/api/animals/cells/{cell['id']}/install", json={"animal_id": 1})
        assert r.status_code == 404


def test_animal_build_via_report(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2004, "player") as c:
        installed = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        required = installed["required"]
        rep = c.post(
            "/api/stitches/reports",
            data={"amount": str(required), "context_type": "animal_build", "context_id": str(installed["id"])},
            files=[("photo_after", ("a.png", _real_img(), "image/png"))],
        )
        assert rep.status_code == 201, rep.text
        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["barnyard"]["status"] == "ready"


def test_produce_die_no_immediate_repeat(admin_client):
    sid = _seed_barnyard_slot(123)
    with make_user_client(123, "player") as c:
        _credit(c, 50000)
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        c.post(f"/api/animals/pens/{sid}/invest", json={"amount": r.json()["required"]})
        r1 = c.post(f"/api/animals/pens/{sid}/produce").json()
        assert 1 <= r1["die"] <= 6

        r2 = c.post(f"/api/animals/pens/{sid}/produce")
        assert r2.status_code == 409
        assert "прошлой продукции" in r2.json()["detail"]


def test_produce_uses_personal_dice_norm(admin_client):
    sid = _seed_barnyard_slot(130)
    with make_user_client(130, "player") as c:
        _credit(c, 50000)
        c.put("/api/crystal-norms/mine", json={"norms": {
            "green": {"norm": 10, "treasure": 0},
            "blue": {"norm": 20, "treasure": 0},
            "violet": {"norm": 30, "treasure": 0},
        }, "dice_norm": 40})
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        c.post(f"/api/animals/pens/{sid}/invest", json={"amount": r.json()["required"]})
        data = c.post(f"/api/animals/pens/{sid}/produce").json()
        assert data["required"] == 40 * data["die"]


# ===== Привязка загонов вкладки к клеткам поля =====

def _make_barnyard_cells(admin_client, coords):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "cols": 3, "rows": 3, "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": c, "row": r} for c, r in coords], "kind": "barnyard"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cells = {c["id"]: c for c in detail["cells"] if c["kind"] == "barnyard"}
    return fid, cells


def test_install_from_tab_binds_to_free_cell(admin_client):
    coords = [(0, 0), (1, 0)]
    fid, cells = _make_barnyard_cells(admin_client, coords)
    first_id = min(cells.values(), key=lambda c: (c["row"], c["col"]))["id"]
    second_id = max(cells.values(), key=lambda c: (c["row"], c["col"]))["id"]

    sid1 = _seed_barnyard_slot(2100)
    sid2 = _seed_barnyard_slot(2100)
    with make_user_client(2100, "player") as c:
        r = c.post(f"/api/animals/pens/{sid1}/install", json={"animal_id": 1})
        assert r.status_code == 200
        assert r.json()["cell_id"] == first_id

        r = c.post(f"/api/animals/pens/{sid2}/install", json={"animal_id": 2})
        assert r.json()["cell_id"] == second_id

        detail = c.get(f"/api/fields/{fid}").json()
        bound = {x["barnyard"]["animal_id"]: x["id"] for x in detail["cells"] if x.get("barnyard")}
        assert bound == {1: first_id, 2: second_id}


def test_install_from_tab_skips_occupied_cell(admin_client):
    coords = [(0, 0), (1, 0)]
    fid, cells = _make_barnyard_cells(admin_client, coords)
    first_id = min(cells.values(), key=lambda c: (c["row"], c["col"]))["id"]
    second_id = max(cells.values(), key=lambda c: (c["row"], c["col"]))["id"]

    sid_other = _seed_barnyard_slot(2101)
    with make_user_client(2101, "player") as c:
        c.post(f"/api/animals/pens/{sid_other}/install", json={"animal_id": 1})
        assert c.get("/api/animals/pens").json()[0]["cell_id"] == first_id

    sid_mine = _seed_barnyard_slot(2102)
    with make_user_client(2102, "player") as c:
        r = c.post(f"/api/animals/pens/{sid_mine}/install", json={"animal_id": 2})
        assert r.json()["cell_id"] == second_id


def test_install_from_tab_without_cells_leaves_null(admin_client):
    sid = _seed_barnyard_slot(2103)
    with make_user_client(2103, "player") as c:
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        assert r.status_code == 200
        assert r.json()["cell_id"] is None


def test_install_from_tab_locked_without_unlocked_pens(admin_client):
    from models import User
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 2104).first()
        if u is None:
            u = User(vk_id=2104, role="player", unlocked_barnyard=0, unlocked_pets=0)
            s.add(u)
            s.commit()
    finally:
        s.close()

    sid = _seed_barnyard_slot(2104)
    with make_user_client(2104, "player") as c:
        r = c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        assert r.status_code == 403
        assert "Животноводство" in r.json()["detail"]


def _set_animal_images(animal_id):
    from models import Animal
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        a = s.query(Animal).filter(Animal.id == animal_id).first()
        a.image_empty_pen_url = "/uploads/empty.png"
        a.image_pen_url = "/uploads/pen.png"
        a.image_harvested_url = "/uploads/harvested.png"
        s.commit()
    finally:
        s.close()


def _make_animal_product(animal_id):
    from models import Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        p = s.query(Product).filter(Product.animal_id == animal_id).first()
        if p is None:
            p = Product(code=f"animal_product_{animal_id}", name="Продукция", animal_id=animal_id, production_kind="barnyard")
            s.add(p)
            s.commit()
            s.refresh(p)
        return p.id
    finally:
        s.close()


def test_pens_payload_has_pen_images(admin_client):
    _set_animal_images(1)
    sid = _seed_barnyard_slot(2105)
    with make_user_client(2105, "player") as c:
        _credit(c, 50000)
        c.post(f"/api/animals/pens/{sid}/install", json={"animal_id": 1})
        pens = c.get("/api/animals/pens").json()
        filled = [p for p in pens if p["animal_id"] is not None][0]
        assert filled["image_empty_pen_url"] == "/uploads/empty.png"
        assert filled["image_pen_url"] == "/uploads/pen.png"
        assert filled["image_harvested_url"] == "/uploads/harvested.png"


def test_field_cell_detail_has_empty_pen_image(admin_client):
    _set_animal_images(1)
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2106, "player") as c:
        c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["barnyard"]["image_empty_pen_url"] == "/uploads/empty.png"


# ===== Производство: отшив и зачисление продукции =====

def _full_cycle_client(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    _set_animal_images(1)
    return fid, cell_id


def test_animal_build_report_insufficient_amount(admin_client):
    fid, cell_id = _full_cycle_client(admin_client)
    with make_user_client(2107, "player") as c:
        installed = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        rep = c.post(
            "/api/stitches/reports",
            data={"amount": str(installed["required"] - 1), "context_type": "animal_build", "context_id": str(installed["id"])},
            files=[("photo_after", ("a.png", _real_img(), "image/png"))],
        )
        assert rep.status_code == 400
        assert "Норма постройки" in rep.json()["detail"]


def test_animal_produce_credits_inventory(admin_client):
    fid, cell_id = _full_cycle_client(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2108, "player") as c:
        installed = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        rep = c.post(
            "/api/stitches/reports",
            data={"amount": str(installed["required"]), "context_type": "animal_build", "context_id": str(installed["id"])},
            files=[("photo_after", ("a.png", _real_img(), "image/png"))],
        )
        assert rep.status_code == 201, rep.text

        produced = c.post(f"/api/animals/pens/{installed['id']}/produce").json()
        die = produced["die"]
        rep2 = c.post(
            "/api/stitches/reports",
            data={"amount": str(produced["required"] + 5000), "context_type": "animal_produce", "context_id": str(installed["id"])},
            files=[("photo_after", ("b.png", _real_img(), "image/png"))],
        )
        assert rep2.status_code == 201, rep2.text

        inv = c.get("/api/farm/inventory").json()
        row = [i for i in inv if i["item_kind"] == "product" and i["item_id"] == pid]
        assert row and row[0]["qty"] == die

        again = c.post(f"/api/animals/pens/{installed['id']}/produce")
        assert again.status_code == 200


def test_animal_produce_insufficient_amount(admin_client):
    fid, cell_id = _full_cycle_client(admin_client)
    with make_user_client(2109, "player") as c:
        installed = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        c.post(
            "/api/stitches/reports",
            data={"amount": str(installed["required"]), "context_type": "animal_build", "context_id": str(installed["id"])},
            files=[("photo_after", ("a.png", _real_img(), "image/png"))],
        )
        produced = c.post(f"/api/animals/pens/{installed['id']}/produce").json()
        rep = c.post(
            "/api/stitches/reports",
            data={"amount": str(produced["required"] - 1), "context_type": "animal_produce", "context_id": str(installed["id"])},
            files=[("photo_after", ("b.png", _real_img(), "image/png"))],
        )
        assert rep.status_code == 400
        assert "Норма продукции" in rep.json()["detail"]


def test_animal_produce_report_without_roll(admin_client):
    fid, cell_id = _full_cycle_client(admin_client)
    with make_user_client(2110, "player") as c:
        installed = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1}).json()
        rep = c.post(
            "/api/stitches/reports",
            data={"amount": "100", "context_type": "animal_produce", "context_id": str(installed["id"])},
            files=[("photo_after", ("a.png", _real_img(), "image/png"))],
        )
        assert rep.status_code == 409

