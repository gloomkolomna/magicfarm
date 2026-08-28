from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import User
from services.availability import locked_locations_for
from services.leveling import count_route_plots

router = APIRouter(prefix="/api", tags=["me"])


class MeResponse(BaseModel):
    vk_id: int
    role: str
    status: str
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
    story_seen: bool
    plots_placed: int
    locked_locations: list[str]
    access_active: bool
    trial_active: bool
    subscription_active: bool
    trial_until: str | None
    subscription_until: str | None
    subscription_dlc_codes: list[str]
    days_left: int | None
    trial_days_left: int | None
    subscription_days_left: int | None
    block_after_expiry: bool
    is_donor: bool
    donor_exempt: bool
    game_open: bool
    block_reason: str | None


@router.get("/me", response_model=MeResponse)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from routes.settings import get_game_open
    from services.donor import can_play, is_donor
    from services.subscription import (
        access_until, days_left, is_access_active, is_subscription_active, is_trial_active, parse_dlc_codes,
    )

    game_open = get_game_open(db)
    if user.role == "admin":
        play_allowed, block_reason = True, None
    elif game_open:
        play_allowed, block_reason = can_play(db, user)
    else:
        play_allowed, block_reason = is_access_active(user), None

    return MeResponse(
        vk_id=user.vk_id,
        role=user.role,
        status=user.status or "active",
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
        story_seen=bool(user.story_seen),
        plots_placed=count_route_plots(db, user.vk_id),
        locked_locations=locked_locations_for(user, db),
        access_active=play_allowed or user.role == "admin",
        trial_active=is_trial_active(user),
        subscription_active=is_subscription_active(user),
        trial_until=user.trial_until.isoformat() if user.trial_until else None,
        subscription_until=user.subscription_until.isoformat() if user.subscription_until else None,
        subscription_dlc_codes=parse_dlc_codes(user.subscription_dlc_codes),
        days_left=days_left(access_until(user)),
        trial_days_left=days_left(user.trial_until),
        subscription_days_left=days_left(user.subscription_until),
        block_after_expiry=bool(user.block_after_expiry),
        is_donor=is_donor(db, user.vk_id),
        donor_exempt=bool(user.donor_exempt),
        game_open=game_open,
        block_reason=block_reason,
    )
