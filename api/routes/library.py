from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Recipe, User, UserRecipe

router = APIRouter(prefix="/api/library", tags=["library"])


class RecipeOut(BaseModel):
    id: int
    source_kind: str
    plant_id: int | None
    plant_name: str | None
    plant_emoji: str | None
    plant_image: str | None = None
    source_product_id: int | None
    source_product_name: str | None
    source_product_emoji: str | None
    source_product_image: str | None = None
    product_id: int
    product_name: str
    product_emoji: str | None
    product_image: str | None = None
    level: int
    status: str


def _recipe_to_out(r: Recipe, user_id: int, db: Session) -> RecipeOut:
    ur = db.query(UserRecipe).filter(
        UserRecipe.user_id == user_id, UserRecipe.recipe_id == r.id
    ).first()
    status_val = ur.status if ur else "locked"
    plant = r.plant if r.plant_id is not None else None
    source_product = r.source_product if r.source_product_id is not None else None
    plant_image = None
    if plant is not None:
        plant_image = plant.image_harvested_url or plant.image_url
    return RecipeOut(
        id=r.id,
        source_kind="animal_product" if r.source_product_id is not None else "plant",
        plant_id=r.plant_id,
        plant_name=plant.name if plant else None,
        plant_emoji=plant.emoji if plant else None,
        plant_image=plant_image,
        source_product_id=r.source_product_id,
        source_product_name=source_product.name if source_product else None,
        source_product_emoji=source_product.emoji if source_product else None,
        source_product_image=source_product.image_url if source_product else None,
        product_id=r.product_id,
        product_name=r.product.name, product_emoji=r.product.emoji,
        product_image=r.product.image_url,
        level=r.level, status=status_val,
    )


@router.get("", response_model=list[RecipeOut])
def list_recipes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Recipe)
        .filter(Recipe.source_product_id.is_(None))
        .order_by(Recipe.level.asc(), Recipe.id.asc())
        .all()
    )
    return [_recipe_to_out(r, user.vk_id, db) for r in rows]


@router.post("/{recipe_id}/study", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def start_study(
    recipe_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")

    if r.source_product_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Рецепты скотного двора не изучаются в библиотеке",
        )

    from routes.settings import get_user_study_norm

    study_norm = get_user_study_norm(user, r.level)
    if study_norm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сначала задайте нормы изучения рецептов в профиле (Настройки норм)",
        )

    existing = db.query(UserRecipe).filter(
        UserRecipe.user_id == user.vk_id, UserRecipe.recipe_id == recipe_id
    ).first()
    if existing is not None:
        if existing.status == "studied":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Рецепт уже изучен")
        if existing.status == "studying":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Рецепт уже изучается")

    ur = UserRecipe(user_id=user.vk_id, recipe_id=recipe_id, status="studying", required=study_norm)
    db.add(ur)
    db.commit()
    return _recipe_to_out(r, user.vk_id, db)


def complete_study(user_id: int, recipe_id: int, db: Session) -> None:
    ur = db.query(UserRecipe).filter(
        UserRecipe.user_id == user_id, UserRecipe.recipe_id == recipe_id
    ).first()
    if ur is not None and ur.status == "studying":
        ur.status = "studied"
        db.commit()
