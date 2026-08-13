from __future__ import annotations
import datetime
import json
from typing import Any, Optional

from db import SessionLocal
from models import Log


def _dump_details(details: Any) -> Optional[str]:
    if details is None:
        return None
    try:
        return json.dumps(details, ensure_ascii=False, default=str)
    except Exception:
        return str(details)


def record_log(
    source: str,
    level: str = "info",
    event: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    message: Optional[str] = None,
    details: Any = None,
    user_id: Optional[int] = None,
    client_ip: Optional[str] = None,
    session_factory=None,
) -> None:
    try:
        factory = session_factory or SessionLocal
        db = factory()
        try:
            db.add(Log(
                source=source, level=level, event=event, method=method, path=path,
                status_code=status_code, message=message,
                details=_dump_details(details), user_id=user_id, client_ip=client_ip,
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def cleanup_old_logs(db_session, days: int) -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    deleted = db_session.query(Log).filter(Log.created_at < cutoff).delete(synchronize_session=False)
    db_session.commit()
    return deleted


_LAST_CLEANUP: Optional[datetime.datetime] = None


def maybe_cleanup(db_session, days: int) -> None:
    global _LAST_CLEANUP
    now = datetime.datetime.utcnow()
    if _LAST_CLEANUP is not None and (now - _LAST_CLEANUP).total_seconds() < 3600:
        return
    _LAST_CLEANUP = now
    try:
        cleanup_old_logs(db_session, days)
    except Exception:
        pass
