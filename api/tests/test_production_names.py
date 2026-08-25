from sqlalchemy import text

from models import Field, Production, User
from tests.conftest import TestingSessionLocal


def _add_user(vk_id, display_name="Фермер"):
    s = TestingSessionLocal()
    try:
        s.add(User(vk_id=vk_id, role="player", display_name=display_name))
        s.commit()
    finally:
        s.close()


def _add_template(code, name):
    s = TestingSessionLocal()
    try:
        s.execute(text(
            "INSERT INTO production_templates (code, name, emoji, required, cards_to_draw, surcharge) "
            "VALUES (:code, :name, '', 500, 5, 40)"
        ), {"code": code, "name": name})
        s.commit()
    finally:
        s.close()


def _add_production(vk_id, kind, name):
    s = TestingSessionLocal()
    try:
        s.add(Production(user_id=vk_id, kind=kind, name=name,
                         status="installed", accumulated=0, required=500))
        s.commit()
    finally:
        s.close()


def test_farm_production_name_from_template(player_client):
    _add_user(9101)
    _add_template("shatyor_zelevareniya", "Шатёр зельеварения")
    _add_production(9101, "shatyor_zelevareniya", "shatyor_zelevareniya")

    res = player_client.get("/api/players/9101/farm")
    assert res.status_code == 200, res.text
    prods = res.json()["productions"]
    assert len(prods) == 1
    assert prods[0]["name"] == "Шатёр зельеварения"


def test_admin_player_production_name_from_template(admin_client):
    _add_user(9102)
    _add_template("shatyor_masterskaya_3", "Шатёр-мастерская")
    _add_production(9102, "shatyor_masterskaya_3", "shatyor_masterskaya_3")

    res = admin_client.get("/api/admin/players/9102")
    assert res.status_code == 200, res.text
    prods = res.json()["productions"]
    assert len(prods) == 1
    assert prods[0]["name"] == "Шатёр-мастерская"


def test_own_productions_list_uses_template_name(player_client):
    _add_user(123)
    _add_template("shatyor_zelevareniya", "Шатёр зельеварения")
    _add_production(123, "shatyor_zelevareniya", "shatyor_zelevareniya")

    res = player_client.get("/api/farm/productions")
    assert res.status_code == 200, res.text
    by_kind = {p["kind"]: p["name"] for p in res.json()}
    assert by_kind["shatyor_zelevareniya"] == "Шатёр зельеварения"


def test_production_name_fallback_to_stored(player_client):
    _add_user(9103)
    _add_production(9103, "some_unknown_kind", "SomeStored")

    res = player_client.get("/api/players/9103/farm")
    assert res.status_code == 200, res.text
    assert res.json()["productions"][0]["name"] == "SomeStored"


def test_production_name_fallback_to_kind(player_client):
    _add_user(9104)
    _add_production(9104, "some_unknown_kind", "")

    res = player_client.get("/api/players/9104/farm")
    assert res.status_code == 200, res.text
    assert res.json()["productions"][0]["name"] == "some_unknown_kind"


def test_player_field_returns_field_kind(player_client):
    _add_user(9105)
    s = TestingSessionLocal()
    try:
        fld = Field(code="clinic_t", name="Сцена", cols=2, rows=2,
                    field_kind="infirmary", grid_color="#2a1a0e")
        s.add(fld)
        s.commit()
        fld_id = fld.id
    finally:
        s.close()

    res = player_client.get(f"/api/players/9105/fields/{fld_id}")
    assert res.status_code == 200, res.text
    assert res.json()["field_kind"] == "infirmary"
