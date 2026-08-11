from starlette.requests import Request

from db import SessionLocal
from models import RequestLog


async def log_failed_requests(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        try:
            # SessionFactory может быть переопределён в тестах через app.state.
            session_factory = getattr(request.app.state, "session_factory", None) or SessionLocal
            db = session_factory()
            log = RequestLog(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                client_ip=request.client.host if request.client else None,
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception:
            pass
    return response
