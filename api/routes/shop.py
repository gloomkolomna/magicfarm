from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Field, Ingredient, Inventory, TradeCell, User, UserIngredient
from routes.admin_fields import _get_field_or_404
from routes.farm import InventoryOut, _inv_to_out
from routes.ingredients import ApothecaryItemOut, IngredientOut, _apothecary_item_out, _ingredient_out

router = APIRouter(prefix="/api/shop", tags=["shop"])


def _check_field_gate(f: Field, user: User) -> None:
    if f.min_level is not None and (user.level or 0) < f.min_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Эта локация пока недоступна")


class TradeCellOut(BaseModel):
    id: int
    col: int
    row: int
    ingredients: list[IngredientOut]


class ShopOut(BaseModel):
    field_id: int
    name: str
    map_url: str | None
    cols: int
    rows: int
    cells: list[TradeCellOut]
    apothecary: list[ApothecaryItemOut]
    inventory: list[InventoryOut]


@router.get("/{field_id}", response_model=ShopOut)
def get_shop(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    if f.field_kind != "shop":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это не городская лавка")
    _check_field_gate(f, user)

    cells = db.query(TradeCell).filter(
        TradeCell.field_id == f.id
    ).order_by(TradeCell.row.asc(), TradeCell.col.asc()).all()
    apo = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.qty > 0
    ).all()
    inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.qty > 0
    ).order_by(Inventory.id.asc()).all()
    return ShopOut(
        field_id=f.id, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows,
        cells=[TradeCellOut(
            id=tc.id, col=tc.col, row=tc.row,
            ingredients=[_ingredient_out(tci.ingredient) for tci in tc.ingredients],
        ) for tc in cells],
        apothecary=[_apothecary_item_out(ui) for ui in apo],
        inventory=[_inv_to_out(i) for i in inv],
    )


class BarterRequest(BaseModel):
    want_ingredient_id: int
    give_kind: str = "ingredient"
    give_item_id: int
    qty: int = 1


class BarterGiveOut(BaseModel):
    kind: str
    id: int
    name: str
    emoji: str | None = None


class BarterResult(BaseModel):
    cell_id: int
    want: IngredientOut
    give: BarterGiveOut
    qty: int
    apothecary: list[ApothecaryItemOut]
    inventory: list[InventoryOut]


def _give_have(kind: str, item_id: int, user_id: int, db: Session):
    if kind == "ingredient":
        row = db.query(UserIngredient).filter(
            UserIngredient.user_id == user_id, UserIngredient.ingredient_id == item_id
        ).first()
        return row
    if kind == "plant":
        return db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.plant_id == item_id
        ).first()
    return db.query(Inventory).filter(
        Inventory.user_id == user_id, Inventory.product_id == item_id
    ).first()


@router.post("/cells/{cell_id}/barter", response_model=BarterResult)
def barter(
    cell_id: int,
    req: BarterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tc = db.query(TradeCell).filter(TradeCell.id == cell_id).first()
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка бартера не найдена")
    _check_field_gate(tc.field, user)

    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество должно быть не меньше 1")
    if req.give_kind not in ("ingredient", "plant", "product"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="give_kind: ingredient, plant или product")

    want_ids = {tci.ingredient_id for tci in tc.ingredients}
    if req.want_ingredient_id not in want_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этого ингредиента нет в ассортименте клетки",
        )

    give = _give_have(req.give_kind, req.give_item_id, user.vk_id, db)
    if give is None or (give.qty or 0) < req.qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно предмета на складе",
        )

    give.qty = (give.qty or 0) - req.qty
    want = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id,
        UserIngredient.ingredient_id == req.want_ingredient_id,
    ).first()
    if want is None:
        want = UserIngredient(user_id=user.vk_id, ingredient_id=req.want_ingredient_id, qty=0)
        db.add(want)
    want.qty = (want.qty or 0) + req.qty
    db.commit()

    apo = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.qty > 0
    ).all()
    inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.qty > 0
    ).order_by(Inventory.id.asc()).all()
    want_ing = db.query(Ingredient).filter(Ingredient.id == req.want_ingredient_id).first()

    give_name, give_emoji = _give_label(req.give_kind, req.give_item_id, db)

    return BarterResult(
        cell_id=tc.id,
        want=_ingredient_out(want_ing),
        give=BarterGiveOut(kind=req.give_kind, id=req.give_item_id, name=give_name, emoji=give_emoji),
        qty=req.qty,
        apothecary=[_apothecary_item_out(ui) for ui in apo],
        inventory=[_inv_to_out(i) for i in inv],
    )


def _give_label(kind: str, item_id: int, db: Session) -> tuple[str, str | None]:
    if kind == "ingredient":
        ing = db.query(Ingredient).filter(Ingredient.id == item_id).first()
        return (ing.name if ing else "ингредиент"), None
    from models import Plant, Product
    if kind == "plant":
        p = db.query(Plant).filter(Plant.id == item_id).first()
        return (p.name if p else "растение"), (p.emoji if p else None)
    pr = db.query(Product).filter(Product.id == item_id).first()
    return (pr.name if pr else "товар"), (pr.emoji if pr else None)
