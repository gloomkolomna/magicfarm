from tests.conftest import TestingSessionLocal, make_user_client
from models import Field, FieldCell, Inventory, Plot, User


def _add_user(vk_id, display_name=None, level=0, coins=0, crosses_total=0, status="active"):
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        if u is None:
            u = User(vk_id=vk_id, role="player", display_name=display_name,
                     level=level, coins=coins, crosses_total=crosses_total, status=status)
            s.add(u)
        else:
            u.display_name = display_name
            u.level = level
            u.coins = coins
            u.crosses_total = crosses_total
            u.status = status
        s.commit()
    finally:
        s.close()


def test_players_search_requires_auth(client):
    assert client.get("/api/players/search", params={"q": "x"}).status_code == 401
    assert client.get("/api/players/1/farm").status_code == 401


def test_search_by_name(player_client):
    _add_user(9001, display_name="Марина")
    _add_user(9002, display_name="Маг Годвин")
    res = player_client.get("/api/players/search", params={"q": "марина"})
    assert res.status_code == 200
    ids = [p["vk_id"] for p in res.json()]
    assert 9001 in ids
    assert 9002 not in ids
    hit = next(p for p in res.json() if p["vk_id"] == 9001)
    assert hit["display_name"] == "Марина"


def test_search_by_vk_id(player_client):
    _add_user(9003, display_name="Русалка")
    res = player_client.get("/api/players/search", params={"q": "9003"})
    assert res.status_code == 200
    assert any(p["vk_id"] == 9003 for p in res.json())


def test_search_excludes_blocked(player_client):
    _add_user(9004, display_name="Заблок", status="blocked")
    res = player_client.get("/api/players/search", params={"q": "заблок"})
    assert res.status_code == 200
    assert res.json() == []


def test_farm_returns_read_only_snapshot(player_client):
    _add_user(9005, display_name="Фермер", level=3, coins=100, crosses_total=500)
    s = TestingSessionLocal()
    try:
        s.add(Plot(user_id=9005, plant_id=1, qty=2, status="planted", accumulated=0, required=100))
        s.add(Inventory(user_id=9005, plant_id=1, qty=3))
        s.add(Inventory(user_id=9005, product_id=1, qty=2))
        s.commit()
    finally:
        s.close()
    res = player_client.get("/api/players/9005/farm")
    assert res.status_code == 200
    data = res.json()
    assert data["display_name"] == "Фермер"
    assert data["level"] == 3
    assert data["coins"] == 100
    assert data["crosses_total"] == 500
    assert data["round"] == 1
    assert len(data["plots"]) == 1
    assert data["plots"][0]["plant_name"] == "Джекобоб"
    assert data["plots"][0]["status"] == "planted"
    assert data["plots"][0]["required"] == 100
    assert len(data["plants"]) == 1
    assert data["plants"][0]["item_id"] == 1
    assert data["plants"][0]["name"] == "Джекобоб"
    assert data["plants"][0]["qty"] == 3
    assert len(data["products"]) == 1
    assert data["products"][0]["item_id"] == 1
    assert data["products"][0]["name"] == "Яд"
    assert data["products"][0]["qty"] == 2


def test_farm_unknown_player_404(player_client):
    assert player_client.get("/api/players/999999/farm").status_code == 404


def test_farm_blocked_user_404(player_client):
    _add_user(9006, display_name="Блок", status="blocked")
    assert player_client.get("/api/players/9006/farm").status_code == 404


def test_player_field_public_requires_auth(client):
    assert client.get("/api/players/1/fields/1").status_code == 401


def test_player_field_returns_plots(player_client):
    _add_user(9010, display_name="Фермер")
    s = TestingSessionLocal()
    try:
        fld = Field(code="test_f", name="Тестовое поле", cols=4, rows=2, grid_color="#2a1a0e")
        s.add(fld)
        s.flush()
        s.add(FieldCell(field_id=fld.id, col=0, row=0, kind="bed", occupant_user_id=9010))
        s.flush()
        cell = s.query(FieldCell).filter(FieldCell.field_id == fld.id).first()
        s.add(Plot(user_id=9010, plant_id=1, qty=1, cell_id=cell.id, status="planted", accumulated=10, required=100))
        s.commit()
        fld_id = fld.id
    finally:
        s.close()
    res = player_client.get(f"/api/players/9010/fields/{fld_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Тестовое поле"
    assert data["cols"] == 4 and data["rows"] == 2
    beds = [c for c in data["cells"] if c["kind"] == "bed"]
    assert len(beds) == 1
    assert beds[0]["plot"]["plant_name"] == "Джекобоб"
    assert beds[0]["plot"]["accumulated"] == 10
    assert beds[0]["plot"]["required"] == 100


def test_player_field_404(player_client):
    _add_user(9011)
    assert player_client.get("/api/players/999999/fields/1").status_code == 404
    assert player_client.get("/api/players/9011/fields/999999").status_code == 404


def test_farm_fields_lists_only_opened_locations(player_client):
    _add_user(9012, display_name="Фермер")
    s = TestingSessionLocal()
    try:
        f1 = Field(code="f1", name="Поле 1", cols=4, rows=2, grid_color="#2a1a0e")
        f2 = Field(code="f2", name="Поле 2", cols=4, rows=2, grid_color="#2a1a0e")
        s.add_all([f1, f2])
        s.flush()
        s.add(FieldCell(field_id=f1.id, col=0, row=0, kind="bed"))
        s.flush()
        cell = s.query(FieldCell).filter(FieldCell.field_id == f1.id).first()
        s.add(Plot(user_id=9012, plant_id=1, qty=1, cell_id=cell.id, status="planted", accumulated=0, required=100))
        s.commit()
        f1_id = f1.id
        f2_id = f2.id
    finally:
        s.close()
    data = player_client.get("/api/players/9012/farm").json()
    ids = [f["id"] for f in data["fields"]]
    assert f1_id in ids
    assert f2_id not in ids


def test_player_field_includes_pets(player_client):
    from models import Pet, PetZone, UserPet

    _add_user(9013, display_name="Фермер")
    s = TestingSessionLocal()
    try:
        fld = Field(code="pets_f", name="Питомцы", cols=4, rows=2, grid_color="#2a1a0e")
        s.add(fld)
        s.flush()
        s.add(PetZone(field_id=fld.id, col1=0, row1=0, col2=2, row2=1))
        s.add(FieldCell(field_id=fld.id, col=0, row=0, kind="pet"))
        s.flush()
        pet = Pet(code="test_pet", name="Енот", emoji="🦝")
        s.add(pet)
        s.flush()
        cell = s.query(FieldCell).filter(FieldCell.field_id == fld.id).first()
        s.add(UserPet(user_id=9013, pet_id=pet.id, cell_id=cell.id))
        s.commit()
        fld_id = fld.id
    finally:
        s.close()
    data = player_client.get(f"/api/players/9013/fields/{fld_id}").json()
    zones = data["pet_zones"]
    assert len(zones) == 1
    assert zones[0]["pet_id"] is not None
    assert zones[0]["pet_name"] == "Енот"
    assert zones[0]["pet_emoji"] == "🦝"


def test_farm_fields_includes_only_active_patient_scene(player_client):
    from models import PatientAnimal, UserPatientState

    _add_user(9014, display_name="Фермер")
    s = TestingSessionLocal()
    try:
        pa = PatientAnimal(code="test_pa", name="Лис", level=1)
        s.add(pa)
        s.flush()
        scene = Field(code="scene_f", name="Лесная лечебница", cols=4, rows=2, grid_color="#2a1a0e",
                      field_kind="infirmary", clinic_animal_id=pa.id, clinic_stage="sick")
        s.add(scene)
        s.flush()
        other = Field(code="other_scene", name="Другая сцена", cols=4, rows=2, grid_color="#2a1a0e",
                      field_kind="infirmary")
        s.add(other)
        s.commit()
        s.add(UserPatientState(user_id=9014, patient_id=pa.id, status="sick", current_field_id=scene.id))
        s.commit()
        scene_id = scene.id
        other_id = other.id
    finally:
        s.close()
    data = player_client.get("/api/players/9014/farm").json()
    ids = [f["id"] for f in data["fields"]]
    assert scene_id in ids
    assert other_id not in ids


def test_search_by_vk_id_outside_candidates(player_client, monkeypatch):
    from routes import public_players

    monkeypatch.setattr(public_players, "SEARCH_CANDIDATE_LIMIT", 2)

    _add_user(501, display_name="Лидер Раз", level=9)
    _add_user(502, display_name="Лидер Два", level=8)
    _add_user(777, display_name="Новичок", level=0)

    res = player_client.get("/api/players/search", params={"q": "777"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 1
    assert data[0]["vk_id"] == 777
    assert data[0]["display_name"] == "Новичок"
