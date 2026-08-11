import io
import os

import pytest
from PIL import Image


def _img_bytes(w: int = 400, h: int = 300, fmt: str = "PNG") -> bytes:
    img = Image.new("RGB", (w, h), (90, 160, 70))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ===== POST /stitches/reports — авто-зачёт (по умолчанию) =====

def test_create_report_auto_credit(uploads_tmp, player_client):
    # По умолчанию auto_credit=on → сразу accepted и зачислено на баланс.
    res = player_client.post(
        "/api/stitches/reports",
        data={"amount": "50", "note": "вышито 50"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "accepted"
    assert data["amount"] == 50
    assert data["user_id"] == 123
    assert data["note"] == "вышито 50"
    assert data["reviewed_at"] is not None

    me = player_client.get("/api/me").json()
    assert me["crosses_balance"] == 50
    assert me["crosses_total"] == 50


def test_create_report_requires_auth(uploads_tmp, client):
    res = client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 401


def test_create_report_amount_below_min(uploads_tmp, player_client):
    res = player_client.post(
        "/api/stitches/reports",
        data={"amount": "0"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 400


def test_create_report_amount_above_max(uploads_tmp, player_client):
    res = player_client.post(
        "/api/stitches/reports",
        data={"amount": "100001"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 400


def test_create_report_not_an_image(uploads_tmp, player_client):
    res = player_client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("x.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert res.status_code == 400


def test_create_report_dedup_same_amount(uploads_tmp, player_client):
    # Два отчёта с одинаковым amount подряд → второй отклоняется (дубль).
    first = player_client.post(
        "/api/stitches/reports",
        data={"amount": "77"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert first.status_code == 201
    second = player_client.post(
        "/api/stitches/reports",
        data={"amount": "77"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert second.status_code == 429
    # Создан только один отчёт.
    rows = player_client.get("/api/stitches/reports").json()
    assert len([r for r in rows if r["amount"] == 77]) == 1


def test_create_report_different_amount_allowed(uploads_tmp, player_client):
    # Разные amount подряд — оба принимаются (это не дубль).
    player_client.post(
        "/api/stitches/reports",
        data={"amount": "11"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    res = player_client.post(
        "/api/stitches/reports",
        data={"amount": "12"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 201


# ===== Режим модерации (auto_credit=off) =====

def test_create_report_review_mode_pending(uploads_tmp, admin_client):
    # Выключаем авто-зачёт → отчёт ждёт модерации, ничего не начисляется.
    admin_client.put("/api/admin/settings/auto_credit", json={"value": "0"})
    res = admin_client.post(
        "/api/stitches/reports",
        data={"amount": "30"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "pending"
    assert data["reviewed_at"] is None


def test_review_accept_credits(admin_client, uploads_tmp):
    # auto_credit off → создаём отчёт игроком, принимает admin.
    admin_client.put("/api/admin/settings/auto_credit", json={"value": "0"})

    from tests.conftest import make_user_client
    with make_user_client(555, "player") as pc:
        created = pc.post(
            "/api/stitches/reports",
            data={"amount": "40"},
            files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
        ).json()
        assert created["status"] == "pending"

        # Игрок: крестики ещё не начислены.
        me_before = pc.get("/api/me").json()
        assert me_before["crosses_balance"] == 0

        rid = created["id"]

    # Admin принимает.
    res = admin_client.post(f"/api/stitches/reports/{rid}/accept")
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"

    with make_user_client(555, "player") as pc:
        me = pc.get("/api/me").json()
        assert me["crosses_balance"] == 40
        assert me["crosses_total"] == 40


def test_review_reject_no_credit(admin_client, uploads_tmp):
    admin_client.put("/api/admin/settings/auto_credit", json={"value": "0"})

    from tests.conftest import make_user_client
    with make_user_client(556, "player") as pc:
        rid = pc.post(
            "/api/stitches/reports",
            data={"amount": "40"},
            files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
        ).json()["id"]

    res = admin_client.post(f"/api/stitches/reports/{rid}/reject")
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    with make_user_client(556, "player") as pc:
        assert pc.get("/api/me").json()["crosses_balance"] == 0


def test_accept_requires_admin(uploads_tmp, player_client):
    # auto_credit off — игрок не может сам принять свой отчёт.
    player_client.put("/api/admin/settings/auto_credit", json={"value": "0"})
    rid = player_client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    ).json()["id"]
    res = player_client.post(f"/api/stitches/reports/{rid}/accept")
    assert res.status_code == 403


def test_accept_already_reviewed(admin_client, uploads_tmp):
    admin_client.put("/api/admin/settings/auto_credit", json={"value": "0"})
    rid = admin_client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    ).json()["id"]
    assert admin_client.post(f"/api/stitches/reports/{rid}/accept").status_code == 200
    # Повторный accept уже рассмотренного → 409.
    res = admin_client.post(f"/api/stitches/reports/{rid}/accept")
    assert res.status_code == 409


def test_accept_not_found(admin_client):
    assert admin_client.post("/api/stitches/reports/9999/accept").status_code == 404


# ===== GET /stitches/reports =====

def test_list_reports_mine(uploads_tmp, player_client):
    for n in (10, 20):
        player_client.post(
            "/api/stitches/reports",
            data={"amount": str(n)},
            files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
        )
    res = player_client.get("/api/stitches/reports")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    assert all(r["user_id"] == 123 for r in rows)


def test_list_reports_player_cannot_see_others(uploads_tmp, player_client):
    player_client.post(
        "/api/stitches/reports",
        data={"amount": "5"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    from tests.conftest import make_user_client
    with make_user_client(777, "player") as other:
        other.post(
            "/api/stitches/reports",
            data={"amount": "7"},
            files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
        )
    # player видит только свой отчёт, не чужой.
    rows = player_client.get("/api/stitches/reports").json()
    assert len(rows) == 1
    assert rows[0]["amount"] == 5


def test_list_reports_admin_sees_all(uploads_tmp, admin_client):
    admin_client.post(
        "/api/stitches/reports",
        data={"amount": "8"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    from tests.conftest import make_user_client
    with make_user_client(888, "player") as other:
        other.post(
            "/api/stitches/reports",
            data={"amount": "9"},
            files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
        )
    rows = admin_client.get("/api/stitches/reports").json()
    amounts = sorted(r["amount"] for r in rows)
    assert amounts == [8, 9]


def test_list_reports_status_filter(uploads_tmp, admin_client):
    admin_client.put("/api/admin/settings/auto_credit", json={"value": "0"})
    admin_client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    rows = admin_client.get("/api/stitches/reports?status=pending").json()
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"


# ===== DELETE =====

def test_delete_report_admin(uploads_tmp, admin_client):
    rid = admin_client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    ).json()["id"]
    res = admin_client.delete(f"/api/stitches/reports/{rid}")
    assert res.status_code == 204


def test_delete_report_player_forbidden(uploads_tmp, player_client):
    rid = player_client.post(
        "/api/stitches/reports",
        data={"amount": "10"},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    ).json()["id"]
    res = player_client.delete(f"/api/stitches/reports/{rid}")
    assert res.status_code == 403
