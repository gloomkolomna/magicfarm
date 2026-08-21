import datetime
import io
import os

from PIL import Image

from tests.conftest import TestingSessionLocal


def _photo_png(w: int = 900, h: int = 700) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (80, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _upload_report(c, **fields):
    data = {"amount": fields.get("amount", 100)}
    if fields.get("note") is not None:
        data["note"] = fields["note"]
    files = [("photo_after", ("a.png", io.BytesIO(_photo_png()), "image/png"))]
    if fields.get("before"):
        files.append(("photo_before", ("b.png", io.BytesIO(_photo_png(600, 400)), "image/png")))
    return c.post("/api/stitches/reports", data=data, files=files)


def _seed_report(
    vk_id: int,
    created_days_ago: int,
    status: str = "accepted",
    thumb: bool = True,
    photo_url: str | None = None,
) -> int:
    from models import StitchReport
    s = TestingSessionLocal()
    try:
        r = StitchReport(
            user_id=vk_id,
            amount=100,
            status=status,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=created_days_ago),
        )
        if photo_url is not None:
            r.photo_after_url = photo_url
            if thumb:
                r.photo_after_thumb_url = photo_url.replace("stitch_", "thumb_stitch_", 1)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def _get_report(rid: int):
    from models import StitchReport
    s = TestingSessionLocal()
    try:
        s.expire_all()
        return s.query(StitchReport).filter(StitchReport.id == rid).first()
    finally:
        s.close()


def test_upload_creates_thumbnail(player_client, uploads_tmp):
    r = _upload_report(player_client, amount=100, before=True, note="тест")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["photo_after_url"] and body["photo_after_url"].startswith("/api/uploads/stitch_")
    assert body["photo_after_thumb_url"] and body["photo_after_thumb_url"].startswith("/api/uploads/thumb_stitch_")
    assert body["photo_before_thumb_url"] and body["photo_before_thumb_url"].startswith("/api/uploads/thumb_stitch_")

    for url in (body["photo_after_url"], body["photo_after_thumb_url"]):
        path = os.path.join(uploads_tmp, url.rsplit("/", 1)[-1])
        assert os.path.isfile(path)

    thumb_name = body["photo_after_thumb_url"].rsplit("/", 1)[-1]
    img = Image.open(os.path.join(uploads_tmp, thumb_name))
    assert max(img.size) <= 300
    orig = Image.open(os.path.join(uploads_tmp, body["photo_after_url"].rsplit("/", 1)[-1]))
    assert max(orig.size) <= 1280
    assert orig.size >= img.size


def test_cleanup_deletes_expired_originals_and_keeps_thumbs(db, monkeypatch):
    import config
    from services import s3_storage
    from services.s3_cleanup import cleanup_expired_stitch_photos

    base = "https://storage.example.net/bk"
    monkeypatch.setattr(config, "S3_PUBLIC_URL", base)
    deleted = []
    monkeypatch.setattr(s3_storage, "delete_object", lambda key: deleted.append(key))

    expired = _seed_report(123, created_days_ago=31, photo_url=f"{base}/123/stitch_123_after_1_ab.jpg")
    fresh = _seed_report(123, created_days_ago=10, photo_url=f"{base}/123/stitch_123_after_2_cd.jpg")
    pending = _seed_report(123, created_days_ago=40, status="pending", photo_url=f"{base}/123/stitch_123_after_3_ef.jpg")
    legacy = _seed_report(123, created_days_ago=40, thumb=False, photo_url=f"{base}/123/stitch_123_after_4_gh.jpg")
    local = _seed_report(123, created_days_ago=40, photo_url="/api/uploads/stitch_123_after_5_ij.jpg")

    stats = cleanup_expired_stitch_photos(db)

    assert stats["cleaned"] == 1
    assert stats["objects_deleted"] == 1
    assert stats["skipped_no_thumb"] == 1
    assert deleted == ["123/stitch_123_after_1_ab.jpg"]

    r = _get_report(expired)
    assert r.photo_after_url is None
    assert r.photo_after_thumb_url == f"{base}/123/thumb_stitch_123_after_1_ab.jpg"

    assert _get_report(fresh).photo_after_url is not None
    assert _get_report(pending).photo_after_url is not None
    assert _get_report(legacy).photo_after_url is not None
    assert _get_report(local).photo_after_url is not None


def test_cleanup_removes_before_photo_too(db, monkeypatch):
    import config
    from models import StitchReport
    from services import s3_storage
    from services.s3_cleanup import cleanup_expired_stitch_photos

    base = "https://storage.example.net/bk"
    monkeypatch.setattr(config, "S3_PUBLIC_URL", base)
    deleted = []
    monkeypatch.setattr(s3_storage, "delete_object", lambda key: deleted.append(key))

    s = TestingSessionLocal()
    try:
        old = datetime.datetime.utcnow() - datetime.timedelta(days=32)
        s.add(StitchReport(
            user_id=123, amount=50, status="accepted", created_at=old,
            photo_after_url=f"{base}/123/stitch_123_after_9_aa.jpg",
            photo_after_thumb_url=f"{base}/123/thumb_stitch_123_after_9_aa.jpg",
            photo_before_url=f"{base}/123/stitch_123_before_9_bb.jpg",
            photo_before_thumb_url=f"{base}/123/thumb_stitch_123_before_9_bb.jpg",
        ))
        s.commit()
    finally:
        s.close()

    stats = cleanup_expired_stitch_photos(db)
    assert stats["objects_deleted"] == 2
    assert set(deleted) == {"123/stitch_123_after_9_aa.jpg", "123/stitch_123_before_9_bb.jpg"}

    s2 = TestingSessionLocal()
    try:
        s2.expire_all()
        row = s2.query(StitchReport).filter(StitchReport.user_id == 123).first()
        assert row.photo_after_url is None
        assert row.photo_before_url is None
        assert row.photo_after_thumb_url is not None
        assert row.photo_before_thumb_url is not None
    finally:
        s2.close()


def test_run_cleanup_script_prints_stats(db, monkeypatch, capsys):
    import run_cleanup

    monkeypatch.setattr(run_cleanup, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        run_cleanup, "cleanup_expired_stitch_photos",
        lambda session: {"scanned": 0, "cleaned": 0, "objects_deleted": 0, "skipped_no_thumb": 0},
    )

    run_cleanup.main()
    out = capsys.readouterr().out
    assert "scanned=0" in out
    assert "cleaned=0" in out


def test_s3_key_from_url(monkeypatch):
    import config
    from services import s3_storage

    base = "https://storage.example.net/bk"
    monkeypatch.setattr(config, "S3_PUBLIC_URL", base)
    assert s3_storage.s3_key_from_url(f"{base}/123/stitch_a.jpg") == "123/stitch_a.jpg"
    assert s3_storage.s3_key_from_url("/api/uploads/stitch_a.jpg") is None
    assert s3_storage.s3_key_from_url("https://other.net/stitch_a.jpg") is None
    assert s3_storage.s3_key_from_url(None) is None
    monkeypatch.setattr(config, "S3_PUBLIC_URL", "")
    assert s3_storage.s3_key_from_url(f"{base}/123/stitch_a.jpg") is None
