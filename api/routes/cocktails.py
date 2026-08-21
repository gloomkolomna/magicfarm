from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_location, require_role
from models import (
    COCKTAIL_REWARD_COINS, CocktailRecipe, CocktailRecipeItem, Ingredient, Inventory,
    PatientAnimal, Plant, Product, Remedy, Shaker, User, UserCard, UserIngredient, UserRemedy,
)
from routes.admin_catalog import _auto_code, _unique_code
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/cocktails", tags=["cocktails"], dependencies=[Depends(require_location("infirmary"))])

COCKTAIL_ITEM_KINDS = ("product", "plant", "ingredient", "remedy")


class CocktailItemOut(BaseModel):
    kind: str
    item_id: int
    name: str | None
    emoji: str | None
    image_url: str | None
    qty: int
    have: int = 0
    enough: bool = False


class CocktailRecipeOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    card_image_url: str | None
    patient_id: int | None
    patient_name: str | None
    reward_coins: int
    unlocked: bool
    items: list[CocktailItemOut]


class ShakerOut(BaseModel):
    id: int
    cocktail_recipe_id: int | None
    recipe_name: str | None
    status: str
    items: list[CocktailItemOut] = []


def _unlocked_patient_ids(user_id: int, db: Session) -> set[int]:
    return {
        c.patient_id for c in db.query(UserCard).filter(UserCard.user_id == user_id).all()
    }


def _item_meta_by_kind(db: Session, kind: str, item_id: int) -> str | None:
    if kind == "product":
        p = db.query(Product).filter(Product.id == item_id).first()
        return p.name if p else None
    if kind == "plant":
        p = db.query(Plant).filter(Plant.id == item_id).first()
        return p.name if p else None
    if kind == "ingredient":
        i = db.query(Ingredient).filter(Ingredient.id == item_id).first()
        return i.name if i else None
    if kind == "remedy":
        r = db.query(Remedy).filter(Remedy.id == item_id).first()
        return r.name if r else None
    return None


def _item_stock(item: CocktailRecipeItem, user_id: int, db: Session) -> int:
    if item.product_id is not None:
        inv = db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.product_id == item.product_id
        ).first()
        return (inv.qty or 0) if inv else 0
    if item.plant_id is not None:
        inv = db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.plant_id == item.plant_id
        ).first()
        return (inv.qty or 0) if inv else 0
    if item.ingredient_id is not None:
        ui = db.query(UserIngredient).filter(
            UserIngredient.user_id == user_id, UserIngredient.ingredient_id == item.ingredient_id
        ).first()
        return (ui.qty or 0) if ui else 0
    if item.remedy_id is not None:
        ur = db.query(UserRemedy).filter(
            UserRemedy.user_id == user_id, UserRemedy.remedy_id == item.remedy_id
        ).first()
        return (ur.qty or 0) if ur else 0
    return 0


def _item_out(item: CocktailRecipeItem, user_id: int, db: Session) -> CocktailItemOut:
    kind = "product"
    item_id = None
    name = None
    emoji = None
    image_url = None
    if item.product_id is not None:
        kind = "product"
        item_id = item.product_id
        if item.product is not None:
            name = item.product.name
            emoji = item.product.emoji
            image_url = item.product.image_url
    elif item.plant_id is not None:
        kind = "plant"
        item_id = item.plant_id
        if item.plant is not None:
            name = item.plant.name
            emoji = item.plant.emoji
            image_url = item.plant.image_harvested_url or item.plant.image_grown_url or item.plant.image_url
    elif item.ingredient_id is not None:
        kind = "ingredient"
        item_id = item.ingredient_id
        if item.ingredient is not None:
            name = item.ingredient.name
            image_url = item.ingredient.image_url
    elif item.remedy_id is not None:
        kind = "remedy"
        item_id = item.remedy_id
        if item.remedy is not None:
            name = item.remedy.name
            image_url = item.remedy.image_url
    have = _item_stock(item, user_id, db)
    return CocktailItemOut(
        kind=kind, item_id=item_id, name=name, emoji=emoji, image_url=image_url,
        qty=item.qty, have=have, enough=have >= item.qty,
    )


def _recipe_out(r: CocktailRecipe, user_id: int, db: Session, unlocked: bool) -> CocktailRecipeOut:
    return CocktailRecipeOut(
        id=r.id, code=r.code, name=r.name, description=r.description,
        image_url=r.image_url, card_image_url=r.card_image_url,
        patient_id=r.patient_id,
        patient_name=r.patient.name if r.patient else None,
        reward_coins=COCKTAIL_REWARD_COINS,
        unlocked=unlocked,
        items=[_item_out(i, user_id, db) for i in r.recipe_items],
    )


def _shaker_out(s: Shaker, db: Session) -> ShakerOut:
    recipe = s.recipe
    items = [_item_out(i, s.user_id, db) for i in (recipe.recipe_items if recipe else [])]
    return ShakerOut(
        id=s.id, cocktail_recipe_id=s.cocktail_recipe_id,
        recipe_name=recipe.name if recipe else None,
        status=s.status, items=items,
    )


@router.get("/recipes", response_model=list[CocktailRecipeOut])
def list_recipes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    unlocked_patients = _unlocked_patient_ids(user.vk_id, db)
    rows = db.query(CocktailRecipe).order_by(CocktailRecipe.id.asc()).all()
    return [
        _recipe_out(r, user.vk_id, db, r.patient_id is None or r.patient_id in unlocked_patients)
        for r in rows
    ]


@router.get("/shaker", response_model=ShakerOut | None)
def get_shaker(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Shaker).filter(
        Shaker.user_id == user.vk_id, Shaker.status != "done"
    ).first()
    return _shaker_out(s, db) if s is not None else None


class InstallShakerRequest(BaseModel):
    recipe_id: int


@router.post("/shaker", response_model=ShakerOut, status_code=status.HTTP_201_CREATED)
def install_shaker(
    req: InstallShakerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = db.query(CocktailRecipe).filter(CocktailRecipe.id == req.recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")

    unlocked_patients = _unlocked_patient_ids(user.vk_id, db)
    if recipe.patient_id is not None and recipe.patient_id not in unlocked_patients:
        patient = recipe.patient.name if recipe.patient else None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Рецепт ещё не открыт. Вылечите животное «{patient or recipe.patient_id}».",
        )

    if not recipe.recipe_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У рецепта нет ингредиентов")

    existing = db.query(Shaker).filter(
        Shaker.user_id == user.vk_id, Shaker.status != "done"
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Уже есть активный шейкер")

    s = Shaker(user_id=user.vk_id, cocktail_recipe_id=recipe.id, status="empty")
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Уже есть активный шейкер")
    db.refresh(s)
    return _shaker_out(s, db)


class MixOut(BaseModel):
    id: int
    recipe_name: str | None
    coins_earned: int
    coins_balance: int


def _grouped_items(recipe_items: list[CocktailRecipeItem]) -> list[tuple[str, int, int]]:
    totals: dict[tuple[str, int], int] = {}
    for item in recipe_items:
        if item.product_id is not None:
            key = ("product", item.product_id)
        elif item.plant_id is not None:
            key = ("plant", item.plant_id)
        elif item.ingredient_id is not None:
            key = ("ingredient", item.ingredient_id)
        elif item.remedy_id is not None:
            key = ("remedy", item.remedy_id)
        else:
            continue
        totals[key] = totals.get(key, 0) + (item.qty or 0)
    return [(kind, item_id, qty) for (kind, item_id), qty in totals.items()]


_STOCK_MODELS = {
    "product": (Inventory, "product_id"),
    "plant": (Inventory, "plant_id"),
    "ingredient": (UserIngredient, "ingredient_id"),
    "remedy": (UserRemedy, "remedy_id"),
}


def _stock_filter(kind: str, item_id: int, user_id: int):
    model, col_name = _STOCK_MODELS[kind]
    return (model.user_id == user_id, getattr(model, col_name) == item_id)


def _grouped_stock(db: Session, kind: str, item_id: int, user_id: int) -> int:
    model, col_name = _STOCK_MODELS[kind]
    row = db.query(model).filter(*_stock_filter(kind, item_id, user_id)).first()
    return (row.qty or 0) if row else 0


def _grouped_consume(db: Session, kind: str, item_id: int, user_id: int, qty: int) -> bool:
    model, _ = _STOCK_MODELS[kind]
    res = db.execute(
        update(model)
        .where(*_stock_filter(kind, item_id, user_id), model.qty >= qty)
        .values(qty=model.qty - qty)
    )
    return res.rowcount == 1


@router.post("/shaker/mix", response_model=MixOut)
def mix_cocktail(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Shaker).filter(
        Shaker.user_id == user.vk_id, Shaker.status != "done"
    ).first()
    if s is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Шейкер не установлен")

    recipe = s.recipe
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Рецепт не найден")

    grouped = _grouped_items(recipe.recipe_items)
    missing = []
    for kind, item_id, qty in grouped:
        if _grouped_stock(db, kind, item_id, user.vk_id) < qty:
            meta = _item_meta_by_kind(db, kind, item_id)
            missing.append(meta or f"#{item_id}")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не хватает ингредиентов: " + ", ".join(missing),
        )

    for kind, item_id, qty in grouped:
        if not _grouped_consume(db, kind, item_id, user.vk_id, qty):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не хватает ингредиентов, попробуйте ещё раз",
            )

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.coins = (u.coins or 0) + COCKTAIL_REWARD_COINS
    s.status = "done"
    db.commit()

    return MixOut(
        id=s.id, recipe_name=recipe.name,
        coins_earned=COCKTAIL_REWARD_COINS, coins_balance=u.coins or 0,
    )


# ── Admin ──

admin_router = APIRouter(prefix="/api/admin/cocktail-recipes", tags=["admin-cocktail-recipes"])


class CocktailItemIn(BaseModel):
    kind: str
    item_id: int
    qty: int = 1


class CocktailRecipeCreate(BaseModel):
    name: str
    description: str | None = None
    patient_id: int | None = None
    items: list[CocktailItemIn] = []


class CocktailRecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    patient_id: int | None = None
    items: list[CocktailItemIn] | None = None


class CocktailItemAdminOut(BaseModel):
    kind: str
    item_id: int
    name: str | None
    emoji: str | None
    image_url: str | None
    qty: int


class CocktailRecipeAdminOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    card_image_url: str | None
    patient_id: int | None
    patient_name: str | None
    items: list[CocktailItemAdminOut]


def _admin_item_out(item: CocktailRecipeItem) -> CocktailItemAdminOut:
    kind = "product"
    item_id = None
    name = None
    emoji = None
    image_url = None
    if item.product_id is not None:
        kind = "product"
        item_id = item.product_id
        if item.product is not None:
            name = item.product.name
            emoji = item.product.emoji
            image_url = item.product.image_url
    elif item.plant_id is not None:
        kind = "plant"
        item_id = item.plant_id
        if item.plant is not None:
            name = item.plant.name
            emoji = item.plant.emoji
            image_url = item.plant.image_harvested_url or item.plant.image_grown_url or item.plant.image_url
    elif item.ingredient_id is not None:
        kind = "ingredient"
        item_id = item.ingredient_id
        if item.ingredient is not None:
            name = item.ingredient.name
            image_url = item.ingredient.image_url
    elif item.remedy_id is not None:
        kind = "remedy"
        item_id = item.remedy_id
        if item.remedy is not None:
            name = item.remedy.name
            image_url = item.remedy.image_url
    return CocktailItemAdminOut(kind=kind, item_id=item_id, name=name, emoji=emoji, image_url=image_url, qty=item.qty)


def _admin_recipe_out(r: CocktailRecipe) -> CocktailRecipeAdminOut:
    return CocktailRecipeAdminOut(
        id=r.id, code=r.code, name=r.name, description=r.description,
        image_url=r.image_url, card_image_url=r.card_image_url,
        patient_id=r.patient_id,
        patient_name=r.patient.name if r.patient else None,
        items=[_admin_item_out(i) for i in r.recipe_items],
    )


def _resolve_item_kind(kind: str, item_id: int, db: Session) -> dict:
    if kind == "product":
        if db.query(Product).filter(Product.id == item_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Товар не найден")
        return {"product_id": item_id}
    if kind == "plant":
        if db.query(Plant).filter(Plant.id == item_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Растение не найдено")
        return {"plant_id": item_id}
    if kind == "ingredient":
        if db.query(Ingredient).filter(Ingredient.id == item_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ингредиент не найден")
        return {"ingredient_id": item_id}
    if kind == "remedy":
        if db.query(Remedy).filter(Remedy.id == item_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Лекарство не найдено")
        return {"remedy_id": item_id}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Тип должен быть одним из: {', '.join(COCKTAIL_ITEM_KINDS)}",
    )


def _validate_patient(patient_id: int | None, db: Session) -> None:
    if patient_id is not None and db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Животное не найдено")


def _set_items(recipe_id: int, items: list[CocktailItemIn], db: Session) -> None:
    merged: dict[tuple[str, int], int] = {}
    for it in items:
        if it.qty < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество должно быть не меньше 1")
        _resolve_item_kind(it.kind, it.item_id, db)
        key = (it.kind, it.item_id)
        merged[key] = merged.get(key, 0) + it.qty
    db.query(CocktailRecipeItem).filter(CocktailRecipeItem.cocktail_recipe_id == recipe_id).delete()
    for (kind, item_id), qty in merged.items():
        fields = _resolve_item_kind(kind, item_id, db)
        db.add(CocktailRecipeItem(cocktail_recipe_id=recipe_id, qty=qty, **fields))


@admin_router.get("", response_model=list[CocktailRecipeAdminOut])
def admin_list(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_admin_recipe_out(r) for r in db.query(CocktailRecipe).order_by(CocktailRecipe.id.asc()).all()]


@admin_router.post("", response_model=CocktailRecipeAdminOut, status_code=status.HTTP_201_CREATED)
def admin_create(
    req: CocktailRecipeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    _validate_patient(req.patient_id, db)
    code = _unique_code(_auto_code(req.name, "cocktail"), CocktailRecipe, db)
    r = CocktailRecipe(code=code, name=req.name.strip(), description=req.description, patient_id=req.patient_id)
    db.add(r)
    db.flush()
    _set_items(r.id, req.items, db)
    db.commit()
    db.refresh(r)
    return _admin_recipe_out(r)


@admin_router.put("/{recipe_id}", response_model=CocktailRecipeAdminOut)
def admin_update(
    recipe_id: int,
    req: CocktailRecipeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(CocktailRecipe).filter(CocktailRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        r.name = req.name.strip()
    if req.description is not None:
        r.description = req.description
    if req.patient_id is not None:
        _validate_patient(req.patient_id, db)
        r.patient_id = req.patient_id
    if req.items is not None:
        _set_items(r.id, req.items, db)
    db.commit()
    db.refresh(r)
    return _admin_recipe_out(r)


@admin_router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete(
    recipe_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(CocktailRecipe).filter(CocktailRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    remove_upload(r.image_url)
    remove_upload(r.card_image_url)
    db.delete(r)
    db.commit()
    return None


@admin_router.put("/{recipe_id}/image", response_model=CocktailRecipeAdminOut)
def admin_upload_image(
    recipe_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(CocktailRecipe).filter(CocktailRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    new_url = save_upload(image, f"cocktail_{r.id}", max_size=400)
    remove_upload(r.image_url)
    r.image_url = new_url
    db.commit()
    db.refresh(r)
    return _admin_recipe_out(r)


@admin_router.put("/{recipe_id}/card-image", response_model=CocktailRecipeAdminOut)
def admin_upload_card_image(
    recipe_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(CocktailRecipe).filter(CocktailRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    new_url = save_upload(image, f"cocktail_card_{r.id}", max_size=1200)
    remove_upload(r.card_image_url)
    r.card_image_url = new_url
    db.commit()
    db.refresh(r)
    return _admin_recipe_out(r)
