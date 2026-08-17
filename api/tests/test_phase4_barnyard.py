import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _make_barnyard_cell(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "cols": 2, "rows": 2, "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}], "kind": "barnyard"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cell = [c for c in detail["cells"] if c["col"] == 0 and c["row"] == 0][0]
    return fid, cell["id"]


def _set_animal_images(animal_id):
    from models import Animal
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        a = s.query(Animal).filter(Animal.id == animal_id).first()
        a.image_empty_pen_url = "/uploads/empty.png"
        a.image_pen_url = "/uploads/pen.png"
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


def _report(c, amount, context_type, context_id, name="a.png"):
    return c.post(
        "/api/stitches/reports",
        data={"amount": str(amount), "context_type": context_type, "context_id": str(context_id)},
        files=[("photo_after", (name, _real_img(), "image/png"))],
    )


def _install(c, cell_id, animal_id=1):
    return c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": animal_id}).json()


def _full_ready_pen(c, cell_id, animal_id=1):
    installed = _install(c, cell_id, animal_id)
    prepared = c.post(f"/api/animals/pens/{installed['id']}/prepare").json()
    rep = _report(c, prepared["required"], "animal_build", installed["id"])
    assert rep.status_code == 201, rep.text
    return installed


# ===== Установка животного на клетку локации =====

def test_install_animal_on_cell(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2001, "player") as c:
        r = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 1})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["animal_id"] == 1
        assert data["cell_id"] == cell_id
        assert data["status"] == "placed"
        assert data["required"] == 0
        assert data["drawn_cards_json"] is None

        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["barnyard"]["animal_id"] == 1
        assert cell["barnyard"]["status"] == "placed"


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


def test_install_duplicate_animal_on_cells(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "cols": 2, "rows": 2, "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}, {"col": 1, "row": 0}], "kind": "barnyard"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cells = [c for c in detail["cells"] if c["kind"] == "barnyard"]
    assert len(cells) == 2
    with make_user_client(2011, "player") as c:
        c.post(f"/api/animals/cells/{cells[0]['id']}/install", json={"animal_id": 1})
        r = c.post(f"/api/animals/cells/{cells[1]['id']}/install", json={"animal_id": 1})
        assert r.status_code == 409
        assert "уже заселено" in r.json()["detail"]


def test_install_unknown_animal(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2012, "player") as c:
        r = c.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": 999})
        assert r.status_code == 404


def test_install_sets_opening_order(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "cols": 2, "rows": 2, "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 0, "row": 0}, {"col": 1, "row": 0}], "kind": "barnyard"})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cells = [c for c in detail["cells"] if c["kind"] == "barnyard"]
    assert len(cells) == 2
    with make_user_client(2013, "player") as c:
        r1 = c.post(f"/api/animals/cells/{cells[0]['id']}/install", json={"animal_id": 1})
        assert r1.status_code == 200, r1.text
        assert r1.json()["opening_order"] == 1
        r2 = c.post(f"/api/animals/cells/{cells[1]['id']}/install", json={"animal_id": 2})
        assert r2.json()["opening_order"] == 2


# ===== Подготовка загона: карты и норма =====

def test_prepare_pen_draws_norm(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2004, "player") as c:
        installed = _install(c, cell_id)
        r = c.post(f"/api/animals/pens/{installed['id']}/prepare")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "building"
        assert data["required"] > 0
        assert data["accumulated"] == 0
        assert data["drawn_cards_json"]


def test_prepare_pen_requires_placed(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2005, "player") as c:
        installed = _install(c, cell_id)
        c.post(f"/api/animals/pens/{installed['id']}/prepare")
        r = c.post(f"/api/animals/pens/{installed['id']}/prepare")
        assert r.status_code == 409

        with make_user_client(2014, "player") as c2:
            r2 = c2.post(f"/api/animals/pens/{installed['id']}/prepare")
            assert r2.status_code == 404


def test_animal_build_via_report(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2006, "player") as c:
        installed = _install(c, cell_id)
        prepared = c.post(f"/api/animals/pens/{installed['id']}/prepare").json()
        rep = _report(c, prepared["required"], "animal_build", installed["id"])
        assert rep.status_code == 201, rep.text
        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["barnyard"]["status"] == "ready"


def test_animal_build_report_insufficient_amount(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2007, "player") as c:
        installed = _install(c, cell_id)
        prepared = c.post(f"/api/animals/pens/{installed['id']}/prepare").json()
        rep = _report(c, prepared["required"] - 1, "animal_build", installed["id"])
        assert rep.status_code == 400
        assert "Норма постройки" in rep.json()["detail"]


# ===== Сбор продукции: кубик без отшива, склад шатра =====

def test_collect_product_no_stitch(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2008, "player") as c:
        installed = _full_ready_pen(c, cell_id)
        r = c.post(f"/api/animals/pens/{installed['id']}/produce")
        assert r.status_code == 200
        data = r.json()
        assert 1 <= data["die"] <= 6
        assert data["qty_added"] == data["die"]
        assert data["product_id"] == pid
        assert data["storage_qty"] == data["die"]

        inv = c.get("/api/farm/inventory").json()
        assert not any(i["item_kind"] == "product" and i["item_id"] == pid for i in inv)

        r2 = c.post(f"/api/animals/pens/{installed['id']}/produce")
        assert r2.status_code == 200
        assert r2.json()["storage_qty"] == data["die"] + r2.json()["die"]


def test_collect_not_ready(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2009, "player") as c:
        installed = _install(c, cell_id)
        r = c.post(f"/api/animals/pens/{installed['id']}/produce")
        assert r.status_code == 409


def test_tent_storage_lists_items(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    _make_animal_product(1)
    with make_user_client(2015, "player") as c:
        installed = _full_ready_pen(c, cell_id)
        c.post(f"/api/animals/pens/{installed['id']}/produce")
        r = c.get("/api/animals/tents/storage")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["qty"] >= 1
        assert data["pending"] == []
        assert data["norm_per_unit"] == 100


# ===== Забор со склада шатра: норма × количество =====

def test_withdraw_creates_pending(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2016, "player") as c:
        installed = _full_ready_pen(c, cell_id)
        total = 0
        while total < 5:
            total = c.post(f"/api/animals/pens/{installed['id']}/produce").json()["storage_qty"]

        r = c.post("/api/animals/tents/withdraw", json={"product_id": pid, "qty": 3})
        assert r.status_code == 200
        w = r.json()
        assert w["qty"] == 3
        assert w["required"] == 100 * 3
        assert w["status"] == "pending"

        st = c.get("/api/animals/tents/storage").json()
        assert len(st["pending"]) == 1

        r2 = c.post("/api/animals/tents/withdraw", json={"product_id": pid, "qty": total})
        assert r2.status_code == 400
        assert "Недостаточно" in r2.json()["detail"]


def test_withdraw_report_credits_inventory(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2017, "player") as c:
        installed = _full_ready_pen(c, cell_id)
        total = 0
        while total < 4:
            total = c.post(f"/api/animals/pens/{installed['id']}/produce").json()["storage_qty"]

        w = c.post("/api/animals/tents/withdraw", json={"product_id": pid, "qty": 2}).json()
        rep = _report(c, w["required"], "barnyard_withdraw", w["id"], name="b.png")
        assert rep.status_code == 201, rep.text

        inv = c.get("/api/farm/inventory").json()
        row = [i for i in inv if i["item_kind"] == "product" and i["item_id"] == pid]
        assert row and row[0]["qty"] == 2

        st = c.get("/api/animals/tents/storage").json()
        assert st["pending"] == []
        item = [i for i in st["items"] if i["product_id"] == pid]
        assert item and item[0]["qty"] == total - 2

        rep2 = _report(c, w["required"], "barnyard_withdraw", w["id"], name="c.png")
        assert rep2.status_code == 409


def test_withdraw_report_insufficient_amount(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2018, "player") as c:
        installed = _full_ready_pen(c, cell_id)
        while c.post(f"/api/animals/pens/{installed['id']}/produce").json()["storage_qty"] < 2:
            pass
        w = c.post("/api/animals/tents/withdraw", json={"product_id": pid, "qty": 2}).json()
        rep = _report(c, w["required"] - 1, "barnyard_withdraw", w["id"])
        assert rep.status_code == 400
        assert "Норма забора" in rep.json()["detail"]


def test_withdraw_without_stock(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2019, "player") as c:
        r = c.post("/api/animals/tents/withdraw", json={"product_id": pid, "qty": 1})
        assert r.status_code == 400


def test_withdraw_uses_personal_norm(admin_client):
    fid, cell_id = _make_barnyard_cell(admin_client)
    pid = _make_animal_product(1)
    with make_user_client(2020, "player") as c:
        c.put("/api/crystal-norms/mine", json={"norms": {
            "green": {"norm": 10, "treasure": 0},
            "blue": {"norm": 20, "treasure": 0},
            "violet": {"norm": 30, "treasure": 0},
        }, "dice_norm": 40, "animal_product_norm": 7})
        installed = _full_ready_pen(c, cell_id)
        while c.post(f"/api/animals/pens/{installed['id']}/produce").json()["storage_qty"] < 2:
            pass
        w = c.post("/api/animals/tents/withdraw", json={"product_id": pid, "qty": 2}).json()
        assert w["required"] == 7 * 2


# ===== Норма продукции скотного двора в /mine =====

def test_mine_animal_product_norm_default_and_set(admin_client):
    with make_user_client(2021, "player") as c:
        mine = c.get("/api/crystal-norms/mine").json()
        assert mine["animal_product_norm"] == 100

        c.put("/api/crystal-norms/mine", json={"norms": {
            "green": {"norm": 10, "treasure": 0},
            "blue": {"norm": 20, "treasure": 0},
            "violet": {"norm": 30, "treasure": 0},
        }, "dice_norm": 200, "animal_product_norm": 55})
        mine2 = c.get("/api/crystal-norms/mine").json()
        assert mine2["animal_product_norm"] == 55


def test_mine_animal_product_norm_invalid(admin_client):
    with make_user_client(2022, "player") as c:
        r = c.put("/api/crystal-norms/mine", json={"norms": {
            "green": {"norm": 10, "treasure": 0},
            "blue": {"norm": 20, "treasure": 0},
            "violet": {"norm": 30, "treasure": 0},
        }, "dice_norm": 200, "animal_product_norm": 0})
        assert r.status_code == 400


# ===== Картинки загона в деталях клетки =====

def test_field_cell_detail_has_pen_images(admin_client):
    _set_animal_images(1)
    fid, cell_id = _make_barnyard_cell(admin_client)
    with make_user_client(2023, "player") as c:
        _install(c, cell_id)
        detail = c.get(f"/api/fields/{fid}").json()
        cell = [x for x in detail["cells"] if x["id"] == cell_id][0]
        assert cell["barnyard"]["image_empty_pen_url"] == "/uploads/empty.png"
        assert cell["barnyard"]["image_pen_url"] == "/uploads/pen.png"
        assert "image_harvested_url" not in cell["barnyard"]
