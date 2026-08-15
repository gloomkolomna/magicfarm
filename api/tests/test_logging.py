from __future__ import annotations

from models import Log


def _logs_for(db, path: str):
    return (
        db.query(Log)
        .filter(Log.path == path)
        .order_by(Log.id.desc())
        .limit(10)
        .all()
    )


def test_log_captures_400_detail(player_client, db):
    resp = player_client.post("/api/farm/sell-surplus", json={
        "item_kind": "product", "item_id": 1, "qty": 0,
    })
    assert resp.status_code == 400
    assert resp.json()["detail"] == "qty >= 1"

    rows = _logs_for(db, "/api/farm/sell-surplus")
    assert rows, "ожидается запись лога для 400"
    err = rows[0]
    assert err.level == "warn"
    assert err.status_code == 400
    assert err.method == "POST"
    assert err.message is not None and "qty" in err.message.lower()
    assert err.details is not None and "qty" in err.details


def test_log_captures_422_detail(player_client, db):
    resp = player_client.post("/api/farm/plots/not-an-int/invest", json={"amount": 10})
    assert resp.status_code == 422

    rows = _logs_for(db, "/api/farm/plots/not-an-int/invest")
    assert rows, "ожидается запись лога для 422"
    err = rows[0]
    assert err.level == "warn"
    assert err.status_code == 422
    assert err.message, "detail валидации должен попасть в лог"


def test_log_skips_body_for_2xx(player_client, db):
    resp = player_client.get("/api/farm/productions")
    assert resp.status_code == 200

    rows = _logs_for(db, "/api/farm/productions")
    assert not rows, "успешные запросы (2xx) не логируются"
