def test_health(client):
    res = client.get("/api/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "farm-api"


def test_health_no_auth_required(client):
    # /api/ не требует авторизации — публичный health-check.
    res = client.get("/api/")
    assert res.status_code == 200
