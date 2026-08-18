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


def _diagnose(c, patient_id: int, disease_id: int):
    return c.post(f"/api/infirmary/patients/{patient_id}/diagnose", json={"disease_id": disease_id})


def test_brew_consumes_and_heals(admin_client):
    ing1 = _seed_ingredient("Роса")
    ing2 = _seed_ingredient("Папоротник")
    rid = _seed_remedy("Мазь от кашля", [(ing1, 3), (ing2, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid = _seed_patient("Лис", did, 1, lab)
    _seed_user_ingredient(123, ing1, 5)
    _seed_user_ingredient(123, ing2, 1)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        assert d.status_code == 200
        card_id = d.json()["remedy_card_id"]

        r = c.post(f"/api/remedy-cards/{card_id}/brew")
        assert r.status_code == 200
        data = r.json()
        assert data["collection_card_earned"] is True
        assert data["patient_id"] == pid

        apo = {a["ingredient_id"]: a["qty"] for a in c.get("/api/apothecary").json()}
        assert apo[ing1] == 2
        assert apo.get(ing2, 0) == 0

        inf = c.get("/api/infirmary").json()
        l1 = next(x for x in inf["levels"] if x["level"] == 1)
        assert l1["patients"][0]["healed"] is True
        assert l1["patients"][0]["card_earned"] is True


def test_brew_insufficient_ingredients_400(admin_client):
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 3)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid = _seed_patient("Лис", did, 1, lab)
    _seed_user_ingredient(123, ing1, 2)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        r = c.post(f"/api/remedy-cards/{card_id}/brew")
        assert r.status_code == 400
        assert "Недостаточно" in r.json()["detail"]


def test_brew_unknown_card_404(admin_client):
    with make_user_client(123, "player") as c:
        assert c.post("/api/remedy-cards/9999/brew").status_code == 404


def test_brew_already_healed_400(admin_client):
    ing1 = _seed_ingredient("Роса")
    rid = _seed_remedy("Мазь", [(ing1, 1)])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    pid = _seed_patient("Лис", did, 1, lab)
    _seed_user_ingredient(123, ing1, 5)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200
        r = c.post(f"/api/remedy-cards/{card_id}/brew")
        assert r.status_code == 400


def test_collection(admin_client):
    rid = _seed_remedy("Мазь", [])
    did = _seed_disease("Кашель", rid)
    lab = _seed_field("remedy_lab", "Лаборатория")
    _seed_patient("Лис", did, 1, lab)
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
    pid = _seed_patient("Лис", did, 1, lab)
    _seed_user_ingredient(123, ing1, 5)

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200

        earned = [a for a in c.get("/api/achievements").json() if a["condition_kind"] == "healed_count"]
        assert len(earned) == 1
        assert earned[0]["earned"] is True

        ing2 = _seed_ingredient("Вода")
        rid2 = _seed_remedy("Бальзам", [(ing2, 1)])
        did2 = _seed_disease("Хромота", rid2)
        pid2 = _seed_patient("Сова", did2, 1, lab)
        _seed_user_ingredient(123, ing2, 5)
        d2 = _diagnose(c, pid2, did2)
        c.post(f"/api/remedy-cards/{d2.json()['remedy_card_id']}/brew")

        earned2 = [a for a in c.get("/api/achievements").json() if a["condition_kind"] == "healed_count"]
        assert len(earned2) == 1


def test_brew_requires_auth(client):
    assert client.post("/api/remedy-cards/1/brew").status_code == 401
    assert client.get("/api/collection").status_code == 401
