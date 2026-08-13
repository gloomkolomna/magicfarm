from __future__ import annotations
import traceback

from starlette.requests import Request

from services.auth import decode_access_token
from services.logging_svc import record_log


def _extract_user_id(request: Request) -> int | None:
    auth = request.headers.get("authorization") or ""
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        try:
            return decode_access_token(parts[1])
        except Exception:
            return None
    return None


async def log_failed_requests(request: Request, call_next):
    path = request.url.path
    should_log = not path.startswith("/api/uploads")
    client_ip = request.client.host if request.client else None
    user_id = _extract_user_id(request) if should_log else None
    session_factory = getattr(request.app.state, "session_factory", None)

    try:
        response = await call_next(request)
    except Exception:
        if should_log:
            record_log(
                source="server", level="error", event="exception",
                method=request.method, path=path, message="Unhandled exception",
                details={"traceback": traceback.format_exc()},
                user_id=user_id, client_ip=client_ip, session_factory=session_factory,
            )
        raise

    if should_log:
        status_code = response.status_code
        level = "error" if status_code >= 500 else ("warn" if status_code >= 400 else "info")
        record_log(
            source="server", level=level, event="http_request",
            method=request.method, path=path, status_code=status_code,
            user_id=user_id, client_ip=client_ip, session_factory=session_factory,
        )
    return response
