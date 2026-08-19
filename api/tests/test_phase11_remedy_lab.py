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

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        assert d.status_code == 200
        card_id = d.json()["remedy_card_id"]

        r = c.post(f"/api/remedy-cards/{card_id}/brew")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "treated"
        assert data["patient_id"] == pid

        apo = {a["ingredient_id"]: a["qty"] for a in c.get("/api/apothecary").json()}
        assert apo[ing1] == 2
        assert apo.get(ing2, 0) == 0

        # Карточка в коллекцию ещё НЕ выдана (только после выпуска).
        col = c.get("/api/collection").json()
        l1 = next(x for x in col["levels"] if x["level"] == 1)
        assert l1["cards"][0]["earned"] is False

        # Пациент «вылечен», но ещё не выпущен.
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

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200

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
    pid, _ = _seed_patient("Лис", did, 1)
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

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pid, did)
        card_id = d.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200
        assert c.post(f"/api/infirmary/patients/{pid}/release").status_code == 200

        earned = [a for a in c.get("/api/achievements").json() if a["condition_kind"] == "healed_count"]
        assert len(earned) == 1
        assert earned[0]["earned"] is True

        ing2 = _seed_ingredient("Вода")
        rid2 = _seed_remedy("Бальзам", [(ing2, 1)])
        did2 = _seed_disease("Хромота", rid2)
        pid2, _ = _seed_patient("Сова", did2, 1)
        _seed_user_ingredient(123, ing2, 5)
        d2 = _diagnose(c, pid2, did2)
        c.post(f"/api/remedy-cards/{d2.json()['remedy_card_id']}/brew")
        c.post(f"/api/infirmary/patients/{pid2}/release")

        earned2 = [a for a in c.get("/api/achievements").json() if a["condition_kind"] == "healed_count"]
        assert len(earned2) == 1


def test_brew_requires_auth(client):
    assert client.post("/api/remedy-cards/1/brew").status_code == 401
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

    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=123, plant_id=pid, qty=3))
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pat, did)
        card_id = d.json()["remedy_card_id"]
        assert c.post(f"/api/remedy-cards/{card_id}/brew").status_code == 200

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

    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=123, plant_id=pid, qty=1))
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        d = _diagnose(c, pat, did)
        card_id = d.json()["remedy_card_id"]
        res = c.post(f"/api/remedy-cards/{card_id}/brew")
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

    with make_user_client(1001, "player") as c1:
        assert c1.get(f"/api/infirmary/{inf}").json()["status"] == "sick"
        d = _diagnose(c1, pid, did)
        assert c1.post(f"/api/remedy-cards/{d.json()['remedy_card_id']}/brew").status_code == 200
        assert c1.post(f"/api/infirmary/patients/{pid}/release").status_code == 200
        assert c1.get(f"/api/infirmary/{inf}").json()["status"] == "released"

    with make_user_client(1002, "player") as c2:
        assert c2.get(f"/api/infirmary/{inf}").json()["status"] == "sick"
        d = _diagnose(c2, pid, did)
        assert d.status_code == 200
        assert c2.post(f"/api/remedy-cards/{d.json()['remedy_card_id']}/brew").status_code == 200
        assert c2.post(f"/api/infirmary/patients/{pid}/release").status_code == 200
        assert c2.get(f"/api/infirmary/{inf}").json()["status"] == "released"

    # Животное не удаляется из админки.
    patients = admin_client.get("/api/admin/patients").json()
    assert any(p["id"] == pid for p in patients)
