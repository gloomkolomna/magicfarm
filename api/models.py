from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


PRODUCTION_KINDS = ("alchemy", "sewing", "workshop")
PRODUCTION_NAMES = {"alchemy": "Стол зельеварения", "sewing": "Шатёр портнихи", "workshop": "Мастерская"}

MAX_PLOT_QTY = 20

CARD_DRAW_RULES = {
    "plant_1": (1, False),
    "plant_2": (2, True),
    "plant_3": (3, True),
    "tent_sewing": (3, True),
    "tent_workshop": (4, True),
    "tent_alchemy": (5, True),
}

CONTEXT_TYPES = (
    "plant_grow", "recipe_study", "production",
    "animal_build", "animal_produce", "tent_build", "pet_settle",
)


class ProductionTemplate(Base):
    __tablename__ = "production_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    required = Column(Integer, nullable=False, default=500, server_default="500")
    cards_to_draw = Column(Integer, nullable=False, default=3, server_default="3")
    surcharge = Column(Integer, nullable=False, default=30, server_default="30")
    image_url = Column(String, nullable=True)


class User(Base):
    __tablename__ = "users"

    vk_id = Column(Integer, primary_key=True)
    role = Column(String, nullable=False, default="player", server_default="player")
    display_name = Column(String, nullable=True)
    crosses_balance = Column(Integer, nullable=False, default=0, server_default="0")
    crosses_total = Column(Integer, nullable=False, default=0, server_default="0")
    coins = Column(Integer, nullable=False, default=0, server_default="0")
    round = Column(Integer, nullable=False, default=1, server_default="1")
    level = Column(Integer, nullable=False, default=0, server_default="0")
    route_variant = Column(Integer, nullable=True)
    onboarding_done = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    plots = relationship("Plot", back_populates="user", cascade="all, delete-orphan")
    productions = relationship("Production", back_populates="user", cascade="all, delete-orphan")
    inventory = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("OrderReq", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("StitchReport", foreign_keys="StitchReport.user_id", cascade="all, delete-orphan")
    crystal_norms = relationship("UserCrystalNorm", back_populates="user", cascade="all, delete-orphan")


class UserCrystalNorm(Base):
    __tablename__ = "user_crystal_norms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    color = Column(String, nullable=False)
    count = Column(Integer, nullable=False)
    value = Column(Integer, nullable=False)

    user = relationship("User", back_populates="crystal_norms")

    __table_args__ = (
        UniqueConstraint("user_id", "color", "count", name="uq_usercrystalnorm_user_color_count"),
    )


class CrystalNormImage(Base):
    __tablename__ = "crystal_norm_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    color = Column(String, nullable=False)
    count = Column(Integer, nullable=False)
    image_url = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("color", "count", name="uq_crystalnormimage_color_count"),
    )


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class StitchReport(Base):
    __tablename__ = "stitch_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
    photo_before_url = Column(String, nullable=True)
    photo_after_url = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    context_type = Column(String, nullable=True)
    context_id = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="pending", server_default="pending")
    reviewer_id = Column(Integer, ForeignKey("users.vk_id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    category = Column(String, nullable=False, default="garden", server_default="garden")
    level = Column(Integer, nullable=False, default=1, server_default="1")
    norm_per_crystal = Column(Integer, nullable=False, default=100, server_default="100")
    bonus_text = Column(Text, nullable=True)
    bonus_kind = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    stitch_condition = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    image_young_url = Column(String, nullable=True)
    image_grown_url = Column(String, nullable=True)

    plots = relationship("Plot", back_populates="plant")
    products = relationship("Product", back_populates="plant")


class Plot(Base):
    __tablename__ = "plots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(String, nullable=False, default="planted", server_default="planted")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    required = Column(Integer, nullable=False, default=0, server_default="0")
    crystal_color = Column(String, nullable=True)
    crystal_count = Column(Integer, nullable=True)
    drawn_cards_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    cell_id = Column(Integer, ForeignKey("field_cells.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="plots")
    plant = relationship("Plant", back_populates="plots")


class Production(Base):
    __tablename__ = "productions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="installed", server_default="installed")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    required = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)
    tent_id = Column(Integer, ForeignKey("tents.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="productions")

    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_production_user_kind"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="SET NULL"), nullable=True)
    stars = Column(Integer, nullable=False, default=1, server_default="1")
    production_kind = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    plant = relationship("Plant", back_populates="products")


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=True)
    qty = Column(Integer, nullable=False, default=0, server_default="0")

    user = relationship("User", back_populates="inventory")
    product = relationship("Product")
    plant = relationship("Plant")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_inventory_user_product"),
        UniqueConstraint("user_id", "plant_id", name="uq_inventory_user_plant"),
    )


class OrderReq(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False)
    reward_coins = Column(Integer, nullable=False, default=0, server_default="0")
    customer = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open", server_default="open")
    name = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    product = relationship("Product")


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    client_ip = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class Field(Base):
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    map_url = Column(String, nullable=True)
    cols = Column(Integer, nullable=False, default=6, server_default="6")
    rows = Column(Integer, nullable=False, default=4, server_default="4")
    grid_color = Column(String, nullable=False, default="#2a1a0e", server_default="#2a1a0e")
    plant_category = Column(String, nullable=True)
    min_level = Column(Integer, nullable=False, default=0, server_default="0")
    field_kind = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    cells = relationship("FieldCell", back_populates="field", cascade="all, delete-orphan")
    tents = relationship("Tent", back_populates="field", cascade="all, delete-orphan")
    plants = relationship("FieldPlant", back_populates="field", cascade="all, delete-orphan")


class FieldPlant(Base):
    __tablename__ = "field_plants"

    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, primary_key=True)

    field = relationship("Field", back_populates="plants")
    plant = relationship("Plant")


class FieldCell(Base):
    __tablename__ = "field_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col = Column(Integer, nullable=False)
    row = Column(Integer, nullable=False)
    kind = Column(String, nullable=False, default="empty", server_default="empty")
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="SET NULL"), nullable=True)
    occupant_user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="SET NULL"), nullable=True)
    tent_id = Column(Integer, ForeignKey("tents.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    field = relationship("Field", back_populates="cells")
    plant = relationship("Plant")

    __table_args__ = (
        UniqueConstraint("field_id", "col", "row", name="uq_fieldcell_field_col_row"),
    )


class Tent(Base):
    __tablename__ = "tents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    kind = Column(String, nullable=False, default="alchemy", server_default="alchemy")
    col1 = Column(Integer, nullable=False)
    row1 = Column(Integer, nullable=False)
    col2 = Column(Integer, nullable=False)
    row2 = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    builder_user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="SET NULL"), nullable=True)
    build_status = Column(String, nullable=False, default="slot", server_default="slot")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    required = Column(Integer, nullable=False, default=0, server_default="0")
    crystal_color = Column(String, nullable=True)
    crystal_count = Column(Integer, nullable=True)
    drawn_cards_json = Column(Text, nullable=True)

    field = relationship("Field", back_populates="tents")


class Animal(Base):
    __tablename__ = "animals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    product_name = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    image_url = Column(String, nullable=True)
    image_empty_pen_url = Column(String, nullable=True)
    image_pen_url = Column(String, nullable=True)


class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    bonus_kind = Column(String, nullable=True)
    bonus_description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)


class CrystalCard(Base):
    __tablename__ = "crystal_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    color = Column(String, nullable=False)
    value = Column(Integer, nullable=False)
    is_treasure = Column(Boolean, nullable=False, default=False, server_default="0")
    image_url = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("color", "value", "is_treasure", name="uq_crystalcard_color_value_treasure"),
    )


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False, default=1, server_default="1")

    plant = relationship("Plant")
    product = relationship("Product")


class UserRecipe(Base):
    __tablename__ = "user_recipes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="locked", server_default="locked")

    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_userrecipe_user_recipe"),
    )


class CraftSession(Base):
    __tablename__ = "craft_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    required = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(String, nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class LevelGate(Base):
    __tablename__ = "level_gates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    variant = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    coins_required = Column(Integer, nullable=False, default=0, server_default="0")
    plots_required = Column(Integer, nullable=False, default=0, server_default="0")
    rewards_json = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("variant", "level", name="uq_levelgate_variant_level"),
    )


class OrderTemplate(Base):
    __tablename__ = "order_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_kind = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False)
    reward_coins = Column(Integer, nullable=False, default=0, server_default="0")
    customer = Column(String, nullable=True)
    name = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    product = relationship("Product")


class BarnyardSlot(Base):
    __tablename__ = "barnyard_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    animal_id = Column(Integer, ForeignKey("animals.id", ondelete="CASCADE"), nullable=True)
    status = Column(String, nullable=False, default="empty", server_default="empty")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    required = Column(Integer, nullable=False, default=0, server_default="0")
    last_die = Column(Integer, nullable=True)
    drawn_cards_json = Column(Text, nullable=True)
    opening_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    animal = relationship("Animal")


class GameMedia(Base):
    __tablename__ = "game_media"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    kind = Column(String, nullable=False)
    url = Column(String, nullable=True)


class UserPet(Base):
    __tablename__ = "user_pets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(Integer, nullable=True)
    acquired_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    pet = relationship("Pet")

    __table_args__ = (
        UniqueConstraint("user_id", "pet_id", name="uq_userpet_user_pet"),
    )


class PotionRecipe(Base):
    __tablename__ = "potion_recipes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    level = Column(String, nullable=False)
    ingredient_slots = Column(Text, nullable=False)
    bonus_code = Column(String, nullable=True)
    reward_coins = Column(Integer, nullable=False, default=100, server_default="100")
    image_url = Column(String, nullable=True)


class Cauldron(Base):
    __tablename__ = "cauldrons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("potion_recipes.id", ondelete="CASCADE"), nullable=True)
    material = Column(String, nullable=False, default="tin", server_default="tin")
    capacity = Column(Integer, nullable=False, default=4, server_default="4")
    status = Column(String, nullable=False, default="empty", server_default="empty")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class CauldronSlot(Base):
    __tablename__ = "cauldron_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cauldron_id = Column(Integer, ForeignKey("cauldrons.id", ondelete="CASCADE"), nullable=False)
    slot_index = Column(Integer, nullable=False)
    item_type = Column(String, nullable=False)
    item_id = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("cauldron_id", "slot_index", name="uq_cauldronslot_cauldron_slot"),
    )


class UserPotion(Base):
    __tablename__ = "user_potions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    potion_recipe_id = Column(Integer, ForeignKey("potion_recipes.id", ondelete="CASCADE"), nullable=False)
    bonus_code = Column(String, nullable=True)
    activated = Column(Boolean, nullable=False, default=False, server_default="0")
    acquired_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "potion_recipe_id", name="uq_userpotion_user_recipe"),
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    condition_kind = Column(String, nullable=False)
    condition_value = Column(Integer, nullable=False, default=1, server_default="1")
    image_url = Column(String, nullable=True)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False)
    earned_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_userachieve_user_achieve"),
    )
