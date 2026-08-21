import io
import os

from tests.conftest import TestingSessionLocal, make_user_client
from tests.test_phase11_infirmary import _brew_remedy, _img_bytes


def _seed_ingredient(name: str) -> int:
    from models import Ingredient
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "ingredient"), Ingredient, s)
        ing = Ingredient(code=code, name=name)
        s.add(ing)
        s.commit()
        s.refresh(ing)
        return ing.id
    finally:
        s.close()


def _seed_remedy(name: str, items: list[tuple[int, int]]) -> int:
    from models import Remedy, RemedyRecipeItem
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "remedy"), Remedy, s)
        r = Remedy(code=code, name=name)
        s.add(r)
        s.flush()
        for ing_id, qty in items:
            s.add(RemedyRecipeItem(remedy_id=r.id, ingredient_id=ing_id, qty=qty))
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def _seed_disease(name: str, remedy_id: int) -> int:
    from models import Disease
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "disease"), Disease, s)
        d = Disease(code=code, name=name, remedy_id=remedy_id)
        s.add(d)
        s.commit()
        s.refresh(d)
        return d.id
    finally:
        s.close()


def _seed_field(kind: str, name: str) -> int:
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code=name.lower(), name=name, cols=2, rows=1, field_kind=kind, min_level=0)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id
    finally:
        s.close()


def _seed_patient(name: str, disease_id: int, level: int = 1) -> tuple[int, dict[str, int]]:
    from models import Field, PatientAnimal
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "patient"), PatientAnimal, s)
        p = PatientAnimal(code=code, name=name, level=level, disease_id=disease_id)
        s.add(p)
        s.flush()
        scenes: dict[str, int] = {}
        for stage, label in (("sick", "больное"), ("treating", "на лечении"), ("healthy", "здоровое")):
            fcode = _unique_code(_auto_code(f"{name}_{stage}", "scene"), Field, s)
            f = Field(code=fcode, name=f"{name} — {label}", cols=3, rows=2,
                      field_kind="infirmary", clinic_animal_id=p.id, clinic_stage=stage)
            s.add(f)
            s.flush()
            scenes[stage] = f.id
        s.commit()
        return p.id, scenes
    finally:
        s.close()


def _seed_user_ingredient(vk_id: int, ingredient_id: int, qty: int) -> None:
    from models import UserIngredient
    s = TestingSessionLocal()
    try:
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_achievement(kind: str, value: int = 1, production_code: str | None = None) -> int:
    from models import Achievement
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(kind, "ach"), Achievement, s)
        a = Achievement(code=code, name=kind, condition_kind=kind, condition_value=value,
                        production_code=production_code)
        s.add(a)
        s.commit()
        s.refresh(a)
        return a.id
    finally:
        s.close()


def _seed_device(admin_client, lab_id: int, remedy_id: int, col: int = 0) -> int:
    r = admin_client.post(f"/api/admin/fields/{lab_id}/remedy-device-cells", json={
        "col1": col, "row1": 0, "col2": col, "row2": 0, "install_cards": 1, "remedy_ids": [remedy_id],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _diagnose(c, patient_id: int, disease_id: int):
    return c.post(f"/api/infirmary/patients/{patient_id}/diagnose", json={"disease_id": disease_id})


def test_brew_consumes_and_treats(admin_client):
    ing1 = _seed_ingredient("Роса")
    ing2 = _seed_ingredient("Папоротник")
    rid = _seed_remedy("Мазь от кашля", [(ing1, 3), (ing2, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing1, 5)
    _seed_user_ingredient(123, ing2, 1)
    cell_id = _seed_device(admin_client, lab, rid)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        assert d.status_code == 200
        card_id = d.json()["remedy_card_id"]

        _brew_remedy(c, cell_id, card_id)

        apo = {a["ingredient_id"]: a["qty"] for a in c.get("/api/apothecary").json()}
        assert apo[ing1] == 2
        assert apo.get(ing2, 0) == 0

        stock = c.get(f"/api/remedy-lab/{lab}").json()["remedies_stock"]
        assert stock and stock[0]["remedy_id"] == rid and stock[0]["qty"] == 1

        inf = c.get("/api/infirmary").json()
        l1inf = next(x for x in inf["levels"] if x["level"] == 1)
        assert l1inf["patients"][0]["healed"] is False

        assert c.post(f"/api/infirmary/patients/{pid}/give-remedy").status_code == 200

        # Пациент «вылечен», но карточка в коллекцию ещё НЕ выдана (только после выпуска).
        col = c.get("/api/collection").json()
        l1 = next(x for x in col["levels"] if x["level"] == 1)
        assert l1["cards"][0]["earned"] is False

        inf = c.get("/api/infirmary").json()
        l1inf = next(x for x in inf["levels"] if x["level"] == 1)
        assert l1inf["patients"][0]["healed"] is True
        assert l1inf["patients"][0]["card_earned"] is False


def test_release_grants_card(admin_client):
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing1, 5)
    cell_id = _seed_device(admin_client, lab, rid)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        _brew_remedy(c, cell_id, card_id)
        assert c.post(f"/api/infirmary/patients/{pid}/give-remedy").status_code == 200

        r = c.post(f"/api/infirmary/patients/{pid}/release")
        assert r.status_code == 200
        assert r.json()["card_earned"] is True

        col = c.get("/api/collection").json()
        l1 = next(x for x in col["levels"] if x["level"] == 1)
        assert l1["cards"][0]["earned"] is True

        # Повторный выпуск — 400.
        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 400


def test_release_requires_treated(admin_client):
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid, _ = _seed_patient("Лис", did, 1)

    with make_user_client(123, "player") as c:
        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 400


def test_brew_insufficient_ingredients_400(admin_client):
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 3)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing1, 2)
    cell_id = _seed_device(admin_client, lab, rid)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        c.post(f"/api/remedy-lab/cells/{cell_id}/install")
        c.post("/api/stitches/reports", data={
            "amount": "100000", "context_type": "remedy_device_install", "context_id": str(cell_id),
        }, files=[("photo_after", ("a.png", _img_bytes(), "image/png"))])
        r = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert r.status_code == 400
        assert "Недостаточно" in r.json()["detail"]


def test_brew_unknown_card_404(admin_client):
    with make_user_client(123, "player") as c:
        assert c.post("/api/remedy-cards/9999/brew", json={"cell_id": 1}).status_code == 404


def test_brew_already_healed_400(admin_client):
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing1, 5)
    cell_id = _seed_device(admin_client, lab, rid)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        _brew_remedy(c, cell_id, card_id)
        assert c.post(f"/api/infirmary/patients/{pid}/give-remedy").status_code == 200
        r = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert r.status_code == 400


def test_collection(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    _seed_patient("Лис", did, 1)
    with make_user_client(123, "player") as c:
        r = c.get("/api/collection")
        assert r.status_code == 200
        l1 = next(x for x in r.json()["levels"] if x["level"] == 1)
        assert l1["total_count"] == 1
        assert l1["earned_count"] == 0
        assert l1["cards"][0]["earned"] is False


def test_achievement_healed_count_awarded_once(admin_client):
    _seed_achievement("healed_count", 1)
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing1, 5)
    cell_id = _seed_device(admin_client, lab, rid)
    ing2 = _seed_ingredient("Вода")
    rid2 = _seed_remedy("Бальзам", [(ing2, 1)])
    did2 = _seed_disease("Хромота", rid2)
    pid2, _ = _seed_patient("Сова", did2, 1)
    _seed_user_ingredient(123, ing2, 5)
    cell2 = _seed_device(admin_client, lab, rid2, col=1)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        _brew_remedy(c, cell_id, card_id)
        assert c.post(f"/api/infirmary/patients/{pid}/give-remedy").status_code == 200
        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 200

        earned = [a for a in c.get("/api/achievements").json() if a["condition_kind"] == "healed_count"]
        assert len(earned) == 1
        assert earned[0]["earned"] is True

        d2 = _diagnose(c, pid2, did2)
        _brew_remedy(c, cell2, d2.json()["remedy_card_id"])
        c.post(f"/api/infirmary/patients/{pid2}/give-remedy")
        c.post(f"/api/infirmary/patients/{pid2}/release")

        earned2 = [a for a in c.get("/api/achievements").json() if a["condition_kind"] == "healed_count"]
        assert len(earned2) == 1


def test_brew_requires_auth(client):
    assert client.post("/api/remedy-cards/1/brew", json={"cell_id": 1}).status_code == 401
    assert client.get("/api/collection").status_code == 401


def test_brew_consumes_plants_from_inventory(admin_client):
    from models import Inventory
    pid = next(p["id"] for p in admin_client.get("/api/plants").json() if p["code"] == "jackobob")
    ing = _seed_ingredient("Роса")

    r = admin_client.post("/api/admin/remedies", json={
        "name": "Мазь смешанная",
        "recipe_items": [{"ingredient_id": ing, "qty": 1}, {"plant_id": pid, "qty": 2}],
    })
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pat, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing, 5)
    cell_id = _seed_device(admin_client, lab, rid)

    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=123, plant_id=pid, qty=3))
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pat, did)
        card_id = d.json()["remedy_card_id"]
        _brew_remedy(c, cell_id, card_id)

    s2 = TestingSessionLocal()
    try:
        inv = s2.query(Inventory).filter(Inventory.user_id == 123, Inventory.plant_id == pid).first()
        assert inv.qty == 1
    finally:
        s2.close()


def test_brew_insufficient_plants_400(admin_client):
    from models import Inventory
    pid = next(p["id"] for p in admin_client.get("/api/plants").json() if p["code"] == "jackobob")

    r = admin_client.post("/api/admin/remedies", json={
        "name": "Мазь травяная",
        "recipe_items": [{"plant_id": pid, "qty": 2}],
    })
    rid = r.json()["id"]
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pat, _ = _seed_patient("Лис", did, 1)
    cell_id = _seed_device(admin_client, lab, rid)

    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=123, plant_id=pid, qty=1))
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pat, did)
        card_id = d.json()["remedy_card_id"]
        c.post(f"/api/remedy-lab/cells/{cell_id}/install")
        c.post("/api/stitches/reports", data={
            "amount": "100000", "context_type": "remedy_device_install", "context_id": str(cell_id),
        }, files=[("photo_after", ("a.png", _img_bytes(), "image/png"))])
        res = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert res.status_code == 400
        assert "Недостаточно" in res.json()["detail"]


def test_two_players_heal_same_patient_independently(admin_client):
    """Животное — общее из админки; состояние лечения — персональное у каждого игрока."""
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Кашель", rid)
    pid, scenes = _seed_patient("Лис", did, 1)
    inf = scenes["sick"]
    _seed_user_ingredient(1001, ing, 5)
    _seed_user_ingredient(1002, ing, 5)
    lab = _seed_field("remedy_lab", "Лаборатория")
    cell_id = _seed_device(admin_client, lab, rid)

    with make_user_client(1001, "player") as c1:
        assert c1.get(f"/api/infirmary/{inf}").json()["status"] == "sick"
        d = _diagnose(c1, pid, did)
        _brew_remedy(c1, cell_id, d.json()["remedy_card_id"])
        assert c1.post(f"/api/infirmary/patients/{pid}/give-remedy").status_code == 200
        assert c1.post(f"/api/infirmary/patients/{pid}/release").status_code == 200
        assert c1.get(f"/api/infirmary/{inf}").json()["status"] == "released"

    with make_user_client(1002, "player") as c2:
        assert c2.get(f"/api/infirmary/{inf}").json()["status"] == "sick"
        d = _diagnose(c2, pid, did)
        assert d.status_code == 200
        _brew_remedy(c2, cell_id, d.json()["remedy_card_id"])
        assert c2.post(f"/api/infirmary/patients/{pid}/give-remedy").status_code == 200
        assert c2.post(f"/api/infirmary/patients/{pid}/release").status_code == 200
        assert c2.get(f"/api/infirmary/{inf}").json()["status"] == "released"

    # Животное не удаляется из админки.
    patients = admin_client.get("/api/admin/patients").json()
    assert any(p["id"] == pid for p in patients)


def test_remedy_card_ingredients_show_have(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 3)])
    did = _seed_disease("Хворь", rid)
    pid, scenes = _seed_patient("Лис", did, 1)
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория", "cols": 3, "rows": 2, "field_kind": "remedy_lab",
    }).json()
    _seed_user_ingredient(123, ing, 2)

    with make_user_client(123, "player") as c:
        assert c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did}).status_code == 200
        data = c.get(f"/api/remedy-lab/{lab['id']}").json()
        card = data["remedy_cards"][0]
        item = card["recipe_items"][0]
        assert item["have"] == 2
        assert item["qty"] == 3
        assert item["ingredient_id"] == ing


def test_admin_field_detail_and_cleanup_remedy_lab(admin_client):
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория-деталь", "cols": 3, "rows": 2, "field_kind": "remedy_lab",
    }).json()
    fid = lab["id"]
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 3)])
    _seed_device(admin_client, fid, rid)

    detail = admin_client.get(f"/api/admin/fields/{fid}")
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["device_cells"]) == 1

    r = admin_client.post(f"/api/admin/fields/{fid}/cleanup")
    assert r.status_code == 200, r.text
    assert len(r.json()["device_cells"]) == 1


def test_remedy_lab_book_zone(admin_client):
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория-книга", "cols": 4, "rows": 3, "field_kind": "remedy_lab",
    }).json()
    fid = lab["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/infirmary-zones", json={
        "zone_kind": "book", "col1": 0, "row1": 0, "col2": 1, "row2": 0,
    })
    assert r.status_code == 201, r.text
    zid = r.json()["id"]

    detail = admin_client.get(f"/api/admin/fields/{fid}")
    assert any(z["id"] == zid for z in detail.json()["infirmary_zones"])

    with make_user_client(123, "player") as c:
        data = c.get(f"/api/remedy-lab/{fid}").json()
    assert any(z["id"] == zid and z["zone_kind"] == "book" for z in data["infirmary_zones"])


def test_book_zone_rejected_on_other_field_kind(admin_client):
    f = admin_client.post("/api/admin/fields", json={
        "name": "Поле-не-лаборатория", "cols": 3, "rows": 2, "field_kind": "meadow",
    }).json()
    rr = admin_client.post(f"/api/admin/fields/{f['id']}/infirmary-zones", json={
        "zone_kind": "book", "col1": 0, "row1": 0, "col2": 0, "row2": 0,
    })
    assert rr.status_code == 400
    assert "книги" in rr.json()["detail"]


def test_device_zone_multicell_marks_cells_and_shows_in_player(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория-зона", "cols": 4, "rows": 3, "field_kind": "remedy_lab",
    }).json()
    fid = lab["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/remedy-device-cells", json={
        "col1": 1, "row1": 1, "col2": 2, "row2": 2, "install_cards": 3, "remedy_ids": [rid],
    })
    assert r.status_code == 201, r.text
    dev = r.json()
    assert (dev["col1"], dev["row1"], dev["col2"], dev["row2"]) == (1, 1, 2, 2)
    assert dev["install_cards"] == 3

    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    kinds = {(c["col"], c["row"]): c["kind"] for c in detail["cells"]}
    for c in range(1, 3):
        for rr in range(1, 3):
            assert kinds[(c, rr)] == "remedy_device"

    with make_user_client(123, "player") as c:
        data = c.get(f"/api/remedy-lab/{fid}").json()
    assert len(data["device_cells"]) == 1
    assert (data["device_cells"][0]["col1"], data["device_cells"][0]["col2"]) == (1, 2)
    assert (data["device_cells"][0]["row1"], data["device_cells"][0]["row2"]) == (1, 2)


def test_device_zone_overlap_409(admin_client):
    rid = _seed_remedy("Мазь", [])
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория-пересечение", "cols": 4, "rows": 3, "field_kind": "remedy_lab",
    }).json()
    fid = lab["id"]
    ok = admin_client.post(f"/api/admin/fields/{fid}/remedy-device-cells", json={
        "col1": 0, "row1": 0, "col2": 2, "row2": 1, "install_cards": 1, "remedy_ids": [rid],
    })
    assert ok.status_code == 201
    over = admin_client.post(f"/api/admin/fields/{fid}/remedy-device-cells", json={
        "col1": 2, "row1": 1, "col2": 3, "row2": 2, "install_cards": 1, "remedy_ids": [rid],
    })
    assert over.status_code == 409
    assert "пересекается" in over.json()["detail"]


def test_device_zone_outside_field_400(admin_client):
    rid = _seed_remedy("Мазь", [])
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория-граница", "cols": 3, "rows": 2, "field_kind": "remedy_lab",
    }).json()
    fid = lab["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/remedy-device-cells", json={
        "col1": 2, "row1": 0, "col2": 3, "row2": 1, "install_cards": 1, "remedy_ids": [rid],
    })
    assert r.status_code == 400
    assert "пределы" in r.json()["detail"]


def test_device_zone_delete_resets_cells(admin_client):
    rid = _seed_remedy("Мазь", [])
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория-удаление", "cols": 4, "rows": 3, "field_kind": "remedy_lab",
    }).json()
    fid = lab["id"]
    dev = admin_client.post(f"/api/admin/fields/{fid}/remedy-device-cells", json={
        "col1": 0, "row1": 0, "col2": 1, "row2": 1, "install_cards": 1, "remedy_ids": [rid],
    }).json()

    r = admin_client.delete(f"/api/admin/fields/{fid}/remedy-device-cells/{dev['id']}")
    assert r.status_code == 204

    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert len(detail["device_cells"]) == 0
    kinds = {(c["col"], c["row"]): c["kind"] for c in detail["cells"]}
    for c in range(0, 2):
        for rr in range(0, 2):
            assert kinds[(c, rr)] == "empty"


def _upload_device_image(c, fid: int, cell_id: int):
    return c.put(
        f"/api/admin/fields/{fid}/remedy-device-cells/{cell_id}/image",
        files={"image": ("d.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def test_device_image_upload_and_show_in_player(admin_client, uploads_tmp):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    fid = _seed_field("remedy_lab", "Лаборатория-картинка")
    cell_id = _seed_device(admin_client, fid, rid)

    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert detail["device_cells"][0]["image_url"] is None

    r = _upload_device_image(admin_client, fid, cell_id)
    assert r.status_code == 200, r.text
    url = r.json()["image_url"]
    assert url.startswith("/api/uploads/remedy_device_")
    assert os.path.isfile(os.path.join(uploads_tmp, url.rsplit("/", 1)[-1]))

    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert detail["device_cells"][0]["image_url"] == url

    with make_user_client(123, "player") as c:
        data = c.get(f"/api/remedy-lab/{fid}").json()
    assert data["device_cells"][0]["image_url"] == url


def test_device_image_upload_404(admin_client, uploads_tmp):
    fid = _seed_field("remedy_lab", "Лаборатория-404")
    r = _upload_device_image(admin_client, fid, 99999)
    assert r.status_code == 404


def test_device_image_upload_requires_admin(player_client):
    r = player_client.put(
        "/api/admin/fields/1/remedy-device-cells/1/image",
        files={"image": ("d.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 403


def test_device_image_replace_removes_old_file(admin_client, uploads_tmp):
    rid = _seed_remedy("Мазь", [])
    fid = _seed_field("remedy_lab", "Лаборатория-замена")
    cell_id = _seed_device(admin_client, fid, rid)

    first = _upload_device_image(admin_client, fid, cell_id).json()["image_url"]
    second = _upload_device_image(admin_client, fid, cell_id).json()["image_url"]
    assert first != second
    assert not os.path.isfile(os.path.join(uploads_tmp, first.rsplit("/", 1)[-1]))
    assert os.path.isfile(os.path.join(uploads_tmp, second.rsplit("/", 1)[-1]))


def test_device_delete_removes_image_file(admin_client, uploads_tmp):
    rid = _seed_remedy("Мазь", [])
    fid = _seed_field("remedy_lab", "Лаборатория-удаление-картинки")
    cell_id = _seed_device(admin_client, fid, rid)
    url = _upload_device_image(admin_client, fid, cell_id).json()["image_url"]
    name = url.rsplit("/", 1)[-1]
    assert os.path.isfile(os.path.join(uploads_tmp, name))

    r = admin_client.delete(f"/api/admin/fields/{fid}/remedy-device-cells/{cell_id}")
    assert r.status_code == 204
    assert not os.path.isfile(os.path.join(uploads_tmp, name))
