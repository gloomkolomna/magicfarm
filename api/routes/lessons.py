from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Lesson, User
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/lessons", tags=["lessons"])
admin_router = APIRouter(prefix="/api/admin/lessons", tags=["admin-lessons"])


class LessonOut(BaseModel):
    id: int
    title: str
    description: str | None
    video_url: str | None
    image_url: str | None
    sort_order: int


class LessonCreate(BaseModel):
    title: str
    description: str | None = None
    sort_order: int = 0


class LessonUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    sort_order: int | None = None


def _lesson_out(l: Lesson) -> LessonOut:
    return LessonOut(
        id=l.id, title=l.title, description=l.description,
        video_url=l.video_url, image_url=l.image_url, sort_order=l.sort_order or 0,
    )


def _get_lesson_or_404(lesson_id: int, db: Session) -> Lesson:
    l = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Урок не найден")
    return l


@router.get("", response_model=list[LessonOut])
def list_lessons(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return [
        _lesson_out(l)
        for l in db.query(Lesson).order_by(Lesson.sort_order.asc(), Lesson.id.asc()).all()
    ]


@admin_router.get("", response_model=list[LessonOut])
def admin_list_lessons(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [
        _lesson_out(l)
        for l in db.query(Lesson).order_by(Lesson.sort_order.asc(), Lesson.id.asc()).all()
    ]


@admin_router.post("", response_model=LessonOut, status_code=status.HTTP_201_CREATED)
def admin_create_lesson(
    req: LessonCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    l = Lesson(title=title, description=req.description, sort_order=req.sort_order or 0)
    db.add(l)
    db.commit()
    db.refresh(l)
    return _lesson_out(l)


@admin_router.put("/{lesson_id}", response_model=LessonOut)
def admin_update_lesson(
    lesson_id: int,
    req: LessonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    l = _get_lesson_or_404(lesson_id, db)
    if req.title is not None:
        title = req.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        l.title = title
    if req.description is not None:
        l.description = req.description
    if req.sort_order is not None:
        l.sort_order = req.sort_order
    db.commit()
    db.refresh(l)
    return _lesson_out(l)


@admin_router.put("/{lesson_id}/video", response_model=LessonOut)
def admin_upload_lesson_video(
    lesson_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    l = _get_lesson_or_404(lesson_id, db)
    remove_upload(l.video_url)
    l.video_url = save_upload(file, f"lesson_{l.id}", allow_video=True)
    db.commit()
    db.refresh(l)
    return _lesson_out(l)


@admin_router.put("/{lesson_id}/image", response_model=LessonOut)
def admin_upload_lesson_image(
    lesson_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    l = _get_lesson_or_404(lesson_id, db)
    remove_upload(l.image_url)
    l.image_url = save_upload(file, f"lesson_{l.id}", max_size=1200)
    db.commit()
    db.refresh(l)
    return _lesson_out(l)


@admin_router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    l = _get_lesson_or_404(lesson_id, db)
    remove_upload(l.video_url)
    remove_upload(l.image_url)
    db.delete(l)
    db.commit()
    return None
