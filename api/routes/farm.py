from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import CraftSession, Inventory, Plant, Plot, Production, Product, User, Recipe, UserRecipe
from models import PotionRecipe, UserPotion
from sqlalchemy import func

router = APIRouter(prefix="/api/farm", tags=["farm"])

MIN_INVEST = 1


def _get_plot_or_404(plot_id: int, db: Session) -> Plot:
    p = db.query(Plot).filter(Plot.id == plot_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Грядка не найдена")
    return p


def _get_user_plot(plot_id: int, user: User, db: Session) -> Plot:
    p = _get_plot_or_404(plot_id, db)
    if p.user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша грядка")
    if p.status != "planted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Грядка уже выращена")
    return p


class PlotOut(BaseModel):
    id: int
    plant_id: int
    plant_name: str
    plant_emoji: str | None
    qty: int
    status: str
    accumulated: int
    required: int
    crystal_color: str | None
    crystal_count: int | None
    drawn_cards_json: str | None
    norm_revealed: bool
    cell_id: int | None
    created_at: datetime.datetime | None
    completed_at: datetime.datetime | None


def _plot_to_out(p: Plot) -> PlotOut:
    return PlotOut(
        id=p.id, plant_id=p.plant_id, plant_name=p.plant.name, plant_emoji=p.plant.emoji,
        qty=p.qty, status=p.status, accumulated=p.accumulated, required=p.required,
        crystal_color=p.crystal_color, crystal_count=p.crystal_count,
        drawn_cards_json=p.drawn_cards_json,
        norm_revealed=bool(p.norm_revealed),
        cell_id=p.cell_id,
        created_at=p.created_at, completed_at=p.completed_at,
    )


class ProductionOut(BaseModel):
    id: int
    kind: str
    name: str
    status: str
    accumulated: int
    required: int
    created_at: datetime.datetime | None


def _prod_to_out(pr: Production) -> ProductionOut:
    return ProductionOut(
        id=pr.id, kind=pr.kind, name=pr.name, status=pr.status,
        accumulated=pr.accumulated, required=pr.required, created_at=pr.created_at,
    )


INGREDIENT_ICONS = {
    "plant_garden": "🍃",
    "plant_orchard": "🍎",
    "animal_product": "🥚",
    "tent_workshop": "🔨",
    "tent_sewing": "🧵",
    "tent_alchemy": "⚗️",
    "tent_barnyard": "🏚️",
}


class InventoryOut(BaseModel):
    item_kind: str
    item_id: int
    item_code: str
    item_name: str
    item_emoji: str | None
    item_image: str | None = None
    qty: int
    ingredient_type: str | None
    ingredient_icon: str | None


def _inv_to_out(inv: Inventory) -> InventoryOut:
    if inv.plant_id is not None:
        plant = inv.plant
        ing_type = "plant_garden" if plant.category == "garden" else "plant_orchard"
        return InventoryOut(
            item_kind="plant", item_id=plant.id, item_code=plant.code,
            item_name=plant.name, item_emoji=plant.emoji, qty=inv.qty,
            item_image=plant.image_harvested_url or plant.image_grown_url or plant.image_url,
            ingredient_type=ing_type, ingredient_icon=INGREDIENT_ICONS.get(ing_type),
        )
    prod = inv.product
    ing_type = None
    ing_icon = None
    if prod.production_kind:
        ing_type = f"tent_{prod.production_kind}"
        ing_icon = INGREDIENT_ICONS.get(ing_type)
    return InventoryOut(
        item_kind="product", item_id=prod.id, item_code=prod.code,
        item_name=prod.name, item_emoji=prod.emoji, qty=inv.qty,
        item_image=prod.image_url,
        ingredient_type=ing_type, ingredient_icon=ing_icon,
    )


class InvestRequest(BaseModel):
    amount: int


@router.post("/plots/{plot_id}/reveal-norm", response_model=PlotOut)
def reveal_norm(
    plot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plot = db.query(Plot).filter(Plot.id == plot_id, Plot.user_id == user.vk_id).first()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Грядка не найдена")
    plot.norm_revealed = True
    db.commit()
    db.refresh(plot)
    return _plot_to_out(plot)


@router.post("/plots/{plot_id}/invest", response_model=PlotOut)
def invest_plot(
    plot_id: int,
    req: InvestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plot = _get_user_plot(plot_id, user, db)
    if req.amount < MIN_INVEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Минимум {MIN_INVEST} крестиков",
        )

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    if (u.crosses_balance or 0) < req.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно крестиков на балансе",
        )

    u.crosses_balance = (u.crosses_balance or 0) - req.amount
    plot.accumulated = (plot.accumulated or 0) + req.amount

    if plot.accumulated >= plot.required:
        plot.status = "grown"
        plot.completed_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(plot)
    return _plot_to_out(plot)


# ===== Производства (шатры) =====

PRODUCTION_KINDS = ("alchemy", "sewing", "workshop", "barnyard")
PRODUCTION_NAMES = {"alchemy": "Стол зельеварения", "sewing": "Шатёр портнихи", "workshop": "Мастерская", "barnyard": "Шатёр скотного двора"}


def _get_production_or_404(production_id: int, db: Session) -> Production:
    pr = db.query(Production).filter(Production.id == production_id).first()
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Производство не найдено")
    return pr


def _get_user_production(production_id: int, user: User, db: Session) -> Production:
    pr = _get_production_or_404(production_id, db)
    if pr.user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваше производство")
    return pr


class CraftRequest(BaseModel):
    product_id: int
    qty: int = 1


class CraftInfoOut(BaseModel):
    source_kind: str
    plant_id: int | None
    plant_name: str | None
    plant_emoji: str | None
    source_product_id: int | None
    source_product_name: str | None
    source_product_emoji: str | None
    stock_qty: int
    norm_per_unit: int


@router.get("/products/{product_id}/craft-info", response_model=CraftInfoOut)
def product_craft_info(
    product_id: int,
    production_kind: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")

    from routes.settings import get_user_production_norm

    if product.plant_id is not None:
        plant_obj = db.query(Plant).filter(Plant.id == product.plant_id).first()
        if plant_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")

        inv = db.query(Inventory).filter(
            Inventory.user_id == user.vk_id, Inventory.plant_id == product.plant_id
        ).first()

        norm = get_user_production_norm(user, plant_obj.level)
        if norm is not None and production_kind:
            from models import ProductionTemplate
            pt = db.query(ProductionTemplate).filter(
                ProductionTemplate.code == production_kind
            ).first()
            crystal = pt.processing_crystal if pt is not None else 0
            norm = (crystal + plant_obj.level) * norm

        return CraftInfoOut(
            source_kind="plant",
            plant_id=plant_obj.id,
            plant_name=plant_obj.name,
            plant_emoji=plant_obj.emoji,
            source_product_id=None,
            source_product_name=None,
            source_product_emoji=None,
            stock_qty=(inv.qty or 0) if inv else 0,
            norm_per_unit=norm or 0,
        )

    from models import Recipe
    recipe = db.query(Recipe).filter(
        Recipe.product_id == product.id, Recipe.source_product_id.isnot(None)
    ).first()
    if recipe is None or recipe.source_product is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У товара нет источника для крафта")

    inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.product_id == recipe.source_product_id
    ).first()

    return CraftInfoOut(
        source_kind="animal_product",
        plant_id=None,
        plant_name=None,
        plant_emoji=None,
        source_product_id=recipe.source_product_id,
        source_product_name=recipe.source_product.name,
        source_product_emoji=recipe.source_product.emoji,
        stock_qty=(inv.qty or 0) if inv else 0,
        norm_per_unit=get_user_production_norm(user, recipe.level) or 0,
    )


@router.post("/productions/{production_id}/craft", response_model=dict)
def craft_product(
    production_id: int,
    req: CraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pr = _get_user_production(production_id, user, db)
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    if product.production_kind is not None and product.production_kind != pr.kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот товар производится на другом производстве",
        )
    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество товара должно быть ≥ 1")

    from models import Recipe
    from routes.settings import get_user_production_norm

    if product.plant_id is not None:
        plant_obj = db.query(Plant).filter(Plant.id == product.plant_id).first()
        if plant_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")

        plant_inv = db.query(Inventory).filter(
            Inventory.user_id == user.vk_id, Inventory.plant_id == product.plant_id
        ).first()
        if plant_inv is None or (plant_inv.qty or 0) < req.qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недостаточно растений на складе",
            )

        recipe = db.query(UserRecipe).join(
            Recipe, UserRecipe.recipe_id == Recipe.id
        ).filter(
            UserRecipe.user_id == user.vk_id,
            UserRecipe.status == "studied",
            Recipe.plant_id == product.plant_id,
            Recipe.product_id == req.product_id,
        ).first()
        if recipe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Рецепт не изучен",
            )

        prod_norm = get_user_production_norm(user, plant_obj.level)
        if prod_norm is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Сначала задайте нормы производства товара в профиле (Настройки норм)",
            )

        from models import ProductionTemplate
        pt = db.query(ProductionTemplate).filter(ProductionTemplate.code == pr.kind).first()
        crystal = pt.processing_crystal if pt is not None else 0
        required = (crystal + plant_obj.level) * prod_norm * req.qty

        cs = CraftSession(
            user_id=user.vk_id, plant_id=product.plant_id, qty=req.qty,
            product_id=req.product_id, required=required,
        )
        db.add(cs)
        db.commit()
        db.refresh(cs)

        return {
            "craft_session_id": cs.id,
            "required": required,
            "plant_name": plant_obj.name,
            "product_name": product.name,
            "qty": req.qty,
        }

    recipe = db.query(Recipe).filter(
        Recipe.product_id == req.product_id, Recipe.source_product_id.isnot(None)
    ).first()
    if recipe is None or recipe.source_product is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У товара нет источника для крафта",
        )

    studied = db.query(UserRecipe).filter(
        UserRecipe.user_id == user.vk_id,
        UserRecipe.recipe_id == recipe.id,
        UserRecipe.status == "studied",
    ).first()
    if studied is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Рецепт не изучен",
        )

    source_inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.product_id == recipe.source_product_id
    ).first()
    if source_inv is None or (source_inv.qty or 0) < req.qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно продукции животного на складе",
        )

    prod_norm = get_user_production_norm(user, recipe.level)
    if prod_norm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сначала задайте нормы производства товара в профиле (Настройки норм)",
        )
    required = prod_norm * req.qty

    cs = CraftSession(
        user_id=user.vk_id, plant_id=None, source_product_id=recipe.source_product_id,
        qty=req.qty, product_id=req.product_id, required=required,
    )
    db.add(cs)
    db.commit()
    db.refresh(cs)

    return {
        "craft_session_id": cs.id,
        "required": required,
        "source_product_name": recipe.source_product.name,
        "product_name": product.name,
        "qty": req.qty,
    }


class CraftSessionOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_emoji: str | None
    plant_name: str | None
    source_product_name: str | None
    qty: int
    required: int
    production_kind: str | None
    status: str
    created_at: datetime.datetime | None


def _cs_to_out(cs: CraftSession, db: Session) -> CraftSessionOut:
    product = db.query(Product).filter(Product.id == cs.product_id).first()
    plant = db.query(Plant).filter(Plant.id == cs.plant_id).first() if cs.plant_id is not None else None
    source_product = (
        db.query(Product).filter(Product.id == cs.source_product_id).first()
        if cs.source_product_id is not None else None
    )
    return CraftSessionOut(
        id=cs.id,
        product_id=cs.product_id,
        product_name=product.name if product else "",
        product_emoji=product.emoji if product else None,
        plant_name=plant.name if plant else None,
        source_product_name=source_product.name if source_product else None,
        qty=cs.qty,
        required=cs.required,
        production_kind=product.production_kind if product else None,
        status=cs.status,
        created_at=cs.created_at,
    )


@router.get("/craft-sessions", response_model=list[CraftSessionOut])
def list_craft_sessions(
    status_filter: str = Query(default="pending", alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if status_filter not in ("pending", "all"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status: pending или all")
    q = db.query(CraftSession).filter(CraftSession.user_id == user.vk_id)
    if status_filter == "pending":
        q = q.filter(CraftSession.status == "pending")
    rows = q.order_by(CraftSession.created_at.desc()).all()
    return [_cs_to_out(cs, db) for cs in rows]


@router.delete("/craft-sessions/{session_id}", response_model=dict)
def cancel_craft_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cs = db.query(CraftSession).filter(CraftSession.id == session_id).first()
    if cs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Крафт не найден")
    if cs.user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваш крафт")
    if cs.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Крафт уже завершён")
    db.delete(cs)
    db.commit()
    return {"cancelled": True}


@router.get("/productions", response_model=list[ProductionOut])
def list_productions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Production).filter(Production.user_id == user.vk_id).all()
    return [_prod_to_out(pr) for pr in rows]


@router.get("/inventory", response_model=list[InventoryOut])
def list_inventory(
    item_kind: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result: list[InventoryOut] = []
    if item_kind in (None, "plant", "product"):
        q = db.query(Inventory).filter(Inventory.user_id == user.vk_id, Inventory.qty > 0)
        if item_kind == "plant":
            q = q.filter(Inventory.plant_id.isnot(None))
        elif item_kind == "product":
            q = q.filter(Inventory.product_id.isnot(None))
        result = [_inv_to_out(i) for i in q.all()]

    if item_kind in (None, "potion"):
        potion_rows = (
            db.query(PotionRecipe, func.count(UserPotion.id))
            .join(UserPotion, UserPotion.potion_recipe_id == PotionRecipe.id)
            .filter(UserPotion.user_id == user.vk_id, UserPotion.used.is_(False))
            .group_by(PotionRecipe.id)
            .all()
        )
        for recipe, qty in potion_rows:
            result.append(InventoryOut(
                item_kind="potion", item_id=recipe.id, item_code=recipe.code,
                item_name=recipe.name, item_emoji=None,
                item_image=recipe.image_url, qty=qty,
                ingredient_type=None, ingredient_icon=None,
            ))

    return result


class ProductOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    stars: int
    production_kind: str | None
    image_url: str | None
    available: bool = True


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.availability import product_lock_reason

    rows = db.query(Product).order_by(Product.id.asc()).all()
    return [
        ProductOut(
            id=p.id, code=p.code, name=p.name, emoji=p.emoji,
            stars=p.stars, production_kind=p.production_kind,
            image_url=p.image_url,
            available=product_lock_reason(p, user, db) is None,
        )
        for p in rows
    ]


class SellRequest(BaseModel):
    item_kind: str
    item_id: int
    qty: int


@router.post("/sell-surplus", response_model=dict)
def sell_surplus(
    req: SellRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.item_kind not in ("plant", "product"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item_kind: plant или product")
    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="qty >= 1")

    inv = db.query(Inventory).filter(Inventory.user_id == user.vk_id)
    if req.item_kind == "plant":
        inv = inv.filter(Inventory.plant_id == req.item_id)
    else:
        inv = inv.filter(Inventory.product_id == req.item_id)
    inv = inv.first()

    if inv is None or (inv.qty or 0) < req.qty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно на складе")

    from routes.settings import get_sale_price_ratio
    from services.pricing import PLANT_BASE_PRICES, calculate_product_price
    from models import Plant as PlantModel, Product as ProductModel

    ratio = get_sale_price_ratio(db)
    qty = req.qty

    if req.item_kind == "plant":
        plant = db.query(PlantModel).filter(PlantModel.id == req.item_id).first()
        if plant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
        full_price = PLANT_BASE_PRICES.get(plant.level, 5) * qty
    else:
        prod = db.query(ProductModel).filter(ProductModel.id == req.item_id).first()
        if prod is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
        plant = db.query(PlantModel).filter(PlantModel.id == prod.plant_id).first() if prod.plant_id else None
        plant_level = plant.level if plant else 1
        prod_kind = prod.production_kind or "alchemy"
        full_price = calculate_product_price(plant_level, prod_kind, qty, db)

    reward = int(full_price * ratio)

    inv.qty = (inv.qty or 0) - req.qty
    if inv.qty <= 0:
        db.delete(inv)
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.coins = (u.coins or 0) + reward

    db.commit()
    return {"coins_earned": reward, "item_kind": req.item_kind, "qty_sold": req.qty}

