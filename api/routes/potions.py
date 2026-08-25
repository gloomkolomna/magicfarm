from __future__ import annotations
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_location, require_role
from models import BreweryZone, Cauldron, CauldronSlot, Field, FieldPotionRecipe, Inventory, Plant, PotionRecipe, Product, User, UserPotion
from services.achievements import check_and_award
from services.potion_bonuses import CONDITIONAL_BONUSES, INSTANT_BONUSES
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/potions", tags=["potions"], dependencies=[Depends(require_location("brewery"))])

POTION_BONUS_LABELS = {
    "double_garden_harvest": "×2 урожай с грядки",
    "double_orchard_harvest": "×2 урожай из сада",
    "double_animal_product": "×2 продукция животного",
    "skip_plant_stitch": "Растение без отшива нормы",
    "early_level_up": "+1 уровень маршрутного листа",
    "double_order_reward": "×2 награда за заказ",
    "free_pet": "Бесплатный питомец",
    "extra_barnyard_slot": "+1 загон зверо-двора",
    "bonus_sewing_product": "+1 товар портнихи",
    "bonus_workshop_product": "+1 товар мастерской",
    "bonus_alchemy_product": "+1 товар зельеварения",
    "skip_animal_stitch": "Животное без отшива нормы",
    "unlock_garden_l3": "Грядки 3 уровня",
    "unlock_orchard_l3": "Сады 3 уровня",
    "partial_order": "Неполное выполнение заказа",
}


POTION_BONUS_HINTS = {
    "double_garden_harvest": "Сработает автоматически при следующем сборе урожая с грядки",
    "double_orchard_harvest": "Сработает автоматически при следующем сборе урожая в саду",
    "double_animal_product": "Сработает автоматически при следующем получении продукции животного",
    "skip_plant_stitch": "Сработает автоматически при следующей посадке — растение вырастет сразу, без отшива нормы",
    "skip_animal_stitch": "Сработает автоматически при установке следующего животного — без отшива нормы",
    "double_order_reward": "Сработает автоматически при выполнении следующего заказа — награда ×2",
    "partial_order": "Сработает автоматически при выполнении следующего заказа — хватит и части товара",
    "bonus_sewing_product": "Сработает автоматически при следующем отчёте по крафту товара портнихи — +1 товар",
    "bonus_workshop_product": "Сработает автоматически при следующем отчёте по крафту товара мастерской — +1 товар",
    "bonus_alchemy_product": "Сработает автоматически при следующем отчёте по крафту товара зельеварения — +1 товар",
    "free_pet": "Применяется сразу при активации",
    "early_level_up": "Применяется сразу при активации",
    "extra_barnyard_slot": "Применяется сразу при активации",
    "unlock_garden_l3": "Применяется сразу при активации",
    "unlock_orchard_l3": "Применяется сразу при активации",
}


def _bonus_label(code: str | None) -> str | None:
    if not code:
        return None
    return POTION_BONUS_LABELS.get(code, code)


def _bonus_hint(code: str | None) -> str | None:
    if not code:
        return None
    return POTION_BONUS_HINTS.get(code)


class PotionRecipeOut(BaseModel):
    id: int
    code: str
    name: str
    level: str
    ingredient_slots: list[str]
    bonus_code: str | None
    reward_coins: int
    description: str | None
    image_url: str | None
    card_image_url: str | None = None
    unlocked: bool = True


RECIPE_LEVEL_ORDER = ("green", "blue", "violet")


def _unlocked_levels(db: Session, user: User) -> set[str]:
    brewed = {
        up.potion_recipe_id
        for up in db.query(UserPotion).filter(UserPotion.user_id == user.vk_id).all()
    }
    by_level: dict[str, list[PotionRecipe]] = {}
    for r in db.query(PotionRecipe).all():
        by_level.setdefault(r.level, []).append(r)
    unlocked: set[str] = set()
    for i, lv in enumerate(RECIPE_LEVEL_ORDER):
        if i == 0:
            unlocked.add(lv)
            continue
        prev_recipes = by_level.get(RECIPE_LEVEL_ORDER[i - 1], [])
        if prev_recipes and all(r.id in brewed for r in prev_recipes):
            unlocked.add(lv)
    return unlocked


def _recipe_out(r: PotionRecipe, unlocked: bool = True) -> PotionRecipeOut:
    slots = json.loads(r.ingredient_slots) if r.ingredient_slots else []
    return PotionRecipeOut(
        id=r.id, code=r.code, name=r.name, level=r.level,
        ingredient_slots=slots, bonus_code=r.bonus_code,
        reward_coins=r.reward_coins, description=r.description, image_url=r.image_url,
        card_image_url=r.card_image_url,
        unlocked=unlocked,
    )


class CauldronOut(BaseModel):
    id: int
    recipe_id: int | None
    recipe_name: str | None
    field_id: int | None = None
    field_name: str | None = None
    material: str
    capacity: int
    status: str
    slots: list[dict]
    image_url: str | None = None
    created_at: str | None = None


class UserPotionOut(BaseModel):
    id: int
    potion_recipe_id: int
    potion_name: str
    bonus_code: str | None
    bonus_description: str | None
    when_fires: str | None = None
    description: str | None
    image_url: str | None
    activated: bool
    used: bool = False
    acquired_at: str | None


# ── Recipe list ──

@router.get("/recipes", response_model=list[PotionRecipeOut])
def list_recipes(
    level: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(PotionRecipe).order_by(PotionRecipe.id.asc())
    if level is not None:
        q = q.filter(PotionRecipe.level == level)
    unlocked = _unlocked_levels(db, user)
    return [_recipe_out(r, r.level in unlocked) for r in q.limit(100).all()]


# ── Cauldrons ──

class CreateCauldronRequest(BaseModel):
    recipe_id: int
    field_id: int | None = None


def _check_field_level_gate(field: Field, user: User, db: Session) -> None:
    reason = brewery_field_lock_reason(field, user, db)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )


BREWERY_LEVEL_TITLES = {"green": "🟢 простые", "blue": "🔵 средние", "violet": "🟣 сложные"}


def brewery_field_lock_reason(field: Field, user: User, db: Session) -> str | None:
    """Почему зельеварня закрыта: пока не сварены все зелья предыдущего уровня.

    None — открыта (в т.ч. для админов и полей без привязанных рецептов).
    """
    if user is not None and user.role == "admin":
        return None
    levels = {
        r.level
        for r in db.query(PotionRecipe)
        .join(FieldPotionRecipe, FieldPotionRecipe.recipe_id == PotionRecipe.id)
        .filter(FieldPotionRecipe.field_id == field.id)
        .all()
    }
    if not levels:
        return None
    unlocked = _unlocked_levels(db, user)
    for i, lv in enumerate(RECIPE_LEVEL_ORDER):
        if lv in levels and lv not in unlocked:
            if i == 0:
                return "Сварите все зелья этого уровня, чтобы открыть зельеварню"
            prev = RECIPE_LEVEL_ORDER[i - 1]
            return f"Сварите все {BREWERY_LEVEL_TITLES.get(prev, prev)} зелья, чтобы открыть эту зельеварню"
    return None


def _resolve_cauldron_field(req: CreateCauldronRequest, recipe: PotionRecipe, user: User, db: Session) -> int | None:
    if req.field_id is not None:
        field = db.query(Field).filter(Field.id == req.field_id).first()
        if field is None or field.field_kind != "brewery":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Котёл можно установить только в зельеварне",
            )
        bound = db.query(FieldPotionRecipe).filter(
            FieldPotionRecipe.field_id == field.id, FieldPotionRecipe.recipe_id == recipe.id
        ).first()
        if bound is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это зелье не привязано к данной зельеварне",
            )
        _check_field_level_gate(field, user, db)
        return field.id

    binding = db.query(FieldPotionRecipe).filter(
        FieldPotionRecipe.recipe_id == recipe.id
    ).order_by(FieldPotionRecipe.field_id.asc()).first()
    if binding is None:
        return None
    field = db.query(Field).filter(Field.id == binding.field_id).first()
    if field is not None:
        _check_field_level_gate(field, user, db)
    return binding.field_id


@router.post("/cauldrons", response_model=CauldronOut, status_code=status.HTTP_201_CREATED)
def create_cauldron(
    req: CreateCauldronRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == req.recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")

    if recipe.level not in _unlocked_levels(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Рецепты этого уровня ещё не открыты. Сварите все зелья предыдущего уровня.",
        )

    field_id = _resolve_cauldron_field(req, recipe, user, db)

    existing = db.query(Cauldron).filter(
        Cauldron.user_id == user.vk_id, Cauldron.status != "done",
        Cauldron.field_id == field_id,
    ).first()
    if existing is not None:
        detail = "В этой зельеварне уже стоит котёл" if field_id is not None else "Уже есть активный котёл"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    slots = json.loads(recipe.ingredient_slots) if recipe.ingredient_slots else []
    capacity = len(slots)
    material = "tin"
    if capacity >= 6:
        material = "gold"
    elif capacity >= 5:
        material = "silver"

    c = Cauldron(user_id=user.vk_id, recipe_id=recipe.id, field_id=field_id, material=material,
                 capacity=capacity, status="empty")
    db.add(c)
    db.flush()

    for i, slot_type in enumerate(slots):
        db.add(CauldronSlot(cauldron_id=c.id, slot_index=i, item_type=slot_type, item_id=None))

    db.commit()
    db.refresh(c)

    return _cauldron_detail(c, db)


@router.get("/cauldrons/active", response_model=list[CauldronOut])
def get_active_cauldrons(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Cauldron).filter(
        Cauldron.user_id == user.vk_id, Cauldron.status != "done"
    ).order_by(Cauldron.created_at.asc(), Cauldron.id.asc()).all()
    return [_cauldron_detail(c, db) for c in rows]


@router.get("/cauldrons/{cauldron_id}", response_model=CauldronOut)
def get_cauldron(
    cauldron_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Cauldron).filter(Cauldron.id == cauldron_id, Cauldron.user_id == user.vk_id).first()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Котёл не найден")
    return _cauldron_detail(c, db)


def _cauldron_zone_image(db: Session, field_id: int | None) -> str | None:
    if field_id is None:
        return None
    z = db.query(BreweryZone).filter(
        BreweryZone.field_id == field_id, BreweryZone.zone_kind == "cauldron"
    ).order_by(BreweryZone.id.asc()).first()
    return z.image_url if z else None


def _cauldron_detail(c: Cauldron, db: Session) -> CauldronOut:
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == c.recipe_id).first() if c.recipe_id else None
    field = db.query(Field).filter(Field.id == c.field_id).first() if c.field_id else None
    slots = db.query(CauldronSlot).filter(CauldronSlot.cauldron_id == c.id).order_by(CauldronSlot.slot_index).all()
    slot_data = []
    for s in slots:
        d = {"slot_index": s.slot_index, "item_type": s.item_type, "item_id": s.item_id,
             "item_name": None, "item_emoji": None, "item_image": None}
        if s.item_id is not None:
            if s.item_type in PLANT_SLOT_TYPES:
                plant = db.query(Plant).filter(Plant.id == s.item_id).first()
                if plant is not None:
                    d["item_name"] = plant.name
                    d["item_emoji"] = plant.emoji
                    d["item_image"] = plant.image_harvested_url or plant.image_grown_url or plant.image_url
            else:
                prod = db.query(Product).filter(Product.id == s.item_id).first()
                if prod is not None:
                    d["item_name"] = prod.name
                    d["item_emoji"] = prod.emoji
                    d["item_image"] = prod.image_url
        slot_data.append(d)
    return CauldronOut(
        id=c.id, recipe_id=c.recipe_id, recipe_name=recipe.name if recipe else None,
        field_id=c.field_id, field_name=field.name if field else None,
        material=c.material, capacity=c.capacity, status=c.status, slots=slot_data,
        image_url=_cauldron_zone_image(db, c.field_id),
        created_at=c.created_at.isoformat() if c.created_at else None,
    )


# ── Slot warehouse filter ──

PLANT_SLOT_TYPES = ("plant", "plant_garden", "plant_orchard")

SLOT_TYPE_TO_PRODUCTION_KINDS = {
    "workshop": ("workshop", "shatyor_masterskaya_3"),
    "sewing": ("sewing", "shatyor_masterskaya"),
    "alchemy": ("alchemy", "shatyor_zelevareniya"),
    "barnyard": ("barnyard",),
}


def _item_matches_slot(item_type: str, inv: Inventory) -> bool:
    if item_type in ("plant_garden", "plant_orchard"):
        if inv.plant_id is None or inv.plant is None:
            return False
        expected = "garden" if item_type == "plant_garden" else "orchard"
        return inv.plant.category == expected
    if inv.product_id is None or inv.product is None:
        return False
    if item_type == "animal_product":
        return inv.product.animal_id is not None
    kinds = SLOT_TYPE_TO_PRODUCTION_KINDS.get(item_type)
    if kinds is not None:
        return inv.product.production_kind in kinds
    return True


@router.get("/cauldrons/{cauldron_id}/slot/{slot_index}/warehouse")
def slot_warehouse(
    cauldron_id: int,
    slot_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Cauldron).filter(Cauldron.id == cauldron_id, Cauldron.user_id == user.vk_id).first()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Котёл не найден")

    slot = db.query(CauldronSlot).filter(
        CauldronSlot.cauldron_id == c.id, CauldronSlot.slot_index == slot_index
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Слот не найден")

    inv = db.query(Inventory).filter(Inventory.user_id == user.vk_id, Inventory.qty > 0)

    if slot.item_type in ("plant_garden", "plant_orchard"):
        inv = inv.filter(Inventory.plant_id.isnot(None))
    else:
        inv = inv.filter(Inventory.product_id.isnot(None))
    rows = [i for i in inv.all() if _item_matches_slot(slot.item_type, i)]

    all_slots = db.query(CauldronSlot).filter(CauldronSlot.cauldron_id == c.id).all()
    used_plants = {s.item_id for s in all_slots if s.item_id is not None and s.item_type in PLANT_SLOT_TYPES}
    used_products = {s.item_id for s in all_slots if s.item_id is not None and s.item_type not in PLANT_SLOT_TYPES}

    result = []
    for i in rows:
        if i.plant_id:
            if i.plant_id in used_plants:
                continue
            img = i.plant.image_harvested_url or i.plant.image_grown_url or i.plant.image_url
            result.append({"item_kind": "plant", "item_id": i.plant_id, "item_name": i.plant.name, "item_emoji": i.plant.emoji, "item_image": img, "qty": i.qty})
        else:
            if i.product_id in used_products:
                continue
            result.append({"item_kind": "product", "item_id": i.product_id, "item_name": i.product.name, "item_emoji": i.product.emoji, "item_image": i.product.image_url, "qty": i.qty})
    return result


# ── Slot add/remove ──

class SlotFillRequest(BaseModel):
    item_kind: str
    item_id: int


@router.post("/cauldrons/{cauldron_id}/slot/{slot_index}", response_model=CauldronOut)
def fill_slot(
    cauldron_id: int,
    slot_index: int,
    req: SlotFillRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = _get_user_cauldron(cauldron_id, user, db)
    if c.status not in ("empty", "filling"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нельзя менять ингредиенты")

    slot = db.query(CauldronSlot).filter(
        CauldronSlot.cauldron_id == c.id, CauldronSlot.slot_index == slot_index
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Слот не найден")
    if slot.item_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Слот уже заполнен")

    dup_q = db.query(CauldronSlot).filter(
        CauldronSlot.cauldron_id == c.id,
        CauldronSlot.slot_index != slot_index,
        CauldronSlot.item_id == req.item_id,
    )
    if req.item_kind == "plant":
        dup_q = dup_q.filter(CauldronSlot.item_type.in_(PLANT_SLOT_TYPES))
    else:
        dup_q = dup_q.filter(CauldronSlot.item_type.notin_(PLANT_SLOT_TYPES))
    if dup_q.first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот ингредиент уже заложен в другой слот")

    inv = db.query(Inventory).filter(Inventory.user_id == user.vk_id, Inventory.qty > 0)
    if req.item_kind == "plant":
        inv = inv.filter(Inventory.plant_id == req.item_id)
    else:
        inv = inv.filter(Inventory.product_id == req.item_id)
    inv = inv.first()
    if inv is None or inv.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно на складе")
    if not _item_matches_slot(slot.item_type, inv):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Предмет не подходит для этого слота")

    slot.item_id = req.item_id
    c.status = "filling"

    all_filled = True
    for s in db.query(CauldronSlot).filter(CauldronSlot.cauldron_id == c.id).all():
        if s.item_id is None:
            all_filled = False
            break

    db.commit()
    return _cauldron_detail(c, db)


@router.delete("/cauldrons/{cauldron_id}/slot/{slot_index}", response_model=CauldronOut)
def clear_slot(
    cauldron_id: int,
    slot_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = _get_user_cauldron(cauldron_id, user, db)
    if c.status not in ("empty", "filling"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нельзя менять ингредиенты")

    slot = db.query(CauldronSlot).filter(
        CauldronSlot.cauldron_id == c.id, CauldronSlot.slot_index == slot_index
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Слот не найден")

    slot.item_id = None
    any_filled = False
    for s in db.query(CauldronSlot).filter(CauldronSlot.cauldron_id == c.id).all():
        if s.item_id is not None:
            any_filled = True
            break
    if not any_filled:
        c.status = "empty"

    db.commit()
    return _cauldron_detail(c, db)


# ── Brew ──

@router.post("/cauldrons/{cauldron_id}/brew", response_model=CauldronOut)
def brew(
    cauldron_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = _get_user_cauldron(cauldron_id, user, db)
    if c.status not in ("filling",):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Не все ингредиенты добавлены")

    slots = db.query(CauldronSlot).filter(CauldronSlot.cauldron_id == c.id).all()
    for s in slots:
        if s.item_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Слот {s.slot_index} не заполнен")

    for s in slots:
        if s.item_type in ("plant_garden", "plant_orchard"):
            inv = db.query(Inventory).filter(
                Inventory.user_id == user.vk_id, Inventory.plant_id == s.item_id
            ).first()
        else:
            inv = db.query(Inventory).filter(
                Inventory.user_id == user.vk_id, Inventory.product_id == s.item_id
            ).first()
        if inv:
            inv.qty = (inv.qty or 0) - 1

    c.status = "done"
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == c.recipe_id).first()
    if recipe:
        db.add(UserPotion(user_id=user.vk_id, potion_recipe_id=recipe.id,
                          bonus_code=recipe.bonus_code, activated=False))

    db.commit()

    check_and_award(user.vk_id, "potions_count", db)

    return _cauldron_detail(c, db)


def _get_user_cauldron(cauldron_id: int, user: User, db: Session) -> Cauldron:
    c = db.query(Cauldron).filter(Cauldron.id == cauldron_id, Cauldron.user_id == user.vk_id).first()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Котёл не найден")
    return c


# ── User Potions ──

@router.get("", response_model=list[UserPotionOut])
def list_user_potions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserPotion).filter(UserPotion.user_id == user.vk_id).all()
    result = []
    for up in rows:
        recipe = db.query(PotionRecipe).filter(PotionRecipe.id == up.potion_recipe_id).first()
        result.append(UserPotionOut(
            id=up.id, potion_recipe_id=up.potion_recipe_id,
            potion_name=recipe.name if recipe else "?",
            bonus_code=up.bonus_code, bonus_description=_bonus_label(up.bonus_code),
            when_fires=_bonus_hint(up.bonus_code),
            description=recipe.description if recipe else None,
            image_url=recipe.image_url if recipe else None,
            activated=up.activated,
            used=up.used,
            acquired_at=up.acquired_at.isoformat() if up.acquired_at else None,
        ))
    return result


class BonusCatalogItem(BaseModel):
    code: str
    label: str
    kind: str
    owned: bool
    activated: bool
    used: bool
    potion_id: int | None = None
    when_fires: str | None = None


@router.get("/bonuses", response_model=list[BonusCatalogItem])
def list_bonuses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    potions = db.query(UserPotion).filter(UserPotion.user_id == user.vk_id).all()
    by_code: dict[str, list[UserPotion]] = {}
    for p in potions:
        if p.bonus_code:
            by_code.setdefault(p.bonus_code, []).append(p)
    result = []
    for code in POTION_BONUS_LABELS.keys():
        code_potions = by_code.get(code, [])
        armed = next((p for p in code_potions if p.activated and not p.used), None)
        fired = next((p for p in code_potions if p.activated and p.used), None)
        available = next((p for p in code_potions if not p.activated and not p.used), None)
        chosen = armed or fired or available
        result.append(BonusCatalogItem(
            code=code,
            label=_bonus_label(code),
            kind="instant" if code in INSTANT_BONUSES else "conditional",
            owned=bool(code_potions),
            activated=chosen.activated if chosen else False,
            used=chosen.used if chosen else False,
            potion_id=chosen.id if chosen else None,
            when_fires=_bonus_hint(code),
        ))
    return result


def _apply_instant_bonus(user: User, code: str, db: Session) -> None:
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    if u is None:
        return
    if code == "free_pet":
        from models import Pet, UserPet
        pets = db.query(Pet).order_by(Pet.id.asc()).all()
        if not pets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Каталог питомцев пуст — бонус временно недоступен, обратитесь к админу",
            )
        owned = {up.pet_id for up in db.query(UserPet).filter(UserPet.user_id == user.vk_id).all()}
        free = next((p for p in pets if p.id not in owned), None)
        if free is not None:
            db.add(UserPet(user_id=user.vk_id, pet_id=free.id))
        else:
            u.unlocked_pets = (u.unlocked_pets or 0) + 1
    elif code == "early_level_up":
        u.level = (u.level or 0) + 1
        if u.round < u.level:
            u.round = u.level
        from models import LevelGate
        from services.leveling import _apply_unlock
        gate = db.query(LevelGate).filter(LevelGate.level == u.level).first()
        if gate is not None and gate.unlock_type:
            _apply_unlock(u, gate.unlock_type)
    elif code == "extra_barnyard_slot":
        u.unlocked_barnyard = (u.unlocked_barnyard or 0) + 1
    elif code == "unlock_garden_l3":
        if (u.unlocked_plot_level or 1) < 3:
            u.unlocked_plot_level = 3
    elif code == "unlock_orchard_l3":
        if (u.unlocked_garden_level or 0) < 3:
            u.unlocked_garden_level = 3


@router.post("/{potion_id}/activate", response_model=UserPotionOut)
def activate_potion(
    potion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    up = db.query(UserPotion).filter(UserPotion.id == potion_id, UserPotion.user_id == user.vk_id).first()
    if up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зелье не найдено")
    if up.used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Бонус уже использован")
    if up.activated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Бонус уже активирован")
    if not up.bonus_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У этого зелья нет бонуса")

    already_applied = db.query(UserPotion).filter(
        UserPotion.user_id == user.vk_id,
        UserPotion.bonus_code == up.bonus_code,
        UserPotion.id != up.id,
        UserPotion.activated.is_(True),
    ).first()
    if already_applied is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот бонус уже применён. Зелье можно варить много раз, но каждый бонус действует единожды.",
        )

    up.activated = True
    if up.bonus_code in INSTANT_BONUSES:
        _apply_instant_bonus(user, up.bonus_code, db)
        up.used = True

    db.commit()
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == up.potion_recipe_id).first()
    return UserPotionOut(
        id=up.id, potion_recipe_id=up.potion_recipe_id,
        potion_name=recipe.name if recipe else "?",
        bonus_code=up.bonus_code, bonus_description=_bonus_label(up.bonus_code),
        when_fires=_bonus_hint(up.bonus_code),
        description=recipe.description if recipe else None,
        image_url=recipe.image_url if recipe else None,
        activated=up.activated,
        used=up.used,
        acquired_at=up.acquired_at.isoformat() if up.acquired_at else None,
    )


# ── Admin ──

admin_router = APIRouter(prefix="/api/admin/potion-recipes", tags=["admin-potion-recipes"])


class PotionRecipeCreate(BaseModel):
    name: str
    level: str
    ingredient_slots: list[str]
    bonus_code: str | None = None
    reward_coins: int = 100
    description: str | None = None


@admin_router.get("", response_model=list[PotionRecipeOut])
def admin_list(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_recipe_out(r) for r in db.query(PotionRecipe).order_by(PotionRecipe.id.asc()).all()]


@admin_router.post("", response_model=PotionRecipeOut, status_code=status.HTTP_201_CREATED)
def admin_create(
    req: PotionRecipeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    code = req.name.strip().lower().replace(" ", "_")
    existing = db.query(PotionRecipe).filter(PotionRecipe.code == code).first()
    if existing:
        code = f"{code}_{abs(hash(req.name)) % 10000}"
    r = PotionRecipe(
        code=code, name=req.name, level=req.level,
        ingredient_slots=json.dumps(req.ingredient_slots, ensure_ascii=False),
        bonus_code=req.bonus_code, reward_coins=req.reward_coins,
        description=req.description,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@admin_router.put("/{recipe_id}", response_model=PotionRecipeOut)
def admin_update(
    recipe_id: int,
    req: PotionRecipeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(PotionRecipe).filter(PotionRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    r.name = req.name
    r.level = req.level
    r.ingredient_slots = json.dumps(req.ingredient_slots, ensure_ascii=False)
    r.bonus_code = req.bonus_code
    r.reward_coins = req.reward_coins
    r.description = req.description
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@admin_router.put("/{recipe_id}/image", response_model=PotionRecipeOut)
def admin_upload_image(
    recipe_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(PotionRecipe).filter(PotionRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    remove_upload(r.image_url)
    r.image_url = save_upload(image, f"potion_{r.id}", max_size=400)
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@admin_router.put("/{recipe_id}/card-image", response_model=PotionRecipeOut)
def admin_upload_card_image(
    recipe_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(PotionRecipe).filter(PotionRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    remove_upload(r.card_image_url)
    r.card_image_url = save_upload(image, f"potion_card_{r.id}", max_size=1200)
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@admin_router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete(
    recipe_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(PotionRecipe).filter(PotionRecipe.id == recipe_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")
    db.delete(r)
    db.commit()
    return None
