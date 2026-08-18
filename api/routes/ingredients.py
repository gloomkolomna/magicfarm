from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Ingredient, User, UserIngredient
from routes.admin_catalog import _auto_code, _unique_code
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api", tags=["apothecary"])
admin_router = APIRouter(prefix="/api/admin/ingredients", tags=["admin-ingredients"])


class IngredientOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    sort_order: int


class ApothecaryItemOut(BaseModel):
    ingredient_id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    qty: int


def _ingredient_out(i: Ingredient) -> IngredientOut:
    return IngredientOut(
        id=i.id, code=i.code, name=i.name,
        description=i.description, image_url=i.image_url, sort_order=i.sort_order,
    )


def _apothecary_item_out(ui: UserIngredient) -> ApothecaryItemOut:
    i = ui.ingredient
    return ApothecaryItemOut(
        ingredient_id=i.id, code=i.code, name=i.name,
        description=i.description, image_url=i.image_url, qty=ui.qty,
    )


@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Ingredient).order_by(
        Ingredient.sort_order.asc(), Ingredient.id.asc()
    ).all()
    return [_ingredient_out(i) for i in rows]


@router.get("/apothecary", response_model=list[ApothecaryItemOut])
def get_apothecary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserIngredient).join(
        Ingredient, UserIngredient.ingredient_id == Ingredient.id
    ).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.qty > 0
    ).order_by(
        Ingredient.sort_order.asc(), Ingredient.id.asc()
    ).all()
    result = []
    for ui in rows:
        result.append(_apothecary_item_out(ui))
    return result


class IngredientCreate(BaseModel):
    name: str
    description: str | None = None
    sort_order: int = 0


class IngredientUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None


@admin_router.get("", response_model=list[IngredientOut])
def admin_list(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(Ingredient).order_by(
        Ingredient.sort_order.asc(), Ingredient.id.asc()
    ).all()
    return [_ingredient_out(i) for i in rows]


@admin_router.post("", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
def admin_create(
    req: IngredientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    code = _unique_code(_auto_code(req.name, "ingredient"), Ingredient, db)
    i = Ingredient(
        code=code, name=req.name.strip(),
        description=req.description, sort_order=req.sort_order,
    )
    db.add(i)
    db.commit()
    db.refresh(i)
    return _ingredient_out(i)


@admin_router.put("/{ingredient_id}", response_model=IngredientOut)
def admin_update(
    ingredient_id: int,
    req: IngredientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    i = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if i is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ингредиент не найден")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        i.name = req.name.strip()
    if req.description is not None:
        i.description = req.description
    if req.sort_order is not None:
        i.sort_order = req.sort_order
    db.commit()
    db.refresh(i)
    return _ingredient_out(i)


@admin_router.put("/{ingredient_id}/image", response_model=IngredientOut)
def admin_upload_image(
    ingredient_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    i = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if i is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ингредиент не найден")
    remove_upload(i.image_url)
    i.image_url = save_upload(image, f"ingredient_{i.id}", max_size=400)
    db.commit()
    db.refresh(i)
    return _ingredient_out(i)


@admin_router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete(
    ingredient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    i = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if i is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ингредиент не найден")
    remove_upload(i.image_url)
    db.delete(i)
    db.commit()
    return None
