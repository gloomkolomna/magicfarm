from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_current_user
from models import User

router = APIRouter(prefix="/api", tags=["me"])


class MeResponse(BaseModel):
    vk_id: int
    role: str
    display_name: str | None
    crosses_balance: int
    crosses_total: int
    coins: int
    round: int
    level: int
    unlocked_barnyard: int
    unlocked_pets: int
    unlocked_plot_level: int
    unlocked_garden_level: int
    onboarding_done: bool


@router.get("/me", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user)):
    return MeResponse(
        vk_id=user.vk_id,
        role=user.role,
        display_name=user.display_name,
        crosses_balance=user.crosses_balance,
        crosses_total=user.crosses_total,
        coins=user.coins,
        round=user.round,
        level=user.level or 0,
        unlocked_barnyard=user.unlocked_barnyard or 0,
        unlocked_pets=user.unlocked_pets or 0,
        unlocked_plot_level=user.unlocked_plot_level or 1,
        unlocked_garden_level=user.unlocked_garden_level or 0,
        onboarding_done=bool(user.onboarding_done),
    )
