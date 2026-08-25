from __future__ import annotations
import io
import os
import time

from fastapi import HTTPException, UploadFile, status

import config

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

_S3 = None


def _get_s3():
    global _S3
    if _S3 is None and config.S3_ENABLED:
        import services.s3_storage as _mod
        _S3 = _mod
    return _S3


def _read_with_limit(upload: UploadFile, allow_video: bool = False) -> tuple[bytes, bool]:
    ctype = (upload.content_type or "").lower()
    is_video = ctype.startswith("video/")
    if is_video:
        if not allow_video:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Видео не поддерживается")
    elif not ctype.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл должен быть изображением")

    limit = config.UPLOAD_VIDEO_MAX_BYTES if is_video else config.UPLOAD_MAX_BYTES
    buf = bytearray()
    while True:
        chunk = upload.file.read(64 * 1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > limit:
            if is_video:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Файл слишком большой (макс. {limit // (1024 * 1024)} МБ)",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Файл слишком большой (макс. {limit // 1024} КБ)",
            )
    return bytes(buf), is_video


def _process(buf: bytes, max_size: int | None) -> tuple[bytes, bool]:
    if max_size is None:
        return buf, True
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(buf))
        img.load()
    except (OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось прочитать изображение: файл повреждён или формат не поддерживается. "
                   "Пересохраните фото как JPG или PNG и попробуйте снова",
        )

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


class _VideoTooLarge(Exception):
    pass


class _LimitedStream:
    def __init__(self, fh, limit: int):
        self._fh = fh
        self._limit = limit
        self.count = 0

    def read(self, size: int = -1):
        chunk = self._fh.read(size)
        if chunk:
            self.count += len(chunk)
            if self.count > self._limit:
                raise _VideoTooLarge()
        return chunk


_VIDEO_DEFAULT_TYPE = "video/mp4"


def _remove_silent(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _save_video(upload: UploadFile, prefix: str) -> str:
    limit = config.UPLOAD_VIDEO_MAX_BYTES
    ext = os.path.splitext(upload.filename or "")[1].lower().lstrip(".") or "mp4"
    name = f"{prefix}_{int(time.time())}_{os.urandom(3).hex()}.{ext}"
    reader = _LimitedStream(upload.file, limit)
    path = os.path.join(config.UPLOADS_DIR, name)
    s3 = _get_s3()
    try:
        if s3:
            ctype = (upload.content_type or "").lower()
            if not ctype.startswith("video/"):
                ctype = _VIDEO_DEFAULT_TYPE
            return s3.upload_stream(f"videos/{name}", reader, ctype)
        with open(path, "wb") as fh:
            while True:
                chunk = reader.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
        return f"/api/uploads/{name}"
    except _VideoTooLarge:
        _remove_silent(path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Файл слишком большой (макс. {limit // (1024 * 1024)} МБ)",
        )


def save_upload(upload: UploadFile, prefix: str, max_size: int | None = None, allow_video: bool = False) -> str:
    ctype = (upload.content_type or "").lower()
    if allow_video and ctype.startswith("video/"):
        return _save_video(upload, prefix)
    buf, _ = _read_with_limit(upload, allow_video=allow_video)
    processed, is_png = _process(buf, max_size)
    if max_size is not None:
        ext = "png" if is_png else "jpg"
    else:
        ext = os.path.splitext(upload.filename or "")[1].lower().lstrip(".") or "png"
    name = f"{prefix}_{int(time.time())}_{os.urandom(3).hex()}.{ext}"

    s3 = _get_s3()
    if s3 and prefix.startswith("stitch_"):
        vk_id = prefix.split("_", 1)[1]
        content_type = "image/png" if is_png else "image/jpeg"
        return s3.upload_bytes(f"{vk_id}/{name}", processed, content_type)

    path = os.path.join(config.UPLOADS_DIR, name)
    with open(path, "wb") as fh:
        fh.write(processed)
    return f"/api/uploads/{name}"


THUMB_MAX_SIZE = 300


def save_stitch_photo(upload: UploadFile, vk_id: int, kind: str) -> tuple[str, str | None]:
    buf, _ = _read_with_limit(upload)
    processed, is_png = _process(buf, max_size=1280)
    thumb, thumb_is_png = _process(buf, max_size=THUMB_MAX_SIZE)
    stamp = int(time.time())
    name = f"stitch_{vk_id}_{kind}_{stamp}_{os.urandom(3).hex()}.{'png' if is_png else 'jpg'}"
    thumb_name = f"thumb_stitch_{vk_id}_{kind}_{stamp}_{os.urandom(3).hex()}.{'png' if thumb_is_png else 'jpg'}"
    s3 = _get_s3()
    if s3:
        ctype = "image/png" if is_png else "image/jpeg"
        url = s3.upload_bytes(f"{vk_id}/{name}", processed, ctype)
        thumb_url = s3.upload_bytes(f"{vk_id}/{thumb_name}", thumb, "image/png" if thumb_is_png else "image/jpeg")
        return url, thumb_url
    path = os.path.join(config.UPLOADS_DIR, name)
    with open(path, "wb") as fh:
        fh.write(processed)
    thumb_path = os.path.join(config.UPLOADS_DIR, thumb_name)
    with open(thumb_path, "wb") as fh:
        fh.write(thumb)
    return f"/api/uploads/{name}", f"/api/uploads/{thumb_name}"


def remove_upload(url: str | None) -> None:
    if not url:
        return
    s3 = _get_s3()
    if s3 and url.startswith("http"):
        base = config.S3_PUBLIC_URL.rstrip("/") + "/"
        key = url[len(base):] if url.startswith(base) else url.rsplit("/", 1)[-1]
        s3.delete_object(key)
        return
    name = url.rsplit("/", 1)[-1]
    path = os.path.join(config.UPLOADS_DIR, name)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass

