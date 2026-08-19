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


def _seed_clinic_animal_type(name: str = "Лис") -> int:
    from models import ClinicAnimalType
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "animal_type"), ClinicAnimalType, s)
        t = ClinicAnimalType(code=code, name=name)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t.id
    finally:
        s.close()


def _seed_patient(name: str, disease_id: int, level: int = 1, animal_type_id: int | None = None) -> tuple[int, dict[str, int]]:
    from models import Field, PatientAnimal
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "patient"), PatientAnimal, s)
        p = PatientAnimal(code=code, name=name, level=level,
                          disease_id=disease_id, animal_type_id=animal_type_id)
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


def _seed_part_cell(field_id: int, col: int, row: int, part_code: str) -> int:
    from models import ClinicPartCell, FieldCell
    s = TestingSessionLocal()
    try:
        pc = ClinicPartCell(field_id=field_id, col=col, row=row, part_code=part_code)
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


# ── Мази ──

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


# ── Болезни ──

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


# ── Типы животных ──

def test_admin_animal_type_crud(admin_client):
    r = admin_client.post("/api/admin/clinic-animal-types", json={"name": "Лис", "emoji": "🦊"})
    assert r.status_code == 201
    t = r.json()
    assert t["code"]
    assert t["name"] == "Лис"

    r2 = admin_client.put(f"/api/admin/clinic-animal-types/{t['id']}", json={"name": "Лисёнок"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Лисёнок"

    rows = admin_client.get("/api/admin/clinic-animal-types").json()
    assert any(x["id"] == t["id"] for x in rows)

    assert admin_client.delete(f"/api/admin/clinic-animal-types/{t['id']}").status_code == 204
    assert all(x["id"] != t["id"] for x in admin_client.get("/api/admin/clinic-animal-types").json())


def test_admin_animal_type_requires_name(admin_client):
    assert admin_client.post("/api/admin/clinic-animal-types", json={"name": "  "}).status_code == 400


# ── Животные лечебницы ──

def test_admin_create_patient_level_validation(admin_client):
    did = _seed_disease("Хворь", None, {})
    r = admin_client.post("/api/admin/patients", json={"name": "Лис", "level": 5, "disease_id": did})
    assert r.status_code == 400


def test_admin_create_patient_unknown_type_400(admin_client):
    did = _seed_disease("Хворь", None, {})
    r = admin_client.post("/api/admin/patients", json={"name": "Лис", "level": 1, "disease_id": did, "animal_type_id": 9999})
    assert r.status_code == 400


def test_admin_create_patient_creates_three_scenes(admin_client):
    did = _seed_disease("Хворь", None, {})
    tid = _seed_clinic_animal_type("Лис")
    r = admin_client.post("/api/admin/patients", json={
        "name": "Лис", "level": 1, "disease_id": did, "animal_type_id": tid,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["animal_type_name"] == "Лис"
    assert data["disease_id"] == did
    stages = {s["stage"]: s["field_id"] for s in data["scenes"]}
    assert set(stages) == {"sick", "treating", "healthy"}
    assert len({s["field_id"] for s in data["scenes"]}) == 3

    detail = admin_client.get(f"/api/admin/fields/{stages['sick']}").json()
    assert detail["field_kind"] == "infirmary"
    assert detail["name"].endswith("— больное")


def test_admin_update_patient_renames_scenes(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    r = admin_client.put(f"/api/admin/patients/{pid}", json={"name": "Лисёнок"})
    assert r.status_code == 200
    sick = admin_client.get(f"/api/admin/fields/{scenes['sick']}").json()
    assert "Лисёнок" in sick["name"]


def test_admin_delete_patient_removes_scenes(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    assert admin_client.delete(f"/api/admin/patients/{pid}").status_code == 204
    assert admin_client.get(f"/api/admin/fields/{scenes['sick']}").status_code == 404


# ── Части тела (размещение на сцене без пациента) ──

def test_part_cell_on_scene_without_extra_binding(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    sick = scenes["sick"]
    r = admin_client.post(f"/api/admin/fields/{sick}/part-cells", json={"col": 0, "row": 0, "part_code": "nose"})
    assert r.status_code == 201
    pc = r.json()
    assert pc["part_code"] == "nose"
    assert pc["field_id"] == sick
    assert "animal_id" not in pc


def test_admin_part_cell_crud(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    sick = scenes["sick"]
    r = admin_client.post(f"/api/admin/fields/{sick}/part-cells", json={"col": 0, "row": 0, "part_code": "nose"})
    assert r.status_code == 201
    pc = r.json()
    assert pc["part_code"] == "nose"
    r2 = admin_client.put(f"/api/admin/fields/{sick}/part-cells/{pc['id']}", json={"part_code": "ear"})
    assert r2.status_code == 200
    assert r2.json()["part_code"] == "ear"
    assert admin_client.delete(f"/api/admin/fields/{sick}/part-cells/{pc['id']}").status_code == 204


def test_admin_part_cell_duplicate_cell_409(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    sick = scenes["sick"]
    admin_client.post(f"/api/admin/fields/{sick}/part-cells", json={"col": 0, "row": 0, "part_code": "nose"})
    r = admin_client.post(f"/api/admin/fields/{sick}/part-cells", json={"col": 0, "row": 0, "part_code": "ear"})
    assert r.status_code == 409


def test_player_forbidden_on_admin_infirmary(player_client):
    with make_user_client(123, "player") as c:
        assert c.get("/api/admin/remedies").status_code == 403
        assert c.get("/api/admin/diseases").status_code == 403
        assert c.get("/api/admin/patients").status_code == 403
        assert c.get("/api/admin/clinic-animal-types").status_code == 403
        assert c.post("/api/admin/remedies", json={"name": "X"}).status_code == 403


# ── Хаб лечебницы ──

def test_infirmary_hub_current_and_locations(admin_client):
    did = _seed_disease("Хворь", None, {})
    tid = _seed_clinic_animal_type("Лис")
    r = admin_client.post("/api/admin/patients", json={
        "name": "Лис", "level": 1, "disease_id": did, "animal_type_id": tid,
    })
    assert r.status_code == 201
    pid = r.json()["id"]

    with make_user_client(123, "player") as c:
        hub = c.get("/api/infirmary").json()
        assert hub["current"]["id"] == pid
        assert hub["current"]["animal_type_name"] == "Лис"
        assert hub["current"]["status"] == "sick"
        stages = {s["stage"] for s in hub["current"]["scenes"]}
        assert stages == {"sick", "treating", "healthy"}

        l1 = next(x for x in hub["levels"] if x["level"] == 1)
        assert l1["unlocked"] is True
        assert l1["patients"][0]["id"] == pid


def test_infirmary_hub_infirmary_location_first(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    admin_client.post("/api/admin/fields", json={"name": "Поляна", "cols": 2, "rows": 1, "field_kind": "meadow"})
    admin_client.post("/api/admin/fields", json={"name": "Лавка", "cols": 2, "rows": 1, "field_kind": "shop"})

    with make_user_client(123, "player") as c:
        hub = c.get("/api/infirmary").json()
        kinds = [loc["field_kind"] for loc in hub["locations"]]
        assert kinds[0] == "infirmary"
        assert "meadow" in kinds
        assert "shop" in kinds


def test_infirmary_hub_after_release_shows_next(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {"nose": "Горячий нос"})
    pid1, _ = _seed_patient("Лис 1", did, 1)
    pid2, _ = _seed_patient("Сова 2", did, 1)
    _seed_user_ingredient(123, ing, 5)

    with make_user_client(123, "player") as c:
        assert c.get("/api/infirmary").json()["current"]["id"] == pid1
        d = c.post(f"/api/infirmary/patients/{pid1}/diagnose", json={"disease_id": did})
        card_id = d.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200
        assert c.post(f"/api/infirmary/patients/{pid1}/release").status_code == 200
        hub = c.get("/api/infirmary").json()
        assert hub["current"]["id"] == pid2


def test_infirmary_hub_remembers_last_scene(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    with make_user_client(123, "player") as c:
        assert c.get(f"/api/infirmary/{scenes['sick']}").status_code == 200
        hub = c.get("/api/infirmary").json()
        assert hub["current"]["current_field_id"] == scenes["sick"]

        assert c.get(f"/api/infirmary/{scenes['treating']}").status_code == 200
        hub = c.get("/api/infirmary").json()
        assert hub["current"]["status"] == "sick"
        assert hub["current"]["current_field_id"] == scenes["treating"]


# ── Детализация сцены ──

def test_infirmary_detail_scene(admin_client):
    did = _seed_disease("Хворь", None, {"nose": "Горячий нос"})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_part_cell(scenes["sick"], 0, 0, "nose")
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/infirmary/{scenes['sick']}")
        assert r.status_code == 200
        data = r.json()
        assert data["patient_id"] == pid
        assert data["stage"] == "sick"
        assert len(data["part_cells"]) == 1
        assert data["part_cells"][0]["part_code"] == "nose"
        assert data["status"] == "sick"
        assert "patient_image_url" not in data
        stages = {s["stage"] for s in data["patient_scenes"]}
        assert stages == {"sick", "treating", "healthy"}


def test_infirmary_scene_open_for_low_level_player(admin_client):
    """Сцены лечебницы не зависят от уровня игрока (нет 403 «локация недоступна»)."""
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)

    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 123).first()
        if u is None:
            u = User(vk_id=123, role="player", crosses_balance=0)
            s.add(u)
        u.level = 0
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        assert c.get(f"/api/infirmary/{scenes['sick']}").status_code == 200


def test_infirmary_detail_remedy_lab_field_id(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    lab = admin_client.post("/api/admin/fields", json={
        "name": "Лаборатория снадобий", "cols": 3, "rows": 2, "field_kind": "remedy_lab",
    }).json()
    with make_user_client(123, "player") as c:
        d = c.get(f"/api/infirmary/{scenes['sick']}").json()
        assert d["remedy_lab_field_id"] == lab["id"]
        hub = c.get("/api/infirmary").json()
        assert hub["current"]["remedy_lab_field_id"] == lab["id"]


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


# ── Осмотр / диагноз / выпуск ──

def _seed_user_ingredient(vk_id: int, ingredient_id: int, qty: int) -> None:
    from models import UserIngredient
    s = TestingSessionLocal()
    try:
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=qty))
        s.commit()
    finally:
        s.close()


def test_examine_returns_symptoms(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Хворь", rid, {"nose": "Горячий нос", "ear": "Чешется ухо"})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_part_cell(scenes["sick"], 0, 0, "nose")
    _seed_part_cell(scenes["sick"], 1, 0, "ear")
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "nose"})
        assert r.status_code == 200
        assert r.json()["symptoms"] == ["Горячий нос"]


def test_examine_unknown_part_400(admin_client):
    did = _seed_disease("Хворь", None, {"nose": "Горячий нос"})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_part_cell(scenes["sick"], 0, 0, "nose")
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/examine", json={"part_code": "tail"})
        assert r.status_code == 400


def test_diagnose_correct_gives_card(admin_client):
    rid = _seed_remedy("Мазь от кашля", [])
    did = _seed_disease("Кашель", rid, {"chest": "Хрипы"})
    pid, scenes = _seed_patient("Лис", did, 1)
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
    pid, scenes = _seed_patient("Лис", did, 1)
    _set_crosses(123, 500)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": other})
        assert r.status_code == 200
        assert r.json()["correct"] is False
        assert r.json()["crosses_balance"] == 300


def test_diagnose_wrong_blocked_when_balance_low(admin_client):
    did = _seed_disease("Кашель", None, {})
    other = _seed_disease("Хромота", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    _set_crosses(123, 100)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": other})
        assert r.status_code == 400


def test_diagnose_repeat_after_correct_400(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Кашель", rid, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    with make_user_client(123, "player") as c:
        assert c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did}).status_code == 200
        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert r.status_code == 400


def test_infirmary_requires_auth(client):
    assert client.get("/api/infirmary").status_code == 401
    assert client.get("/api/infirmary/handbook").status_code == 401
    assert client.post("/api/infirmary/patients/1/examine", json={"part_code": "nose"}).status_code == 401
    assert client.post("/api/infirmary/patients/1/diagnose", json={"disease_id": 1}).status_code == 401


# ── Зоны лечебницы (только «Книга») ──

def test_admin_infirmary_book_zone_crud(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    sick = scenes["sick"]
    r = admin_client.post(f"/api/admin/fields/{sick}/infirmary-zones", json={
        "zone_kind": "book", "col1": 0, "row1": 0, "col2": 1, "row2": 1,
    })
    assert r.status_code == 201
    z = r.json()
    assert z["zone_kind"] == "book"
    assert (z["col1"], z["row1"], z["col2"], z["row2"]) == (0, 0, 1, 1)

    detail = admin_client.get(f"/api/admin/fields/{sick}").json()
    assert len(detail["infirmary_zones"]) == 1

    assert admin_client.delete(f"/api/admin/fields/{sick}/infirmary-zones/{z['id']}").status_code == 204


def test_admin_infirmary_animal_zone_rejected(admin_client):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)
    r = admin_client.post(f"/api/admin/fields/{scenes['sick']}/infirmary-zones", json={
        "zone_kind": "animal", "col1": 0, "row1": 0, "col2": 1, "row2": 1,
    })
    assert r.status_code == 400


def test_admin_infirmary_zone_wrong_field_kind(admin_client):
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Грядки", "cols": 3, "rows": 2, "field_kind": "garden_beds"}
    ).json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/infirmary-zones", json={
        "zone_kind": "book", "col1": 0, "row1": 0, "col2": 1, "row2": 1,
    })
    assert r.status_code == 400


# ── Картинка карточки ──

def test_admin_upload_patient_card_image(admin_client, uploads_tmp):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), (120, 90, 60)).save(buf, format="PNG")

    r = admin_client.put(
        f"/api/admin/patients/{pid}/card-image",
        files={"image": ("c.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["card_image_url"].startswith("/api/uploads/patient_card_")


def test_admin_upload_patient_animal_image(admin_client, uploads_tmp):
    did = _seed_disease("Хворь", None, {})
    pid, scenes = _seed_patient("Лис", did, 1)

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), (60, 120, 90)).save(buf, format="PNG")

    r = admin_client.put(
        f"/api/admin/patients/{pid}/animal-image",
        files={"image": ("a.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["animal_image_url"].startswith("/api/uploads/patient_animal_")

    with make_user_client(123, "player") as c:
        hub = c.get("/api/infirmary").json()
        assert hub["current"]["animal_image_url"].startswith("/api/uploads/patient_animal_")


def test_admin_upload_disease_image(admin_client, uploads_tmp):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Кашель", rid, {"nose": "Горячий нос"})

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), (60, 60, 120)).save(buf, format="PNG")

    r = admin_client.put(
        f"/api/admin/diseases/{did}/image",
        files={"image": ("d.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["image_url"].startswith("/api/uploads/disease_")

    with make_user_client(123, "player") as c:
        hb = c.get("/api/infirmary/handbook").json()
        d = next(x for x in hb["diseases"] if x["id"] == did)
        assert d["image_url"].startswith("/api/uploads/disease_")


# ── Стадии пациента: sick → diagnosed → treated → released ──

def test_infirmary_status_progression_scenes(admin_client):
    ing = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing, 1)])
    did = _seed_disease("Хворь", rid, {"nose": "Горячий нос"})
    pid, scenes = _seed_patient("Лис", did, 1)
    _seed_part_cell(scenes["sick"], 0, 0, "nose")
    _seed_user_ingredient(123, ing, 5)

    with make_user_client(123, "player") as c:
        d = c.get(f"/api/infirmary/{scenes['sick']}").json()
        assert d["status"] == "sick"
        assert d["stage"] == "sick"

        r = c.post(f"/api/infirmary/patients/{pid}/diagnose", json={"disease_id": did})
        assert r.status_code == 200
        d = c.get(f"/api/infirmary/{scenes['treating']}").json()
        assert d["status"] == "diagnosed"
        assert d["disease_name"] == "Хворь"
        assert d["remedy_name"] == "Мазь"

        card_id = r.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200
        d = c.get(f"/api/infirmary/{scenes['healthy']}").json()
        assert d["status"] == "treated"

        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 200
        d = c.get(f"/api/infirmary/{scenes['healthy']}").json()
        assert d["status"] == "released"
        assert d["card_earned"] is True
