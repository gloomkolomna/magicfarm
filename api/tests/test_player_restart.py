from tests.conftest import TestingSessionLocal, make_user_client

PLAYER_VK = 600

_MODELS = [
    "UserPlantNorm", "UserCrystalNorm", "UserAchievement", "UserPotion", "Cauldron",
    "UserPet", "BarnyardSlot", "BarnyardStorage", "BarnyardWithdrawal", "CraftSession",
    "UserRecipe", "HouseBuild", "TentBuild", "UserOrder", "Inventory", "Production",
    "Plot", "StitchReport", "UserIngredient", "UserCard", "UserPatientState",
    "UserRemedy", "UserRemedyCard", "UserRemedyDevice", "UserExamineLog",
    "UserGatherLog", "PetActionLog", "PetForestTask", "Shaker",
    "UserDlcStoryView", "Notification",
]


def _count(model, vk_id):
    s = TestingSessionLocal()
    try:
        return s.query(model).filter(model.user_id == vk_id).count()
    finally:
        s.close()


def _seed_everything(vk_id):
    from models import (
        BarnyardSlot, BarnyardStorage, BarnyardWithdrawal, Cauldron, CraftSession,
        Field, GatherCell, HouseBuild, Ingredient, Inventory, Notification, OrderReq,
        PatientAnimal, Pet, PetActionLog, PetForestTask, Plot, Production, Remedy,
        RemedyDeviceCell, Shaker, StitchReport, Tent, TentBuild, User, UserAchievement,
        UserCard, UserCrystalNorm, UserDlcStoryView, UserDlcUnlock, UserExamineLog,
        UserGatherLog, UserIngredient, UserOrder, UserPatientState, UserPet,
        UserPlantNorm, UserPotion, UserRecipe, UserRemedy, UserRemedyCard,
        UserRemedyDevice,
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
        u.story_seen = True
        u.dice_norm = 55
        u.study_norm_l1 = 500
        u.production_norm_l1 = 100

        f = Field(code=f"restart_{vk_id}", name="Поле")
        s.add(f)
        s.flush()
        t = Tent(field_id=f.id, name="Шатёр", kind="alchemy", col1=0, row1=0, col2=1, row2=1)
        s.add(t)
        s.flush()
        gc = GatherCell(field_id=f.id, col=1, row=1)
        rdc = RemedyDeviceCell(field_id=f.id, col=2, row=1)
        s.add_all([gc, rdc])
        s.flush()

        ing = Ingredient(code=f"restart_ing_{vk_id}", name="Ингр")
        patient = PatientAnimal(code=f"restart_pat_{vk_id}", name="Пациент")
        remedy = Remedy(code=f"restart_rem_{vk_id}", name="Лекарь")
        pet = Pet(code=f"restart_pet_{vk_id}", name="Питомец")
        s.add_all([ing, patient, remedy, pet])
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
        s.add(BarnyardStorage(user_id=vk_id, product_id=1, qty=5))
        s.add(BarnyardWithdrawal(user_id=vk_id, product_id=1, qty=2, required=10))
        s.add(UserPet(user_id=vk_id, pet_id=pet.id))
        s.add(Cauldron(user_id=vk_id))
        s.add(UserPotion(user_id=vk_id, potion_recipe_id=1))
        s.add(UserAchievement(user_id=vk_id, achievement_id=1))
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ing.id, qty=3))
        s.add(UserCard(user_id=vk_id, patient_id=patient.id))
        s.add(UserPatientState(user_id=vk_id, patient_id=patient.id))
        s.add(UserRemedy(user_id=vk_id, remedy_id=remedy.id, qty=2))
        s.add(UserRemedyCard(user_id=vk_id, patient_id=patient.id, remedy_id=remedy.id))
        s.add(UserRemedyDevice(user_id=vk_id, cell_id=rdc.id))
        s.add(UserExamineLog(user_id=vk_id, patient_id=patient.id, part_code="head"))
        s.add(UserGatherLog(user_id=vk_id, gather_cell_id=gc.id, date="2026-01-01"))
        s.add(PetActionLog(user_id=vk_id, pet_id=pet.id, action="feed", date="2026-01-01"))
        s.add(PetForestTask(user_id=vk_id, pet_id=pet.id, date="2026-01-01", required=200))
        s.add(Shaker(user_id=vk_id, status="empty"))
        s.add(UserDlcUnlock(user_id=vk_id, location_code="brewery"))
        s.add(UserDlcStoryView(user_id=vk_id, location_code="brewery"))
        s.add(Notification(user_id=vk_id, text="тест"))

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
        assert u.story_seen is False
        assert u.dice_norm is None
        assert u.study_norm_l1 is None
        assert u.production_norm_l1 is None
    finally:
        s.close()


def test_restart_removes_photo_files(admin_client, monkeypatch):
    from routes import admin_players
    from models import StitchReport

    with make_user_client(PLAYER_VK, "player") as c:
        c.get("/api/me")
    removed = []
    monkeypatch.setattr(admin_players, "remove_upload", lambda url: removed.append(url))

    s = TestingSessionLocal()
    try:
        s.add(StitchReport(
            user_id=PLAYER_VK, amount=10, status="accepted",
            photo_after_url="/api/uploads/a.jpg", photo_after_thumb_url="/api/uploads/ta.jpg",
            photo_before_url="/api/uploads/b.jpg", photo_before_thumb_url="/api/uploads/tb.jpg",
        ))
        s.commit()
    finally:
        s.close()

    res = admin_client.post(f"/api/admin/players/{PLAYER_VK}/restart")
    assert res.status_code == 200

    assert sorted(removed) == [
        "/api/uploads/a.jpg", "/api/uploads/b.jpg",
        "/api/uploads/ta.jpg", "/api/uploads/tb.jpg",
    ]


def test_restart_cancels_cross_player_trades_and_gifts(admin_client):
    from models import Gift, Inventory, TradeOffer

    with make_user_client(610, "player") as c:
        c.get("/api/me")
    with make_user_client(603, "player") as p:
        p.get("/api/me")

    s = TestingSessionLocal()
    try:
        row = Inventory(user_id=603, plant_id=1, qty=4)
        s.add(row)
        prod = Inventory(user_id=610, product_id=1, qty=2)
        s.add(prod)
        s.commit()
    finally:
        s.close()

    with make_user_client(603, "player") as p:
        r = p.post("/api/trades", json={
            "to_user_id": 610,
            "items": [{"kind": "plant", "item_id": 1, "qty": 3, "direction": "give"}],
        })
        assert r.status_code == 201, r.text
        r = p.post("/api/gifts", json={"to_user_id": 610, "kind": "plant", "item_id": 1, "qty": 1})
        assert r.status_code == 201, r.text
        assert p.post("/api/chat/with/610", json={"text": "привет"}).status_code == 201
    with make_user_client(610, "player") as c:
        r = c.post("/api/gifts", json={"to_user_id": 603, "kind": "product", "item_id": 1, "qty": 2})
        assert r.status_code == 201, r.text
        gift_to_partner_id = r.json()["id"]
        assert c.post("/api/chat/with/603", json={"text": "ответ"}).status_code == 201

    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 603, Inventory.plant_id == 1).first()
        assert (row.qty if row else 0) == 0
    finally:
        s.close()

    res = admin_client.post("/api/admin/players/610/restart")
    assert res.status_code == 200, res.text

    s = TestingSessionLocal()
    try:
        assert s.query(TradeOffer).filter(
            (TradeOffer.from_user_id == 610) | (TradeOffer.to_user_id == 610)
        ).count() == 0
        assert s.query(Inventory).filter(Inventory.user_id == 603, Inventory.plant_id == 1).first().qty == 4
        assert s.query(Inventory).filter(Inventory.user_id == 610).count() == 0
        kept = s.query(Gift).filter(Gift.id == gift_to_partner_id).first()
        assert kept is not None and kept.claimed_at is None
        assert s.query(Gift).filter(Gift.to_user_id == 610).count() == 0
        from models import ChatMessage
        assert s.query(ChatMessage).filter(
            (ChatMessage.from_user_id == 610) | (ChatMessage.to_user_id == 610)
        ).count() == 0
    finally:
        s.close()

    with make_user_client(603, "player") as p:
        notifs = p.get("/api/notifications").json()
        assert len(notifs) == 3
        restarted = [n for n in notifs if "перезапущен" in n["text"]]
        assert len(restarted) == 2
        assert all(n["peer_vk_id"] == 610 for n in restarted)
        assert len([n for n in notifs if "подарок" in n["text"] and "перезапущен" not in n["text"]]) == 1
        assert p.post(f"/api/gifts/{gift_to_partner_id}/claim").status_code == 200
    s = TestingSessionLocal()
    try:
        assert s.query(Inventory).filter(Inventory.user_id == 603, Inventory.product_id == 1).first().qty == 2
    finally:
        s.close()


def test_restart_keeps_admin_grants(admin_client):
    from models import AllowedPlayer, UserDlcUnlock

    with make_user_client(PLAYER_VK, "player") as c:
        c.get("/api/me")
    res = admin_client.post(f"/api/admin/players/{PLAYER_VK}/dlc", json={"location_code": "brewery"})
    assert res.status_code == 201, res.text

    s = TestingSessionLocal()
    try:
        s.add(AllowedPlayer(vk_id=PLAYER_VK))
        s.commit()
    finally:
        s.close()

    res = admin_client.post(f"/api/admin/players/{PLAYER_VK}/restart")
    assert res.status_code == 200, res.text

    s = TestingSessionLocal()
    try:
        assert s.query(UserDlcUnlock).filter(UserDlcUnlock.user_id == PLAYER_VK).count() == 1
        assert s.query(AllowedPlayer).filter(AllowedPlayer.vk_id == PLAYER_VK).count() == 1
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
