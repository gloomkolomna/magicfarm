import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Inventory, Plant, Plot, Production, Product, User, Recipe

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
    cell_id: int | None
    created_at: datetime.datetime | None
    completed_at: datetime.datetime | None


def _plot_to_out(p: Plot) -> PlotOut:
    return PlotOut(
        id=p.id, plant_id=p.plant_id, plant_name=p.plant.name, plant_emoji=p.plant.emoji,
        qty=p.qty, status=p.status, accumulated=p.accumulated, required=p.required,
        crystal_color=p.crystal_color, crystal_count=p.crystal_count,
        drawn_cards_json=p.drawn_cards_json,
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
}


class InventoryOut(BaseModel):
    item_kind: str
    item_id: int
    item_code: str
    item_name: str
    item_emoji: str | None
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
        ingredient_type=ing_type, ingredient_icon=ing_icon,
    )


class InvestRequest(BaseModel):
    amount: int


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

PRODUCTION_KINDS = ("alchemy", "sewing", "workshop")
PRODUCTION_NAMES = {"alchemy": "Стол зельеварения", "sewing": "Шатёр портнихи", "workshop": "Мастерская"}


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
    plant_id: int
    product_id: int
    qty: int = 1


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

    plant_inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.plant_id == req.plant_id
    ).first()
    if plant_inv is None or (plant_inv.qty or 0) < req.qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно растений на складе",
        )

    from models import Plant as PlantModel, UserRecipe
    plant_obj = db.query(PlantModel).filter(PlantModel.id == req.plant_id).first()
    if plant_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")

    recipe = db.query(UserRecipe).join(
        Recipe, UserRecipe.recipe_id == Recipe.id
    ).filter(
        UserRecipe.user_id == user.vk_id,
        UserRecipe.status == "studied",
        Recipe.plant_id == req.plant_id,
        Recipe.product_id == req.product_id,
    ).first()
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Рецепт не изучен",
        )

    from routes.settings import get_production_norm
    norm_per_unit = get_production_norm(db, plant_obj.level)
    required = norm_per_unit * req.qty

    from models import CraftSession
    cs = CraftSession(
        user_id=user.vk_id, plant_id=req.plant_id, qty=req.qty,
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
    q = db.query(Inventory).filter(Inventory.user_id == user.vk_id)
    if item_kind == "plant":
        q = q.filter(Inventory.plant_id.isnot(None))
    elif item_kind == "product":
        q = q.filter(Inventory.product_id.isnot(None))
    rows = q.all()
    return [_inv_to_out(i) for i in rows]


class ProductOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    stars: int
    production_kind: str | None


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Product).order_by(Product.id.asc()).all()
    return [
        ProductOut(
            id=p.id, code=p.code, name=p.name, emoji=p.emoji,
            stars=p.stars, production_kind=p.production_kind,
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
        full_price = calculate_product_price(plant_level, prod_kind, qty)

    reward = int(full_price * ratio)

    inv.qty = (inv.qty or 0) - req.qty
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.coins = (u.coins or 0) + reward

    db.commit()
    return {"coins_earned": reward, "item_kind": req.item_kind, "qty_sold": req.qty}

