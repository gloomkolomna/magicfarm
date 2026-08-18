from tests.conftest import TestingSessionLocal, make_user_client

PLAYER_VK = 600

_MODELS = [
    "UserPlantNorm", "UserCrystalNorm", "UserAchievement", "UserPotion", "Cauldron",
    "UserPet", "BarnyardSlot", "CraftSession", "UserRecipe", "HouseBuild", "TentBuild",
    "UserOrder", "Inventory", "Production", "Plot", "StitchReport",
]


def _count(model, vk_id):
    s = TestingSessionLocal()
    try:
        return s.query(model).filter(model.user_id == vk_id).count()
    finally:
        s.close()


def _seed_everything(vk_id):
    from models import (
        BarnyardSlot, Cauldron, CraftSession, Field, HouseBuild, Inventory, OrderReq,
        Plot, Production, StitchReport, Tent, TentBuild, User, UserAchievement,
        UserCrystalNorm, UserOrder, UserPet, UserPlantNorm, UserPotion, UserRecipe,
    )
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        u.crosses_balance = 123
        u.crosses_total = 456
        u.coins = 78
        u.round = 3
        u.level = 2
        u.unlocked_barnyard = 1
        u.unlocked_pets = 2
        u.unlocked_plot_level = 2
        u.unlocked_garden_level = 1
        u.onboarding_done = True
        u.dice_norm = 55
        u.study_norm_l1 = 500
        u.production_norm_l1 = 100

        f = Field(code=f"restart_{vk_id}", name="Поле")
        s.add(f)
        s.flush()
        t = Tent(field_id=f.id, name="Шатёр", kind="alchemy", col1=0, row1=0, col2=1, row2=1)
        s.add(t)
        s.flush()

        s.add(TentBuild(user_id=vk_id, tent_id=t.id, build_status="planted", required=100))
        s.add(HouseBuild(user_id=vk_id, tent_id=t.id, current_material="glass", current_die=3, current_required=300))
        s.add(Plot(user_id=vk_id, plant_id=1, qty=2, status="planted", accumulated=5, required=60))
        s.add(Production(user_id=vk_id, kind="alchemy", name="Стол", required=500))
        s.add(Inventory(user_id=vk_id, qty=7))
        o = OrderReq(product_id=1, qty=1)
        s.add(o)
        s.flush()
        s.add(UserOrder(user_id=vk_id, order_id=o.id))
        s.add(StitchReport(user_id=vk_id, amount=42, photo_after_url="x.png", status="accepted"))
        s.add(UserCrystalNorm(user_id=vk_id, color="treasure_green", count=0, value=400))
        s.add(UserPlantNorm(user_id=vk_id, plant_id=1, norm_per_unit=30))
        s.add(UserRecipe(user_id=vk_id, recipe_id=1, status="studied", required=500))
        s.add(CraftSession(user_id=vk_id, product_id=1, qty=1, required=100))
        s.add(BarnyardSlot(user_id=vk_id, status="empty"))
        s.add(UserPet(user_id=vk_id, pet_id=1))
        s.add(Cauldron(user_id=vk_id))
        s.add(UserPotion(user_id=vk_id, potion_recipe_id=1))
        s.add(UserAchievement(user_id=vk_id, achievement_id=1))

        s.commit()
    finally:
        s.close()


def _all_empty(vk_id):
    import models
    return all(_count(getattr(models, name), vk_id) == 0 for name in _MODELS)


def test_restart_wipes_all_progress(admin_client):
    with make_user_client(PLAYER_VK, "player") as c:
        c.get("/api/me")
    _seed_everything(PLAYER_VK)
    assert not _all_empty(PLAYER_VK)

    res = admin_client.post(f"/api/admin/players/{PLAYER_VK}/restart")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["crosses_balance"] == 0
    assert data["crosses_total"] == 0
    assert data["coins"] == 0
    assert data["round"] == 1
    assert data["reports_total"] == 0

    assert _all_empty(PLAYER_VK)

    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == PLAYER_VK).first()
        assert u.role == "player"
        assert u.crosses_balance == 0
        assert u.crosses_total == 0
        assert u.coins == 0
        assert u.round == 1
        assert u.level == 0
        assert u.unlocked_barnyard == 0
        assert u.unlocked_pets == 0
        assert u.unlocked_plot_level == 1
        assert u.unlocked_garden_level == 0
        assert u.onboarding_done is False
        assert u.dice_norm is None
        assert u.study_norm_l1 is None
        assert u.production_norm_l1 is None
    finally:
        s.close()


def test_restart_other_players_untouched(admin_client):
    with make_user_client(601, "player") as c1:
        c1.get("/api/me")
    with make_user_client(602, "player") as c2:
        c2.get("/api/me")
    _seed_everything(601)

    res = admin_client.post("/api/admin/players/601/restart")
    assert res.status_code == 200

    from models import UserCrystalNorm
    assert _count(UserCrystalNorm, 602) == 3


def test_restart_requires_admin(player_client):
    res = player_client.post("/api/admin/players/123/restart")
    assert res.status_code == 403


def test_restart_unknown_player(admin_client):
    res = admin_client.post("/api/admin/players/999999/restart")
    assert res.status_code == 404


def test_restart_keeps_order_catalog(admin_client):
    from models import OrderReq, UserOrder
    with make_user_client(PLAYER_VK, "player") as c:
        c.get("/api/me")
    s = TestingSessionLocal()
    try:
        o = OrderReq(product_id=1, qty=1)
        s.add(o)
        s.flush()
        s.add(UserOrder(user_id=PLAYER_VK, order_id=o.id))
        s.commit()
        oid = o.id
    finally:
        s.close()

    res = admin_client.post(f"/api/admin/players/{PLAYER_VK}/restart")
    assert res.status_code == 200

    s = TestingSessionLocal()
    try:
        assert s.query(OrderReq).filter(OrderReq.id == oid).count() == 1
        assert s.query(UserOrder).filter(UserOrder.user_id == PLAYER_VK).count() == 0
    finally:
        s.close()
