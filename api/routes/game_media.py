from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import require_role
from models import GameMedia, User
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/admin/game-media", tags=["admin-game-media"])
public_router = APIRouter(prefix="/api/game-media", tags=["game-media"])


class GameMediaOut(BaseModel):
    id: int
    code: str
    kind: str
    url: str | None

    model_config = {"from_attributes": True}


class GameMediaCreate(BaseModel):
    code: str
    kind: str


class GameMediaUpdate(BaseModel):
    code: str | None = None
    kind: str | None = None


def _gm_out(gm: GameMedia) -> GameMediaOut:
    return GameMediaOut(id=gm.id, code=gm.code, kind=gm.kind, url=gm.url)


@router.get("", response_model=list[GameMediaOut])
def list_media(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_gm_out(gm) for gm in db.query(GameMedia).order_by(GameMedia.id.asc()).all()]


@router.post("", response_model=GameMediaOut, status_code=status.HTTP_201_CREATED)
def create_media(
    req: GameMediaCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код обязателен")
    if db.query(GameMedia).filter(GameMedia.code == code).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Медиа с кодом '{code}' уже существует")
    gm = GameMedia(code=code, kind=req.kind)
    db.add(gm)
    db.commit()
    db.refresh(gm)
    return _gm_out(gm)


@router.put("/{media_id}", response_model=GameMediaOut)
def update_media(
    media_id: int,
    req: GameMediaUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    gm = db.query(GameMedia).filter(GameMedia.id == media_id).first()
    if gm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Медиа не найдено")
    if req.code is not None:
        code = req.code.strip()
        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код обязателен")
        existing = db.query(GameMedia).filter(GameMedia.code == code, GameMedia.id != media_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Медиа с кодом '{code}' уже существует")
        gm.code = code
    if req.kind is not None:
        gm.kind = req.kind
    db.commit()
    db.refresh(gm)
    return _gm_out(gm)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    gm = db.query(GameMedia).filter(GameMedia.id == media_id).first()
    if gm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Медиа не найдено")
    remove_upload(gm.url)
    db.delete(gm)
    db.commit()
    return None


@router.put("/{media_id}/upload", response_model=GameMediaOut)
def upload_media_file(
    media_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    gm = db.query(GameMedia).filter(GameMedia.id == media_id).first()
    if gm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Медиа не найдено")
    remove_upload(gm.url)
    gm.url = save_upload(file, f"gm_{gm.code}", allow_video=True)
    db.commit()
    db.refresh(gm)
    return _gm_out(gm)


@public_router.get("", response_model=list[GameMediaOut])
def list_public_media(
    db: Session = Depends(get_db),
):
    return [_gm_out(gm) for gm in db.query(GameMedia).order_by(GameMedia.id.asc()).all()]


@public_router.get("/{code}", response_model=GameMediaOut)
def get_media_by_code(
    code: str,
    db: Session = Depends(get_db),
):
    gm = db.query(GameMedia).filter(GameMedia.code == code).first()
    if gm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Медиа не найдено")
    return _gm_out(gm)
