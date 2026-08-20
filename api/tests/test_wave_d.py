import io

from tests.conftest import TestingSessionLocal, make_user_client
from tests.test_phase11_infirmary import (
    _brew_remedy, _img_bytes, _seed_disease, _seed_ingredient, _seed_lab_device,
    _seed_patient, _seed_part_cell, _seed_remedy, _seed_user_ingredient,
)


def _report(c, amount, context_type, context_id):
    r = c.post("/api/stitches/reports", data={
        "amount": str(amount),
        "context_type": context_type,
        "context_id": str(context_id),
    }, files=[("photo_after", ("a.png", _img_bytes(), "image/png"))])
    assert r.status_code in (200, 201), r.text


def _seed_otter_pet(cell_kind_pet=True):
    from models import Field, FieldCell, Pet
    s = TestingSessionLocal()
    try:
        pet = Pet(code="vydra", name="Выдра", emoji="🦦")
        s.add(pet)
        cell_id = None
        if cell_kind_pet:
            lawn = Field(code="lawn_test", name="Лужайка питомцев", cols=3, rows=2,
                         field_kind="lawn", min_level=0)
            s.add(lawn)
            s.flush()
            cell = FieldCell(field_id=lawn.id, col=0, row=0, kind="pet")
            s.add(cell)
            s.flush()
            cell_id = cell.id
        s.commit()
        s.refresh(pet)
        return pet.id, cell_id
    finally:
        s.close()


def _seed_meadow_with_ingredient(name="Роса"):
    from models import Field, FieldCell, GatherCell, GatherCellIngredient, Ingredient
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "ingredient"), Ingredient, s)
        ing = Ingredient(code=code, name=name)
        s.add(ing)
        f = Field(code="meadow_wave_d", name="Лесная поляна", cols=3, rows=2,
                  field_kind="meadow", min_level=0)
        s.add(f)
        s.flush()
        gc = GatherCell(field_id=f.id, col=0, row=0, window="always")
        s.add(gc)
        s.flush()
        s.add(GatherCellIngredient(gather_cell_id=gc.id, ingredient_id=ing.id))
        s.add(FieldCell(field_id=f.id, col=0, row=0, kind="gather"))
        s.commit()
        s.refresh(ing)
        return ing.id
    finally:
        s.close()


# ── W-7a: штрафы-долг за осмотр ──

def test_examine_first_free_repeat_adds_debt(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Хворь", rid, {"nose": "Текёт нос"})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_part_cell(scenes["treating"], 0, 0, "nose")
    _seed_part_cell(scenes["treating"], 1, 0, "ear")

    with make_user_client(123, "player") as c:
        r1 = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        assert r1.status_code == 200
        assert r1.json()["first_time"] is True
        assert r1.json()["penalty_due"] == 0

        r2 = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        assert r2.status_code == 200
        assert r2.json()["first_time"] is False
        assert r2.json()["penalty_due"] == 100

        r3 = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        assert r3.json()["penalty_due"] == 200

        r4 = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "ear"})
        assert r4.json()["first_time"] is True
        assert r4.json()["penalty_due"] == 200

        detail = c.get(f"/api/infirmary/{scenes['treating']}").json()
        assert detail["penalty_due"] == 200
        assert set(detail["examined_parts"]) == {"nose", "ear"}


def test_debt_blocks_diagnose_until_paid_by_report(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Хворь", rid, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_part_cell(scenes["treating"], 0, 0, "nose")

    with make_user_client(123, "player") as c:
        c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        assert c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"}).json()["penalty_due"] == 200

        blocked = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert blocked.status_code == 400

        _report(c, 150, "infirmary_penalty", pid)
        detail = c.get(f"/api/infirmary/{scenes['treating']}").json()
        assert detail["penalty_due"] == 50

        _report(c, 90, "infirmary_penalty", pid)
        detail = c.get(f"/api/infirmary/{scenes['treating']}").json()
        assert detail["penalty_due"] == 0

        ok = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert ok.status_code == 200


# ── W-5b: приборы Лесной аптеки ──

def test_admin_remedy_device_cells_crud_and_limits(admin_client):
    rid = _seed_remedy("Мазь", [])
    lab, cell_id = _seed_lab_device(admin_client, rid)
    assert cell_id > 0

    dup = admin_client.post(f"/api/admin/fields/{lab}/remedy-device-cells", json={
        "col": 0, "row": 0, "install_cards": 5, "remedy_ids": [rid],
    })
    assert dup.status_code == 409

    for pos in range(1, 5):
        r = admin_client.post(f"/api/admin/fields/{lab}/remedy-device-cells", json={
            "col": pos, "row": 0, "install_cards": 5, "remedy_ids": [rid],
        })
        assert r.status_code == 201

    over = admin_client.post(f"/api/admin/fields/{lab}/remedy-device-cells", json={
        "col": 0, "row": 1, "install_cards": 5, "remedy_ids": [rid],
    })
    assert over.status_code == 409

    wrong_field = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 3, "rows": 2})
    wrong = admin_client.post(f"/api/admin/fields/{wrong_field.json()['id']}/remedy-device-cells", json={
        "col": 0, "row": 0, "install_cards": 5, "remedy_ids": [],
    })
    assert wrong.status_code == 400


def test_brew_requires_built_device_and_allowed_remedy(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    rid2 = _seed_remedy("Другая мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {})
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing, 5)
    lab, cell_id = _seed_lab_device(admin_client, rid)

    with make_user_client(123, "player") as c:
        d = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        card_id = d.json()["remedy_card_id"]

        r = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert r.status_code == 400

        install = c.post(f"/api/remedy-lab/cells/{cell_id}/install")
        assert install.status_code == 200
        assert install.json()["device"]["build_status"] == "building"

        lab_view = c.get(f"/api/remedy-lab/{lab}").json()
        assert len(lab_view["device_cells"]) == 1
        assert lab_view["device_cells"][0]["remedies"][0]["remedy_id"] == rid

        _report(c, 100000, "remedy_device_install", cell_id)
        lab_view = c.get(f"/api/remedy-lab/{lab}").json()
        assert lab_view["device_cells"][0]["device"]["build_status"] == "built"

        r = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert r.status_code == 200
        dice = r.json()["dice"]
        assert len(dice) == 2 and all(1 <= d <= 6 for d in dice)
        assert r.json()["device"]["brew_required"] > 0

        state = None
        from models import UserPatientState
        s = TestingSessionLocal()
        try:
            state = s.query(UserPatientState).filter(
                UserPatientState.user_id == 123, UserPatientState.patient_id == pid
            ).first()
            st = state.status if state else None
        finally:
            s.close()
        assert st == "diagnosed"

        again = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert again.status_code == 409


def test_brew_wrong_device_rejected(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {})
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing, 5)
    _, cell_id = _seed_lab_device(admin_client, rid)

    lab2 = admin_client.post("/api/admin/fields", json={
        "name": "Аптека 2", "cols": 5, "rows": 3, "field_kind": "remedy_lab",
    }).json()["id"]
    cell2 = admin_client.post(f"/api/admin/fields/{lab2}/remedy-device-cells", json={
        "col": 0, "row": 0, "install_cards": 1, "remedy_ids": [],
    }).json()["id"]

    with make_user_client(123, "player") as c:
        d = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        card_id = d.json()["remedy_card_id"]
        r = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell2})
        assert r.status_code == 400
        assert "другом приборе" in r.json()["detail"]


def test_brew_insufficient_ingredients_400(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 2)])
    did = _seed_disease("Хворь", rid, {})
    pid, _ = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing, 1)
    _, cell_id = _seed_lab_device(admin_client, rid)

    with make_user_client(123, "player") as c:
        c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        lab_cards = c.get(f"/api/remedy-lab/{_lab_id(cell_id)}").json()["remedy_cards"]
        card_id = lab_cards[0]["id"]

        c.post(f"/api/remedy-lab/cells/{cell_id}/install")
        _report(c, 100000, "remedy_device_install", cell_id)
        r = c.post(f"/api/remedy-cards/{card_id}/brew", json={"cell_id": cell_id})
        assert r.status_code == 400
        assert "Недостаточно" in r.json()["detail"]


def _lab_id(cell_id):
    from models import RemedyDeviceCell
    s = TestingSessionLocal()
    try:
        cell = s.query(RemedyDeviceCell).filter(RemedyDeviceCell.id == cell_id).first()
        return cell.field_id
    finally:
        s.close()


# ── W-5c: дать лекарство ──

def test_give_remedy_full_chain_and_card_filter(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {"nose": "Горячий нос"})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing, 5)
    lab, cell_id = _seed_lab_device(admin_client, rid)

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/give-remedy")
        assert r.status_code == 400

        d = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        card_id = d.json()["remedy_card_id"]

        no_stock = c.post(f"/api/infirmary/patients/{pid}/give-remedy")
        assert no_stock.status_code == 400
        assert "аптеке" in no_stock.json()["detail"]

        _brew_remedy(c, cell_id, card_id)
        stock = c.get(f"/api/remedy-lab/{lab}").json()["remedies_stock"]
        assert stock and stock[0]["remedy_id"] == rid and stock[0]["qty"] == 1

        ok = c.post(f"/api/infirmary/patients/{pid}/give-remedy")
        assert ok.status_code == 200
        assert ok.json()["status"] == "treated"
        assert ok.json()["otter_granted"] is False

        repeat = c.post(f"/api/infirmary/patients/{pid}/give-remedy")
        assert repeat.status_code == 400

        cards = c.get(f"/api/remedy-lab/{lab}").json()["remedy_cards"]
        assert cards == []

        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 200


# ── W-5d: воспоминания ──

def test_hub_memories_healthy_images(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_user_ingredient(123, ing, 5)
    _, cell_id = _seed_lab_device(admin_client, rid)

    with make_user_client(123, "player") as c:
        hub = c.get("/api/infirmary").json()
        assert all(m["patient_id"] != pid for m in hub["memories"])
        assert hub["memories"] == []

        d = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        _brew_remedy(c, cell_id, d.json()["remedy_card_id"])
        c.post(f"/api/infirmary/patients/{pid}/give-remedy")

        hub = c.get("/api/infirmary").json()
        mem = next(m for m in hub["memories"] if m["patient_id"] == pid)
        assert mem["healed"] is True
        assert "healthy_image_url" in mem


# ── W-7b: выдра ──

def test_heal_otter_patient_grants_sixth_pet(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Простуда", rid, {})
    tid = None
    pid, scenes = _seed_patient("Выдра Поля", did, 1)
    pet_id, cell_id = _seed_otter_pet()
    _seed_user_ingredient(123, ing, 5)
    _, dev_cell = _seed_lab_device(admin_client, rid)

    with make_user_client(123, "player") as c:
        d = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        _brew_remedy(c, dev_cell, d.json()["remedy_card_id"])
        r = c.post(f"/api/infirmary/patients/{pid}/give-remedy")
        assert r.status_code == 200
        assert r.json()["otter_granted"] is True

        pets = c.get("/api/pets").json()
        otter = next((p for p in pets if p["pet_id"] == pet_id), None)
        assert otter is not None
        assert otter["cell_id"] == cell_id
        assert otter["code"] == "vydra"
        assert otter["forest"] is not None
        assert otter["forest"]["sleeping"] is False


def test_otter_forest_actions_daily_limits(admin_client):
    ing_id = _seed_meadow_with_ingredient("Роса")
    pet_id, cell_id = _seed_otter_pet()

    from models import User, UserPet
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 123).first()
        if u is None:
            u = User(vk_id=123, role="player")
            s.add(u)
        s.add(UserPet(user_id=123, pet_id=pet_id, cell_id=cell_id))
        u.crosses_balance = 1000
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        paid_first = c.post(f"/api/pets/{pet_id}/forest", json={"paid": True})
        assert paid_first.status_code == 400

        r1 = c.post(f"/api/pets/{pet_id}/forest", json={"paid": False})
        assert r1.status_code == 200
        assert r1.json()["ingredient_id"] == ing_id
        assert r1.json()["apothecary_qty"] == 1
        assert r1.json()["sleeping"] is False

        free_again = c.post(f"/api/pets/{pet_id}/forest", json={"paid": False})
        assert free_again.status_code == 429

        r2 = c.post(f"/api/pets/{pet_id}/forest", json={"paid": True})
        assert r2.status_code == 200
        assert r2.json()["apothecary_qty"] == 2
        assert r2.json()["sleeping"] is True
        assert r2.json()["wake_at"] is not None

        sleeping = c.post(f"/api/pets/{pet_id}/forest", json={"paid": False})
        assert sleeping.status_code == 429

        pets = c.get("/api/pets").json()
        otter = next(p for p in pets if p["pet_id"] == pet_id)
        assert otter["forest"]["sleeping"] is True


def test_otter_paid_requires_crosses(admin_client):
    _seed_meadow_with_ingredient("Роса")
    pet_id, cell_id = _seed_otter_pet()

    from models import User, UserPet
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 123).first()
        if u is None:
            u = User(vk_id=123, role="player")
            s.add(u)
        s.add(UserPet(user_id=123, pet_id=pet_id, cell_id=cell_id))
        u.crosses_balance = 10
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        c.post(f"/api/pets/{pet_id}/forest", json={"paid": False})
        r = c.post(f"/api/pets/{pet_id}/forest", json={"paid": True})
        assert r.status_code == 400


def test_forest_denied_for_regular_pet(admin_client):
    from models import Pet, User, UserPet
    s = TestingSessionLocal()
    try:
        pet = Pet(code="fox_wave_d", name="Лис", emoji="🦊")
        s.add(pet)
        s.flush()
        u = s.query(User).filter(User.vk_id == 123).first()
        if u is None:
            u = User(vk_id=123, role="player")
            s.add(u)
        s.add(UserPet(user_id=123, pet_id=pet.id))
        s.commit()
        pet_id = pet.id
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/pets/{pet_id}/forest", json={"paid": False})
        assert r.status_code == 400


# ── Бэкфилл выдры для игроков, вылечивших выдру до внедрения ──

def _seed_lawn_pet_cell():
    from models import Field, FieldCell
    s = TestingSessionLocal()
    try:
        lawn = Field(code="lawn_backfill", name="Лужайка питомцев", cols=3, rows=2,
                     field_kind="lawn", min_level=0)
        s.add(lawn)
        s.flush()
        cell = FieldCell(field_id=lawn.id, col=0, row=0, kind="pet")
        s.add(cell)
        s.commit()
        s.refresh(cell)
        return cell.id
    finally:
        s.close()


def _seed_released_state(vk_id: int, patient_id: int):
    from models import UserPatientState
    s = TestingSessionLocal()
    try:
        s.add(UserPatientState(user_id=vk_id, patient_id=patient_id, status="released"))
        s.commit()
    finally:
        s.close()


def _seed_otter_patient() -> int:
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Простуда", rid, {})
    pid, _ = _seed_patient("Выдра Поля", did, 1)
    return pid


def test_backfill_grants_otter_to_released_players(admin_client):
    from routes.pets import backfill_forest_pets
    pid = _seed_otter_patient()
    cell_id = _seed_lawn_pet_cell()

    with make_user_client(123, "player") as c:
        c.get("/api/me")
    _seed_released_state(123, pid)

    s = TestingSessionLocal()
    try:
        granted = backfill_forest_pets(s)
        s.commit()
    finally:
        s.close()
    assert granted == 1

    from models import Pet, User, UserPet
    s = TestingSessionLocal()
    try:
        pet = s.query(Pet).filter(Pet.code == "vydra").first()
        assert pet is not None
        up = s.query(UserPet).filter(UserPet.user_id == 123, UserPet.pet_id == pet.id).first()
        assert up is not None
        assert up.cell_id == cell_id
        u = s.query(User).filter(User.vk_id == 123).first()
        assert u.unlocked_pets >= 6
    finally:
        s.close()


def test_backfill_skips_players_who_did_not_heal_otter(admin_client):
    from routes.pets import backfill_forest_pets
    pid = _seed_otter_patient()
    _seed_lawn_pet_cell()

    with make_user_client(123, "player") as c:
        c.get("/api/me")
    from models import UserPatientState
    s = TestingSessionLocal()
    try:
        s.add(UserPatientState(user_id=123, patient_id=pid, status="sick"))
        s.commit()
        granted = backfill_forest_pets(s)
        s.commit()
    finally:
        s.close()
    assert granted == 0


def test_backfill_does_not_duplicate_otter(admin_client):
    from routes.pets import backfill_forest_pets
    pid = _seed_otter_patient()
    pet_id, cell_id = _seed_otter_pet()

    with make_user_client(123, "player") as c:
        c.get("/api/me")
    _seed_released_state(123, pid)

    from models import UserPet
    s = TestingSessionLocal()
    try:
        s.add(UserPet(user_id=123, pet_id=pet_id, cell_id=cell_id))
        s.commit()
        granted = backfill_forest_pets(s)
        s.commit()
    finally:
        s.close()
    assert granted == 0


def test_list_pets_backfills_otter(admin_client):
    pid = _seed_otter_patient()
    cell_id = _seed_lawn_pet_cell()

    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _seed_released_state(123, pid)
        pets = c.get("/api/pets").json()
        otter = next((p for p in pets if p["code"] == "vydra"), None)
        assert otter is not None
        assert otter["cell_id"] == cell_id
        assert otter["forest"] is not None


def test_grant_forest_pet_creates_otter_when_catalog_missing(admin_client):
    from routes.pets import grant_forest_pet_if_absent
    _seed_lawn_pet_cell()

    with make_user_client(123, "player") as c:
        c.get("/api/me")

    s = TestingSessionLocal()
    try:
        granted = grant_forest_pet_if_absent(123, s)
        s.commit()
    finally:
        s.close()
    assert granted is True

    from models import Pet, UserPet
    s = TestingSessionLocal()
    try:
        pet = s.query(Pet).filter(Pet.code == "vydra").first()
        assert pet is not None
        assert s.query(UserPet).filter(UserPet.user_id == 123, UserPet.pet_id == pet.id).first() is not None
    finally:
        s.close()
