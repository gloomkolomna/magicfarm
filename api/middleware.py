from __future__ import annotations
import json
import traceback

from starlette.requests import Request
from starlette.responses import Response

from services.auth import decode_access_token
from services.logging_svc import record_log

MAX_BODY_LOG = 1000


def _extract_user_id(request: Request) -> int | None:
    auth = request.headers.get("authorization") or ""
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        try:
            return decode_access_token(parts[1])
        except Exception:
            return None
    return None


def _extract_vk_id_from_body(body: bytes) -> int | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    params = payload.get("params")
    vk_id = params.get("vk_user_id") if isinstance(params, dict) else payload.get("vk_user_id")
    if vk_id is None:
        return None
    try:
        return int(vk_id)
    except (ValueError, TypeError):
        return None


def _extract_detail(raw: bytes) -> tuple[str | None, dict]:
    text = raw.decode("utf-8", errors="replace").strip()
    body_preview = text[:MAX_BODY_LOG] if text else None
    message: str | None = None
    if text:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict) and "detail" in payload:
                detail = payload["detail"]
                if isinstance(detail, str):
                    message = detail[:MAX_BODY_LOG] or None
                else:
                    message = json.dumps(detail, ensure_ascii=False)[:MAX_BODY_LOG] or None
            elif payload is not None:
                message = json.dumps(payload, ensure_ascii=False)[:MAX_BODY_LOG] or None
        except Exception:
            message = body_preview
    details = {"response_body": body_preview} if body_preview else {}
    return message, details


async def _read_body(response) -> bytes:
    body = b""
    iterator = response.body_iterator
    if hasattr(iterator, "__aiter__"):
        async for chunk in iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body += chunk
    else:
        for chunk in iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body += chunk
    return body


async def log_failed_requests(request: Request, call_next):
    path = request.url.path
    should_log = not path.startswith("/api/uploads")
    client_ip = request.client.host if request.client else None
    user_id = _extract_user_id(request) if should_log else None
    session_factory = getattr(request.app.state, "session_factory", None)

    body_vk_id = None
    if should_log and user_id is None and request.method == "POST" and path == "/api/auth/session":
        try:
            body_vk_id = _extract_vk_id_from_body(await request.body())
        except Exception:
            body_vk_id = None

    log_user_id = user_id if user_id is not None else body_vk_id

    try:
        response = await call_next(request)
    except Exception:
        if should_log:
            record_log(
                source="server", level="error", event="exception",
                method=request.method, path=path, message="Unhandled exception",
                details={"traceback": traceback.format_exc()},
                user_id=log_user_id, client_ip=client_ip, session_factory=session_factory,
            )
        raise

    if should_log:
        status_code = response.status_code
        if status_code >= 400:
            try:
                raw = await _read_body(response)
                message, details = _extract_detail(raw)
            except Exception:
                raw = b""
                message, details = None, {}
            copied = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ("content-length", "content-type")
            }
            response = Response(
                content=raw,
                status_code=status_code,
                headers=copied,
                media_type=response.media_type,
            )
            level = "error" if status_code >= 500 else "warn"
            record_log(
                source="server", level=level, event="http_request",
                method=request.method, path=path, status_code=status_code,
                message=message, details=details or None,
                user_id=log_user_id, client_ip=client_ip, session_factory=session_factory,
            )
    return response
