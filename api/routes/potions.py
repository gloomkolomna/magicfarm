from __future__ import annotations
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Cauldron, CauldronSlot, Inventory, PotionRecipe, User, UserPotion
from services.achievements import check_and_award
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/potions", tags=["potions"])

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


def _bonus_label(code: str | None) -> str | None:
    if not code:
        return None
    return POTION_BONUS_LABELS.get(code, code)


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


def _recipe_out(r: PotionRecipe) -> PotionRecipeOut:
    slots = json.loads(r.ingredient_slots) if r.ingredient_slots else []
    return PotionRecipeOut(
        id=r.id, code=r.code, name=r.name, level=r.level,
        ingredient_slots=slots, bonus_code=r.bonus_code,
        reward_coins=r.reward_coins, description=r.description, image_url=r.image_url,
        card_image_url=r.card_image_url,
    )


class CauldronOut(BaseModel):
    id: int
    recipe_id: int | None
    recipe_name: str | None
    material: str
    capacity: int
    status: str
    slots: list[dict]


class UserPotionOut(BaseModel):
    id: int
    potion_recipe_id: int
    potion_name: str
    bonus_code: str | None
    bonus_description: str | None
    description: str | None
    image_url: str | None
    activated: bool
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
    return [_recipe_out(r) for r in q.limit(100).all()]


# ── Cauldrons ──

class CreateCauldronRequest(BaseModel):
    recipe_id: int


@router.post("/cauldrons", response_model=CauldronOut, status_code=status.HTTP_201_CREATED)
def create_cauldron(
    req: CreateCauldronRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == req.recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт не найден")

    existing = db.query(Cauldron).filter(
        Cauldron.user_id == user.vk_id, Cauldron.status != "done"
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Уже есть активный котёл")

    slots = json.loads(recipe.ingredient_slots) if recipe.ingredient_slots else []
    capacity = len(slots)
    material = "tin"
    if capacity >= 6:
        material = "gold"
    elif capacity >= 5:
        material = "silver"

    c = Cauldron(user_id=user.vk_id, recipe_id=recipe.id, material=material,
                 capacity=capacity, status="empty")
    db.add(c)
    db.flush()

    for i, slot_type in enumerate(slots):
        db.add(CauldronSlot(cauldron_id=c.id, slot_index=i, item_type=slot_type, item_id=None))

    db.commit()
    db.refresh(c)

    from models import OrderReq as OrderModel, OrderTemplate
    templates = db.query(OrderTemplate).filter(
        OrderTemplate.source_kind == "potion", OrderTemplate.source_id == recipe.id
    ).all()
    for t in templates:
        existing_order = db.query(OrderModel).filter(
            OrderModel.user_id == user.vk_id,
            OrderModel.product_id == t.product_id,
            OrderModel.status == "open",
        ).first()
        if existing_order is None:
            db.add(OrderModel(
                user_id=user.vk_id, product_id=t.product_id, qty=t.qty,
                reward_coins=t.reward_coins, customer=t.customer,
                status="open", name=t.name, image_url=t.image_url,
            ))
    db.commit()

    return _cauldron_detail(c, db)


@router.get("/cauldrons/active", response_model=CauldronOut | None)
def get_active_cauldron(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Cauldron).filter(
        Cauldron.user_id == user.vk_id, Cauldron.status != "done"
    ).first()
    return _cauldron_detail(c, db) if c is not None else None


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


def _cauldron_detail(c: Cauldron, db: Session) -> CauldronOut:
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == c.recipe_id).first() if c.recipe_id else None
    slots = db.query(CauldronSlot).filter(CauldronSlot.cauldron_id == c.id).order_by(CauldronSlot.slot_index).all()
    slot_data = [{"slot_index": s.slot_index, "item_type": s.item_type, "item_id": s.item_id} for s in slots]
    return CauldronOut(
        id=c.id, recipe_id=c.recipe_id, recipe_name=recipe.name if recipe else None,
        material=c.material, capacity=c.capacity, status=c.status, slots=slot_data,
    )


# ── Slot warehouse filter ──

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

    result = []
    for i in rows:
        if i.plant_id:
            result.append({"item_kind": "plant", "item_id": i.plant_id, "item_name": i.plant.name, "item_emoji": i.plant.emoji, "qty": i.qty})
        else:
            result.append({"item_kind": "product", "item_id": i.product_id, "item_name": i.product.name, "item_emoji": i.product.emoji, "qty": i.qty})
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
        existing = db.query(UserPotion).filter(
            UserPotion.user_id == user.vk_id, UserPotion.potion_recipe_id == recipe.id
        ).first()
        if existing is None:
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
            description=recipe.description if recipe else None,
            image_url=recipe.image_url if recipe else None,
            activated=up.activated,
            acquired_at=up.acquired_at.isoformat() if up.acquired_at else None,
        ))
    return result


@router.post("/{potion_id}/activate", response_model=UserPotionOut)
def activate_potion(
    potion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    up = db.query(UserPotion).filter(UserPotion.id == potion_id, UserPotion.user_id == user.vk_id).first()
    if up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зелье не найдено")
    if up.activated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Бонус уже активирован")
    if not up.bonus_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У этого зелья нет бонуса")

    up.activated = True
    db.commit()
    recipe = db.query(PotionRecipe).filter(PotionRecipe.id == up.potion_recipe_id).first()
    return UserPotionOut(
        id=up.id, potion_recipe_id=up.potion_recipe_id,
        potion_name=recipe.name if recipe else "?",
        bonus_code=up.bonus_code, bonus_description=_bonus_label(up.bonus_code),
        description=recipe.description if recipe else None,
        image_url=recipe.image_url if recipe else None,
        activated=up.activated,
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
    r.card_image_url = save_upload(image, f"potion_card_{r.id}", max_size=512)
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
