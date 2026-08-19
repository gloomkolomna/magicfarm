import io

from tests.conftest import TestingSessionLocal, make_user_client


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


def _seed_disease(name: str, remedy_id: int, symptoms: dict[str, str]) -> int:
    from models import Disease, DiseaseSymptom
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "disease"), Disease, s)
        d = Disease(code=code, name=name, remedy_id=remedy_id)
        s.add(d)
        s.flush()
        for part_code, text in symptoms.items():
            s.add(DiseaseSymptom(disease_id=d.id, part_code=part_code, text=text))
        s.commit()
        s.refresh(d)
        return d.id
    finally:
        s.close()


def _seed_infirmary_field(name: str = "Лесная лечебница", level: int = 0) -> int:
    from models import Field
    from routes.admin_fields import _make_code
    s = TestingSessionLocal()
    try:
        code = _make_code(name, s)
        f = Field(code=code, name=name, cols=3, rows=2,
                  field_kind="infirmary", min_level=level)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id
    finally:
        s.close()


def _seed_patient(name: str, disease_id: int, level: int, field_id: int | None) -> int:
    from models import PatientAnimal
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "patient"), PatientAnimal, s)
        p = PatientAnimal(code=code, name=name, level=level, disease_id=disease_id, field_id=field_id)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id
    finally:
        s.close()


def _seed_part_cell(field_id: int, animal_id: int, col: int, row: int, part_code: str) -> int:
    from models import ClinicPartCell, FieldCell
    s = TestingSessionLocal()
    try:
        pc = ClinicPartCell(field_id=field_id, animal_id=animal_id, col=col, row=row, part_code=part_code)
        s.add(pc)
        s.add(FieldCell(field_id=field_id, col=col, row=row, kind="body_part"))
        s.commit()
        s.refresh(pc)
        return pc.id
    finally:
        s.close()


def _set_crosses(vk_id: int, amount: int) -> None:
    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        if u is None:
            u = User(vk_id=vk_id, role="player", crosses_balance=amount)
            s.add(u)
        else:
            u.crosses_balance = amount
        s.commit()
    finally:
        s.close()


def test_admin_create_remedy_generates_code(admin_client):
    ing = _seed_ingredient("Роса")
    r = admin_client.post("/api/admin/remedies", json={
        "name": "Мазь от кашля", "recipe_items": [{"ingredient_id": ing, "qty": 3}],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["code"]
    assert len(data["recipe_items"]) == 1
    assert data["recipe_items"][0]["ingredient_id"] == ing
    assert data["recipe_items"][0]["qty"] == 3


def test_admin_create_remedy_requires_name(admin_client):
    assert admin_client.post("/api/admin/remedies", json={"name": "  "}).status_code == 400


def test_admin_create_remedy_with_plant_source(admin_client):
    ing = _seed_ingredient("Роса")
    pid = next(p["id"] for p in admin_client.get("/api/plants").json() if p["code"] == "jackobob")
    r = admin_client.post("/api/admin/remedies", json={
        "name": "Мазь травяная",
        "recipe_items": [
            {"ingredient_id": ing, "qty": 2},
            {"plant_id": pid, "qty": 3},
        ],
    })
    assert r.status_code == 201
    data = r.json()
    items = {(i["ingredient_id"], i["plant_id"]): i for i in data["recipe_items"]}
    assert (ing, None) in items
    assert (None, pid) in items
    assert items[(None, pid)]["plant_name"] == "Джекобоб"


def test_admin_create_remedy_requires_single_source(admin_client):
    ing = _seed_ingredient("Роса")
    r = admin_client.post("/api/admin/remedies", json={
        "name": "Мазь", "recipe_items": [{"ingredient_id": ing, "qty": 1, "plant_id": None}, {"qty": 1}],
    })
    assert r.status_code == 400


def test_admin_update_remedy(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    r = admin_client.put(f"/api/admin/remedies/{rid}", json={"name": "Бальзам", "recipe_items": []})
    assert r.status_code == 200
    assert r.json()["name"] == "Бальзам"
    assert r.json()["recipe_items"] == []


def test_admin_delete_remedy(admin_client):
    rid = _seed_remedy("Мазь", [])
    assert admin_client.delete(f"/api/admin/remedies/{rid}").status_code == 204
    assert all(r["id"] != rid for r in admin_client.get("/api/admin/remedies").json())


def test_admin_create_disease_with_symptoms(admin_client):
    rid = _seed_remedy("Мазь", [])
    r = admin_client.post("/api/admin/diseases", json={
        "name": "Лесная лихорадка", "remedy_id": rid,
        "symptoms": [{"part_code": "nose", "text": "Горячий нос"}],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["code"]
    assert data["remedy_id"] == rid
    assert data["symptoms"][0]["part_code"] == "nose"


def test_admin_create_patient_level_validation(admin_client):
    did = _seed_disease("Хворь", None, {})
    r = admin_client.post("/api/admin/patients", json={"name": "Лис", "level": 5, "disease_id": did})
    assert r.status_code == 400


def test_admin_create_patient_unknown_field_400(admin_client):
    did = _seed_disease("Хворь", None, {})
    r = admin_client.post("/api/admin/patients", json={"name": "Лис", "level": 1, "disease_id": did, "field_id": 9999})
    assert r.status_code == 400


def test_admin_create_patient_non_infirmary_field_400(admin_client):
    did = _seed_disease("Хворь", None, {})
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Грядки", "cols": 3, "rows": 2, "field_kind": "garden_beds"}
    ).json()["id"]
    r = admin_client.post("/api/admin/patients", json={"name": "Лис", "level": 1, "disease_id": did, "field_id": fid})
    assert r.status_code == 400


def test_admin_create_patient_ok_infirmary_field(admin_client):
    did = _seed_disease("Хворь", None, {})
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Лечебница", "cols": 3, "rows": 2, "field_kind": "infirmary"}
    ).json()["id"]
    r = admin_client.post("/api/admin/patients", json={"name": "Лис", "level": 1, "disease_id": did, "field_id": fid})
    assert r.status_code == 201
    assert r.json()["field_id"] == fid


def test_part_cell_requires_patient(admin_client):
    fid = _seed_infirmary_field()
    r = admin_client.post(f"/api/admin/fields/{fid}/part-cells", json={"col": 0, "row": 0, "part_code": "nose"})
    assert r.status_code == 400


def test_admin_part_cell_crud(admin_client):
    fid = _seed_infirmary_field()
    did = _seed_disease("Хворь", None, {})
    pid = _seed_patient("Лис", did, 1, fid)
    r = admin_client.post(f"/api/admin/fields/{fid}/part-cells", json={"col": 0, "row": 0, "part_code": "nose"})
    assert r.status_code == 201
    pc = r.json()
    assert pc["animal_id"] == pid
    assert pc["part_code"] == "nose"
    r2 = admin_client.put(f"/api/admin/fields/{fid}/part-cells/{pc['id']}", json={"part_code": "ear"})
    assert r2.status_code == 200
    assert r2.json()["part_code"] == "ear"
    assert admin_client.delete(f"/api/admin/fields/{fid}/part-cells/{pc['id']}").status_code == 204


def test_player_forbidden_on_admin_infirmary(player_client):
    with make_user_client(123, "player") as c:
        assert c.get("/api/admin/remedies").status_code == 403
        assert c.get("/api/admin/diseases").status_code == 403
        assert c.get("/api/admin/patients").status_code == 403
        assert c.post("/api/admin/remedies", json={"name": "X"}).status_code == 403


def test_infirmary_list_levels_unlocked_progression(admin_client):
    did = _seed_disease("Хворь", None, {})
    fid1 = _seed_infirmary_field()
    fid2 = _seed_infirmary_field()
    _seed_patient("Лис 1", did, 1, fid1)
    _seed_patient("Сова 2", did, 2, fid2)
    with make_user_client(123, "player") as c:
        r = c.get("/api/infirmary")
        assert r.status_code == 200
        levels = r.json()["levels"]
        l1 = next(x for x in levels if x["level"] == 1)
        l2 = next(x for x in levels if x["level"] == 2)
        assert l1["unlocked"] is True
        assert l2["unlocked"] is False


def test_infirmary_detail(admin_client):
    did = _seed_disease("Хворь", None, {"nose": "Горячий нос"})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    _seed_part_cell(fid, pid, 0, 0, "nose")
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/infirmary/{fid}")
        assert r.status_code == 200
        data = r.json()
        assert data["patient_id"] == pid
        assert len(data["part_cells"]) == 1
        assert data["part_cells"][0]["part_code"] == "nose"


def test_infirmary_wrong_field_kind(admin_client):
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="beds_x", name="Грядки", cols=2, rows=1, field_kind="garden_beds")
        s.add(f)
        s.commit()
        s.refresh(f)
        fid = f.id
    finally:
        s.close()
    with make_user_client(123, "player") as c:
        assert c.get(f"/api/infirmary/{fid}").status_code == 400


def test_handbook(admin_client):
    rid = _seed_remedy("Мазь от кашля", [])
    _seed_disease("Кашель", rid, {"chest": "Хрипы"})
    with make_user_client(123, "player") as c:
        r = c.get("/api/infirmary/handbook")
        assert r.status_code == 200
        diseases = r.json()["diseases"]
        assert len(diseases) >= 1
        d = next(x for x in diseases if x["name"] == "Кашель")
        assert d["remedy_id"] == rid
        assert d["symptoms"][0]["text"] == "Хрипы"


def test_examine_returns_symptoms(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Хворь", rid, {"nose": "Горячий нос", "ear": "Чешется ухо"})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    _seed_part_cell(fid, pid, 0, 0, "nose")
    _seed_part_cell(fid, pid, 1, 0, "ear")
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        assert r.status_code == 200
        assert r.json()["symptoms"] == ["Горячий нос"]


def test_examine_unknown_part_400(admin_client):
    did = _seed_disease("Хворь", None, {"nose": "Горячий нос"})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    _seed_part_cell(fid, pid, 0, 0, "nose")
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "tail"})
        assert r.status_code == 400


def test_diagnose_correct_gives_card(admin_client):
    rid = _seed_remedy("Мазь от кашля", [])
    did = _seed_disease("Кашель", rid, {"chest": "Хрипы"})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert r.status_code == 200
        data = r.json()
        assert data["correct"] is True
        assert data["remedy_card_id"]
        assert data["remedy_id"] == rid


def test_diagnose_wrong_deducts_200(admin_client):
    did = _seed_disease("Кашель", None, {})
    other = _seed_disease("Хромота", None, {})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    _set_crosses(123, 500)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": other})
        assert r.status_code == 200
        assert r.json()["correct"] is False
        assert r.json()["crosses_balance"] == 300


def test_diagnose_wrong_blocked_when_balance_low(admin_client):
    did = _seed_disease("Кашель", None, {})
    other = _seed_disease("Хромота", None, {})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    _set_crosses(123, 100)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": other})
        assert r.status_code == 400


def test_diagnose_repeat_after_correct_400(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Кашель", rid, {})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    with make_user_client(123, "player") as c:
        assert c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did}).status_code == 200
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert r.status_code == 400


def test_infirmary_requires_auth(client):
    assert client.get("/api/infirmary").status_code == 401
    assert client.get("/api/infirmary/handbook").status_code == 401
    assert client.post("/api/infirmary/patients/1/examine", json={"part_code": "nose"}).status_code == 401
    assert client.post("/api/infirmary/patients/1/diagnose", json={"disease_id": 1}).status_code == 401


# ── Зоны лечебницы ──

def test_admin_infirmary_zone_crud(admin_client):
    fid = _seed_infirmary_field()
    r = admin_client.post(f"/api/admin/fields/{fid}/infirmary-zones", json={
        "zone_kind": "animal", "col1": 0, "row1": 0, "col2": 1, "row2": 1,
    })
    assert r.status_code == 201
    z = r.json()
    assert z["zone_kind"] == "animal"
    assert (z["col1"], z["row1"], z["col2"], z["row2"]) == (0, 0, 1, 1)

    # Пересечение с другой зоной → 409.
    r2 = admin_client.post(f"/api/admin/fields/{fid}/infirmary-zones", json={
        "zone_kind": "book", "col1": 1, "row1": 1, "col2": 2, "row2": 1,
    })
    assert r2.status_code == 409

    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert len(detail["infirmary_zones"]) == 1

    assert admin_client.delete(f"/api/admin/fields/{fid}/infirmary-zones/{z['id']}").status_code == 204


def test_admin_infirmary_zone_wrong_field_kind(admin_client):
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Грядки", "cols": 3, "rows": 2, "field_kind": "garden_beds"}
    ).json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/infirmary-zones", json={
        "zone_kind": "animal", "col1": 0, "row1": 0, "col2": 1, "row2": 1,
    })
    assert r.status_code == 400


# ── Картинки стадий пациента ──

def test_admin_upload_patient_stage_images(admin_client, uploads_tmp):
    did = _seed_disease("Хворь", None, {})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), (120, 90, 60)).save(buf, format="PNG")

    r = admin_client.put(
        f"/api/admin/patients/{pid}/hospital-image",
        files={"image": ("h.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["hospital_image_url"].startswith("/api/uploads/patient_hospital_")

    r2 = admin_client.put(
        f"/api/admin/patients/{pid}/healthy-image",
        files={"image": ("h.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert r2.status_code == 200
    assert r2.json()["healthy_image_url"].startswith("/api/uploads/patient_healthy_")


# ── Стадии пациента: sick → diagnosed → treated → released ──

def _seed_user_ingredient(vk_id: int, ingredient_id: int, qty: int) -> None:
    from models import UserIngredient
    s = TestingSessionLocal()
    try:
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=qty))
        s.commit()
    finally:
        s.close()


def test_infirmary_detail_status_progression(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {"nose": "Горячий нос"})
    fid = _seed_infirmary_field()
    pid = _seed_patient("Лис", did, 1, fid)
    _seed_part_cell(fid, pid, 0, 0, "nose")
    _seed_user_ingredient(123, ing, 5)

    with make_user_client(123, "player") as c:
        d = c.get(f"/api/infirmary/{fid}").json()
        assert d["status"] == "sick"

        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert r.status_code == 200
        d = c.get(f"/api/infirmary/{fid}").json()
        assert d["status"] == "diagnosed"
        assert d["disease_name"] == "Хворь"
        assert d["remedy_name"] == "Мазь"

        card_id = r.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200
        d = c.get(f"/api/infirmary/{fid}").json()
        assert d["status"] == "treated"

        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 200
        d = c.get(f"/api/infirmary/{fid}").json()
        assert d["status"] == "released"
        assert d["card_earned"] is True
