def test_list_plants_requires_auth(client):
    res = client.get("/api/plants")
    assert res.status_code == 401


def test_list_plants(player_client):
    res = player_client.get("/api/plants")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 4
    codes = {r["code"] for r in rows}
    assert "poison_mush" in codes


def test_list_plants_filter_category(player_client):
    res = player_client.get("/api/plants?category=garden")
    assert res.status_code == 200
    assert all(r["category"] == "garden" for r in res.json())


def test_get_plant(player_client):
    rows = player_client.get("/api/plants").json()
    pid = rows[0]["id"]
    res = player_client.get(f"/api/plants/{pid}")
    assert res.status_code == 200
    assert res.json()["id"] == pid


def test_get_plant_not_found(player_client):
    res = player_client.get("/api/plants/9999")
    assert res.status_code == 404
