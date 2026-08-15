def test_get_setting_requires_auth(client):
    res = client.get("/api/settings/auto_credit")
    assert res.status_code == 401


def test_get_auto_credit_default(player_client):
    res = player_client.get("/api/settings/auto_credit")
    assert res.status_code == 200
    assert res.json() == {"key": "auto_credit", "value": "1"}


def test_removed_settings_are_gone(player_client):
    assert player_client.get("/api/settings/crystal_rate_variant").status_code == 404
    assert player_client.get("/api/settings/house_material_norm").status_code == 404
    assert player_client.get("/api/settings/animal_production_norm").status_code == 404


def test_get_setting_unknown_key(player_client):
    res = player_client.get("/api/settings/no_such_key")
    assert res.status_code == 404


def test_update_setting_player_forbidden(player_client):
    res = player_client.put("/api/admin/settings/default_plant_qty", json={"value": "3"})
    assert res.status_code == 403


def test_update_setting_requires_auth(client):
    res = client.put("/api/admin/settings/default_plant_qty", json={"value": "3"})
    assert res.status_code == 401


def test_update_auto_credit_toggle(admin_client):
    res = admin_client.put("/api/admin/settings/auto_credit", json={"value": "0"})
    assert res.status_code == 200
    assert res.json()["value"] == "0"
    assert admin_client.get("/api/settings/auto_credit").json()["value"] == "0"

    res = admin_client.put("/api/admin/settings/auto_credit", json={"value": "1"})
    assert res.json()["value"] == "1"


def test_update_setting_unknown_key(admin_client):
    res = admin_client.put("/api/admin/settings/no_such_key", json={"value": "1"})
    assert res.status_code == 404


def test_update_setting_invalid_value(admin_client):
    res = admin_client.put("/api/admin/settings/default_plant_qty", json={"value": "abc"})
    assert res.status_code == 400


def test_update_plant_qty_clamped(admin_client):
    res = admin_client.put("/api/admin/settings/default_plant_qty", json={"value": "500"})
    assert res.status_code == 200
    assert res.json()["value"] == "50"
