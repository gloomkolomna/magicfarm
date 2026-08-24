import io

import pytest
from PIL import Image

from services.uploads import _process


def _rgba_png(w: int = 100, h: int = 80) -> bytes:
    img = Image.new("RGBA", (w, h), (200, 100, 50, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _rgb_png(w: int = 100, h: int = 80) -> bytes:
    img = Image.new("RGB", (w, h), (90, 160, 70))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_pixels(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_rgba_keeps_transparency():
    buf = _rgba_png()
    result, is_png = _process(buf, max_size=512)
    assert is_png is True
    img = _load_pixels(result)
    assert img.mode in ("RGBA", "P")
    if img.mode == "P":
        return
    px = img.getpixel((10, 10))
    assert px[3] == 0


def test_rgba_opaque_keeps_color():
    img = Image.new("RGBA", (40, 40), (0, 128, 255, 255))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result, is_png = _process(raw.getvalue(), max_size=512)
    assert is_png is True
    px_img = _load_pixels(result)
    if px_img.mode == "P":
        return
    px = px_img.getpixel((5, 5))
    assert px[0] < 5
    assert 120 <= px[1] <= 135
    assert 245 <= px[2] <= 255


def test_rgb_becomes_jpeg():
    buf = _rgb_png()
    result, is_png = _process(buf, max_size=512)
    assert is_png is False
    img = _load_pixels(result)
    assert img.mode == "RGB"


def test_resize_large():
    img = Image.new("RGB", (2000, 1000), (50, 100, 150))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result, _ = _process(raw.getvalue(), max_size=800)
    px_img = _load_pixels(result)
    w, h = px_img.size
    assert max(w, h) <= 800


def test_no_resize_when_small():
    img = Image.new("RGB", (100, 80), (50, 100, 150))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result, _ = _process(raw.getvalue(), max_size=800)
    px_img = _load_pixels(result)
    assert px_img.size == (100, 80)


def test_no_max_size_returns_original():
    buf = _rgb_png()
    result, is_png = _process(buf, max_size=None)
    assert result == buf
    assert is_png is True


# ===== Лимиты изображений и видео =====

def _fake_upload(data: bytes, ctype: str):
    from fastapi import UploadFile
    from io import BytesIO
    return UploadFile(file=BytesIO(data), filename="f.bin", headers={"content-type": ctype})


def test_video_within_limit_saved(monkeypatch, uploads_tmp):
    import config
    monkeypatch.setattr(config, "UPLOAD_VIDEO_MAX_BYTES", 1024 * 1024)
    from services.uploads import save_upload
    up = _fake_upload(b"abcd" * 100, "video/mp4")
    up.filename = "movie.mp4"
    url = save_upload(up, "gm_test", allow_video=True)
    assert url.startswith("/api/uploads/gm_test")
    assert url.endswith(".mp4")


def test_video_over_limit_rejected(monkeypatch, uploads_tmp):
    import config
    monkeypatch.setattr(config, "UPLOAD_VIDEO_MAX_BYTES", 1024)
    from services.uploads import save_upload, _read_with_limit
    from fastapi import HTTPException
    try:
        save_upload(_fake_upload(b"z" * 4096, "video/mp4"), "gm_test", allow_video=True)
        raise AssertionError("ожидались ошибки HTTPException")
    except HTTPException as e:
        assert e.status_code == 400
        assert "МБ" in e.detail


def test_image_over_limit_rejected(monkeypatch, uploads_tmp):
    import config
    monkeypatch.setattr(config, "UPLOAD_MAX_BYTES", 1024)
    from services.uploads import save_upload
    from fastapi import HTTPException
    try:
        save_upload(_fake_upload(b"x" * 4096, "image/png"), "gm_test")
        raise AssertionError("ожидались ошибки HTTPException")
    except HTTPException as e:
        assert e.status_code == 400
        assert "КБ" in e.detail


def test_video_not_allowed_without_flag():
    from services.uploads import save_upload
    from fastapi import HTTPException
    try:
        save_upload(_fake_upload(b"abcd", "video/mp4"), "gm_test")
        raise AssertionError("ожидались ошибки HTTPException")
    except HTTPException as e:
        assert e.status_code == 400


# ===== Видео → S3 (стриминг) =====

class _FakeS3:
    def __init__(self, base: str):
        self.base = base
        self.uploaded = {}
        self.deleted = []

    def upload_bytes(self, key, data, content_type="image/jpeg"):
        self.uploaded[key] = (data, content_type)
        return f"{self.base}/{key}"

    def upload_stream(self, key, fileobj, content_type="video/mp4"):
        self.uploaded[key] = (fileobj.read(), content_type)
        return f"{self.base}/{key}"

    def delete_object(self, key):
        self.deleted.append(key)


def _attach_fake_s3(monkeypatch):
    import config
    from services import uploads as uploads_mod
    fake = _FakeS3("https://s3.example.com/bucket")
    monkeypatch.setattr(config, "S3_PUBLIC_URL", fake.base)
    monkeypatch.setattr(uploads_mod, "_S3", fake)
    return fake


def test_video_s3_stream_upload(monkeypatch, uploads_tmp):
    import os
    import config
    data = b"\x00\x00\x00\x18ftypmp42" + b"v" * 100
    up = _fake_upload(data, "video/mp4")
    up.filename = "movie.mp4"
    fake = _attach_fake_s3(monkeypatch)
    from services.uploads import save_upload
    url = save_upload(up, "gm_test", allow_video=True)
    assert url.startswith(fake.base + "/videos/gm_test")
    assert url.endswith(".mp4")
    assert list(fake.uploaded) == [url[len(fake.base) + 1:]]
    assert fake.uploaded[url[len(fake.base) + 1:]] == (data, "video/mp4")
    assert os.listdir(config.UPLOADS_DIR) == []


def test_video_s3_over_limit_rejected(monkeypatch, uploads_tmp):
    import config
    monkeypatch.setattr(config, "UPLOAD_VIDEO_MAX_BYTES", 1024)
    fake = _attach_fake_s3(monkeypatch)
    from services.uploads import save_upload
    from fastapi import HTTPException
    try:
        save_upload(_fake_upload(b"z" * 4096, "video/mp4"), "gm_test", allow_video=True)
        raise AssertionError("ожидались ошибки HTTPException")
    except HTTPException as e:
        assert e.status_code == 400
        assert "МБ" in e.detail
    assert fake.uploaded == {}


def test_video_local_stream_content(monkeypatch, uploads_tmp):
    import os
    import config
    data = b"v" * 5000
    up = _fake_upload(data, "video/mp4")
    up.filename = "movie.mp4"
    from services.uploads import save_upload
    url = save_upload(up, "gm_test", allow_video=True)
    name = url.rsplit("/", 1)[-1]
    with open(os.path.join(config.UPLOADS_DIR, name), "rb") as fh:
        assert fh.read() == data


def test_video_local_over_limit_no_partial_file(monkeypatch, uploads_tmp):
    import os
    import config
    monkeypatch.setattr(config, "UPLOAD_VIDEO_MAX_BYTES", 1024)
    from services.uploads import save_upload
    from fastapi import HTTPException
    try:
        save_upload(_fake_upload(b"z" * 4096, "video/mp4"), "gm_test", allow_video=True)
        raise AssertionError("ожидались ошибки HTTPException")
    except HTTPException as e:
        assert e.status_code == 400
        assert "МБ" in e.detail
    assert os.listdir(config.UPLOADS_DIR) == []


def test_video_local_reads_stream_not_memory(monkeypatch, uploads_tmp):
    data = b"x" * (3 * 1024 * 1024)
    up = _fake_upload(data, "video/mp4")
    up.filename = "movie.mp4"
    from services import uploads as uploads_mod
    from services.uploads import save_upload
    calls = {"n": 0}

    def _fail_read(*a, **kw):
        calls["n"] += 1
        raise AssertionError("видео не должно читаться в память через _read_with_limit")

    monkeypatch.setattr(uploads_mod, "_read_with_limit", _fail_read)
    url = save_upload(up, "gm_test", allow_video=True)
    assert calls["n"] == 0
    assert url.startswith("/api/uploads/gm_test")
