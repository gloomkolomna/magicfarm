from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import LOCATION_CODES, StorySlide, User, UserDlcStoryView
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/story", tags=["story"])
admin_router = APIRouter(prefix="/api/admin/story", tags=["admin-story"])


class StorySlideOut(BaseModel):
    id: int
    image_url: str | None
    text: str | None
    sort_order: int
    location_code: str | None = None


class StorySlideCreate(BaseModel):
    text: str | None = None
    sort_order: int = 0
    location_code: str | None = None


class StorySlideUpdate(BaseModel):
    text: str | None = None
    sort_order: int | None = None
    location_code: str | None = None


def _slide_out(s: StorySlide) -> StorySlideOut:
    return StorySlideOut(
        id=s.id, image_url=s.image_url, text=s.text,
        sort_order=s.sort_order or 0, location_code=s.location_code,
    )


def _validate_location_code(code: str | None) -> str | None:
    if not code:
        return None
    if code not in LOCATION_CODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестная локация")
    return code


def _get_slide_or_404(slide_id: int, db: Session) -> StorySlide:
    s = db.query(StorySlide).filter(StorySlide.id == slide_id).first()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Слайд не найден")
    return s


@router.get("/slides", response_model=list[StorySlideOut])
def list_slides(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return [
        _slide_out(s)
        for s in db.query(StorySlide)
        .filter(StorySlide.location_code.is_(None))
        .order_by(StorySlide.sort_order.asc(), StorySlide.id.asc())
        .all()
    ]


class DlcStoryOut(BaseModel):
    slides: list[StorySlideOut]
    seen: bool = False


def _dlc_seen(user_id: int, location_code: str, db: Session) -> bool:
    return (
        db.query(UserDlcStoryView)
        .filter(
            UserDlcStoryView.user_id == user_id,
            UserDlcStoryView.location_code == location_code,
        )
        .first()
        is not None
    )


def _check_dlc_access(code: str, user: User, db: Session) -> None:
    from services.availability import location_lock_reason

    reason = location_lock_reason(code, user, db)
    if reason is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


@router.get("/dlc/{location_code}", response_model=DlcStoryOut)
def get_dlc_story(
    location_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = _validate_location_code(location_code)
    _check_dlc_access(code, user, db)
    slides = [
        _slide_out(s)
        for s in db.query(StorySlide)
        .filter(StorySlide.location_code == code)
        .order_by(StorySlide.sort_order.asc(), StorySlide.id.asc())
        .all()
    ]
    return DlcStoryOut(slides=slides, seen=_dlc_seen(user.vk_id, code, db))


class SeenOut(BaseModel):
    ok: bool = True


@router.post("/seen", response_model=SeenOut)
def mark_story_seen(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    if u is not None:
        u.story_seen = True
    else:
        user.story_seen = True
        db.add(user)
    db.commit()
    return SeenOut()


@router.post("/dlc/{location_code}/seen", response_model=SeenOut)
def mark_dlc_story_seen(
    location_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = _validate_location_code(location_code)
    _check_dlc_access(code, user, db)
    existing = db.query(UserDlcStoryView).filter(
        UserDlcStoryView.user_id == user.vk_id,
        UserDlcStoryView.location_code == code,
    ).first()
    if existing is None:
        db.add(UserDlcStoryView(user_id=user.vk_id, location_code=code))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return SeenOut()


@admin_router.get("/slides", response_model=list[StorySlideOut])
def admin_list_slides(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [
        _slide_out(s)
        for s in db.query(StorySlide).order_by(StorySlide.location_code.asc(), StorySlide.sort_order.asc(), StorySlide.id.asc()).all()
    ]


class DlcLocationOut(BaseModel):
    code: str
    name: str


@admin_router.get("/dlc-locations", response_model=list[DlcLocationOut])
def admin_list_dlc_locations(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from models import LOCATION_NAMES

    return [
        DlcLocationOut(code=code, name=LOCATION_NAMES.get(code, code))
        for code in LOCATION_CODES
    ]


@admin_router.post("/slides", response_model=StorySlideOut, status_code=status.HTTP_201_CREATED)
def admin_create_slide(
    req: StorySlideCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    s = StorySlide(text=req.text, sort_order=req.sort_order or 0,
                   location_code=_validate_location_code(req.location_code))
    db.add(s)
    db.commit()
    db.refresh(s)
    return _slide_out(s)


@admin_router.put("/slides/{slide_id}", response_model=StorySlideOut)
def admin_update_slide(
    slide_id: int,
    req: StorySlideUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    s = _get_slide_or_404(slide_id, db)
    if req.text is not None:
        s.text = req.text
    if req.sort_order is not None:
        s.sort_order = req.sort_order
    if req.location_code is not None:
        s.location_code = _validate_location_code(req.location_code)
    db.commit()
    db.refresh(s)
    return _slide_out(s)


@admin_router.put("/slides/{slide_id}/image", response_model=StorySlideOut)
def admin_upload_slide_image(
    slide_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    s = _get_slide_or_404(slide_id, db)
    new_url = save_upload(file, f"story_{s.id}", max_size=1920)
    remove_upload(s.image_url)
    s.image_url = new_url
    db.commit()
    db.refresh(s)
    return _slide_out(s)


@admin_router.delete("/slides/{slide_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_slide(
    slide_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    s = _get_slide_or_404(slide_id, db)
    remove_upload(s.image_url)
    db.delete(s)
    db.commit()
    return None
