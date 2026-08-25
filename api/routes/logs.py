from __future__ import annotations
import datetime
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

import config
from db import get_db
from deps import get_current_user, require_role
from models import Log, User
from services.logging_svc import maybe_cleanup

router = APIRouter(prefix="/api", tags=["logs"])


class VkLogRequest(BaseModel):
    level: str = "info"
    event: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Any] = None


@router.post("/logs/vk", status_code=status.HTTP_201_CREATED)
def report_vk_log(
    req: VkLogRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.level not in ("warn", "error"):
        return {"status": "ok"}
    details_json = None
    if req.details is not None:
        try:
            details_json = json.dumps(req.details, ensure_ascii=False, default=str)
        except Exception:
            details_json = str(req.details)
    db.add(Log(
        source="vk", level=req.level, event=req.event, message=req.message,
        details=details_json, user_id=user.vk_id,
    ))
    db.commit()
    return {"status": "ok"}


class LogOut(BaseModel):
    id: int
    source: str
    level: str
    event: Optional[str]
    method: Optional[str]
    path: Optional[str]
    status_code: Optional[int]
    message: Optional[str]
    details: Optional[str]
    user_id: Optional[int]
    client_ip: Optional[str]
    created_at: datetime.datetime


@router.get("/admin/logs", response_model=list[LogOut])
def list_logs(
    response: Response,
    source: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    response.headers["Cache-Control"] = "no-store"
    maybe_cleanup(db, config.LOG_RETENTION_DAYS)
    query = db.query(Log)
    if source:
        query = query.filter(Log.source == source)
    if level:
        query = query.filter(Log.level == level)
    if user_id is not None:
        query = query.filter(Log.user_id == user_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Log.message.ilike(like), Log.path.ilike(like), Log.event.ilike(like),
        ))
    rows = query.order_by(Log.id.desc()).offset(offset).limit(limit).all()
    return rows


@router.delete("/admin/logs", status_code=status.HTTP_204_NO_CONTENT)
def clear_logs(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    db.query(Log).delete(synchronize_session=False)
    db.commit()
    return None
