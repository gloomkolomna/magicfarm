import io
import os
import time

from fastapi import HTTPException, UploadFile, status

import config

_S3 = None


def _get_s3():
    global _S3
    if _S3 is None and config.S3_ENABLED:
        from services.s3_storage import upload_bytes as _up, delete_object as _del
        _S3 = (_up, _del)
    return _S3


def _read_with_limit(upload: UploadFile, allow_video: bool = False) -> tuple[bytes, bool]:
    ctype = (upload.content_type or "").lower()
    is_video = ctype.startswith("video/")
    if is_video:
        if not allow_video:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Видео не поддерживается")
    elif not ctype.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл должен быть изображением")

    buf = bytearray()
    while True:
        chunk = upload.file.read(64 * 1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > config.UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Файл слишком большой (макс. {config.UPLOAD_MAX_BYTES // 1024} КБ)",
            )
    return bytes(buf), is_video


def _process(buf: bytes, max_size: int | None) -> tuple[bytes, bool]:
    if max_size is None:
        return buf, True
    from PIL import Image

    img = Image.open(io.BytesIO(buf))
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)

    if img.mode == "P":
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if has_alpha else "RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > max_size:
        scale = max_size / longest
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    out = io.BytesIO()
    if has_alpha:
        img.save(out, format="PNG", optimize=True)
        return out.getvalue(), True
    else:
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue(), False


def save_upload(upload: UploadFile, prefix: str, max_size: int | None = None, allow_video: bool = False) -> str:
    buf, is_video = _read_with_limit(upload, allow_video=allow_video)
    if is_video:
        ext = os.path.splitext(upload.filename or "")[1].lower().lstrip(".") or "mp4"
        name = f"{prefix}_{int(time.time())}_{os.urandom(3).hex()}.{ext}"
        path = os.path.join(config.UPLOADS_DIR, name)
        with open(path, "wb") as fh:
            fh.write(buf)
        return f"/api/uploads/{name}"

    processed, is_png = _process(buf, max_size)
    if max_size is not None:
        ext = "png" if is_png else "jpg"
    else:
        ext = os.path.splitext(upload.filename or "")[1].lower().lstrip(".") or "png"
    name = f"{prefix}_{int(time.time())}_{os.urandom(3).hex()}.{ext}"

    s3 = _get_s3()
    if s3 and prefix.startswith("stitch_"):
        vk_id = prefix.split("_", 1)[1]
        upload_fn, _ = s3
        key = f"{vk_id}/{name}"
        content_type = "image/png" if is_png else "image/jpeg"
        return upload_fn(key, processed, content_type)

    path = os.path.join(config.UPLOADS_DIR, name)
    with open(path, "wb") as fh:
        fh.write(processed)
    return f"/api/uploads/{name}"


def remove_upload(url: str | None) -> None:
    if not url:
        return
    s3 = _get_s3()
    if s3 and url.startswith("http"):
        _, delete_fn = s3
        base = config.S3_PUBLIC_URL.rstrip("/") + "/"
        key = url[len(base):] if url.startswith(base) else url.rsplit("/", 1)[-1]
        delete_fn(key)
        return
    name = url.rsplit("/", 1)[-1]
    path = os.path.join(config.UPLOADS_DIR, name)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass

