from __future__ import annotations
from sqlalchemy import (
    CheckConstraint, Column, Integer, String, Boolean, Text, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


PRODUCTION_KINDS = ("alchemy", "sewing", "workshop", "barnyard", "kassa")
PRODUCTION_NAMES = {"alchemy": "Стол зельеварения", "sewing": "Шатёр портнихи", "workshop": "Мастерская", "barnyard": "Шатёр скотного двора", "kassa": "Шатёр-касса"}

KASSA_KIND = "kassa"

MAX_PLOT_QTY = 20

CARD_DRAW_RULES = {
    "plant_1": (1, False),
    "plant_2": (2, True),
    "plant_3": (3, True),
    "tent_sewing": (3, True),
    "tent_workshop": (4, True),
    "tent_alchemy": (5, True),
    "tent_barnyard": (2, True),
}

CONTEXT_TYPES = (
    "plant_grow", "recipe_study", "production",
    "animal_build", "animal_produce", "tent_build", "pet_settle",
    "house_material", "house_build",
)

WITCH_HOUSE_KIND = "witch_house"
HOUSE_MATERIALS = ("glass", "wood", "nails", "pipes", "bricks", "paint")
HOUSE_MATERIAL_NAMES = {
    "glass": "Стекло",
    "wood": "Древесина",
    "nails": "Гвозди",
    "pipes": "Трубы",
    "bricks": "Кирпичи",
    "paint": "Краска",
}
HOUSE_CARDS_TO_DRAW = 5


class ProductionTemplate(Base):
    __tablename__ = "production_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    required = Column(Integer, nullable=False, default=500, server_default="500")
    cards_to_draw = Column(Integer, nullable=False, default=3, server_default="3")
    surcharge = Column(Integer, nullable=False, default=30, server_default="30")
    processing_crystal = Column(Integer, nullable=False, default=0, server_default="0")
    image_url = Column(String, nullable=True)


class User(Base):
    __tablename__ = "users"

    vk_id = Column(Integer, primary_key=True)
    role = Column(String, nullable=False, default="player", server_default="player")
    status = Column(String, nullable=False, default="active", server_default="active")
    display_name = Column(String, nullable=True)
    crosses_balance = Column(Integer, nullable=False, default=0, server_default="0")
    crosses_total = Column(Integer, nullable=False, default=0, server_default="0")
    coins = Column(Integer, nullable=False, default=0, server_default="0")
    round = Column(Integer, nullable=False, default=1, server_default="1")
    level = Column(Integer, nullable=False, default=0, server_default="0")
    unlocked_barnyard = Column(Integer, nullable=False, default=0, server_default="0")
    unlocked_pets = Column(Integer, nullable=False, default=0, server_default="0")
    unlocked_plot_level = Column(Integer, nullable=False, default=1, server_default="1")
    unlocked_garden_level = Column(Integer, nullable=False, default=0, server_default="0")
    dice_norm = Column(Integer, nullable=True)
    animal_product_norm = Column(Integer, nullable=True)
    study_norm_l1 = Column(Integer, nullable=True)
    study_norm_l2 = Column(Integer, nullable=True)
    study_norm_l3 = Column(Integer, nullable=True)
    production_norm_l1 = Column(Integer, nullable=True)
    production_norm_l2 = Column(Integer, nullable=True)
    production_norm_l3 = Column(Integer, nullable=True)
    onboarding_done = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    plots = relationship("Plot", back_populates="user", cascade="all, delete-orphan")
    productions = relationship("Production", back_populates="user", cascade="all, delete-orphan")
    inventory = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")
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


class UserPlantNorm(Base):
    __tablename__ = "user_plant_norms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    norm_per_unit = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "plant_id", name="uq_userplantnorm_user_plant"),
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


LOCATION_CODES = ("infirmary", "brewery")
LOCATION_NAMES = {"infirmary": "Лечебница", "brewery": "Зельеварение"}


class AllowedPlayer(Base):
    __tablename__ = "allowed_players"

    vk_id = Column(Integer, primary_key=True)
    screen_name = Column(String, nullable=True)
    added_by = Column(Integer, ForeignKey("users.vk_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class UserDlcUnlock(Base):
    __tablename__ = "user_dlc_unlocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    location_code = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "location_code", name="uq_userdlcunlock_user_location"),
    )


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
    cell_id = Column(Integer, ForeignKey("field_cells.id", ondelete="SET NULL"), nullable=True)
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
    image_harvested_url = Column(String, nullable=True)

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
    norm_revealed = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    cell_id = Column(Integer, ForeignKey("field_cells.id", ondelete="SET NULL"), nullable=True)
    plant_bed_id = Column(Integer, ForeignKey("plant_beds.id", ondelete="SET NULL"), nullable=True)

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
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="SET NULL"), nullable=True, unique=True)
    animal_id = Column(Integer, ForeignKey("animals.id", ondelete="SET NULL"), nullable=True)
    pet_id = Column(Integer, ForeignKey("pets.id", ondelete="SET NULL"), nullable=True)
    stars = Column(Integer, nullable=False, default=1, server_default="1")
    production_kind = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    plant = relationship("Plant", back_populates="products")
    animal = relationship("Animal")
    pet = relationship("Pet")


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
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    potion_recipe_id = Column(Integer, ForeignKey("potion_recipes.id", ondelete="CASCADE"), nullable=True)
    qty = Column(Integer, nullable=False)
    reward_coins = Column(Integer, nullable=False, default=0, server_default="0")
    customer = Column(String, nullable=True)
    customer_phrase = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="open", server_default="open")
    name = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    product = relationship("Product")
    potion_recipe = relationship("PotionRecipe")


class UserOrder(Base):
    __tablename__ = "user_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    taken_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)
    reward_coins = Column(Integer, nullable=False, default=0, server_default="0")

    order = relationship("OrderReq")

    __table_args__ = (
        UniqueConstraint("user_id", "order_id", name="uq_userorder_user_order"),
    )


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
    clinic_animal_id = Column(Integer, ForeignKey("patient_animals.id", ondelete="CASCADE"), nullable=True)
    clinic_stage = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    cells = relationship("FieldCell", back_populates="field", cascade="all, delete-orphan")
    tents = relationship("Tent", back_populates="field", cascade="all, delete-orphan")
    plants = relationship("FieldPlant", back_populates="field", cascade="all, delete-orphan")
    plant_beds = relationship("PlantBed", back_populates="field", cascade="all, delete-orphan")
    pet_zones = relationship("PetZone", back_populates="field", cascade="all, delete-orphan")
    animals = relationship("FieldAnimal", back_populates="field", cascade="all, delete-orphan")
    pets = relationship("FieldPet", back_populates="field", cascade="all, delete-orphan")
    potion_recipes = relationship("FieldPotionRecipe", back_populates="field", cascade="all, delete-orphan")
    brewery_zones = relationship("BreweryZone", back_populates="field", cascade="all, delete-orphan")
    gather_cells = relationship("GatherCell", back_populates="field", cascade="all, delete-orphan")
    trade_cells = relationship("TradeCell", back_populates="field", cascade="all, delete-orphan")
    part_cells = relationship("ClinicPartCell", back_populates="field", cascade="all, delete-orphan")
    infirmary_zones = relationship("InfirmaryZone", back_populates="field", cascade="all, delete-orphan")
    clinic_animal = relationship("PatientAnimal", back_populates="scenes")

    __table_args__ = (
        UniqueConstraint("clinic_animal_id", "clinic_stage", name="uq_field_clinic_animal_stage"),
    )


class FieldPlant(Base):
    __tablename__ = "field_plants"

    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, primary_key=True)

    field = relationship("Field", back_populates="plants")
    plant = relationship("Plant")


class FieldAnimal(Base):
    __tablename__ = "field_animals"

    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id", ondelete="CASCADE"), nullable=False, primary_key=True)

    field = relationship("Field", back_populates="animals")
    animal = relationship("Animal")


class FieldPet(Base):
    __tablename__ = "field_pets"

    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, primary_key=True)

    field = relationship("Field", back_populates="pets")
    pet = relationship("Pet")


class FieldPotionRecipe(Base):
    __tablename__ = "field_potion_recipes"

    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("potion_recipes.id", ondelete="CASCADE"), nullable=False, primary_key=True)

    field = relationship("Field", back_populates="potion_recipes")
    recipe = relationship("PotionRecipe")


BREWERY_ZONE_KINDS = ("cauldron", "jar", "ingredient", "recipe_card")
BREWERY_MAX_INGREDIENT_CELLS = 6


class BreweryZone(Base):
    __tablename__ = "brewery_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    zone_kind = Column(String, nullable=False)
    col1 = Column(Integer, nullable=False)
    row1 = Column(Integer, nullable=False)
    col2 = Column(Integer, nullable=False)
    row2 = Column(Integer, nullable=False)
    image_url = Column(String, nullable=True)
    recipe_id = Column(Integer, ForeignKey("potion_recipes.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    field = relationship("Field", back_populates="brewery_zones")
    recipe = relationship("PotionRecipe")


INFIRMARY_ZONE_KINDS = ("book",)


class InfirmaryZone(Base):
    __tablename__ = "infirmary_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    zone_kind = Column(String, nullable=False)
    col1 = Column(Integer, nullable=False)
    row1 = Column(Integer, nullable=False)
    col2 = Column(Integer, nullable=False)
    row2 = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    field = relationship("Field", back_populates="infirmary_zones")


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


class TentBuild(Base):
    __tablename__ = "tent_builds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    tent_id = Column(Integer, ForeignKey("tents.id", ondelete="CASCADE"), nullable=False)
    build_status = Column(String, nullable=False, default="slot", server_default="slot")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    required = Column(Integer, nullable=False, default=0, server_default="0")
    crystal_color = Column(String, nullable=True)
    crystal_count = Column(Integer, nullable=True)
    drawn_cards_json = Column(Text, nullable=True)
    norm_revealed = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "tent_id", name="uq_tentbuild_user_tent"),
    )


class HouseBuild(Base):
    __tablename__ = "house_builds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    tent_id = Column(Integer, ForeignKey("tents.id", ondelete="CASCADE"), nullable=False)
    phase = Column(String, nullable=False, default="materials", server_default="materials")
    current_material = Column(String, nullable=True)
    current_die = Column(Integer, nullable=True)
    last_die = Column(Integer, nullable=True)
    current_required = Column(Integer, nullable=True)
    collected_json = Column(Text, nullable=False, default="[]", server_default="[]")
    cards_json = Column(Text, nullable=True)
    required = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "tent_id", name="uq_housebuild_user_tent"),
    )


class PlantBed(Base):
    __tablename__ = "plant_beds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col1 = Column(Integer, nullable=False)
    row1 = Column(Integer, nullable=False)
    col2 = Column(Integer, nullable=False)
    row2 = Column(Integer, nullable=False)
    plant_category = Column(String, nullable=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="SET NULL"), nullable=True)
    occupant_user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    field = relationship("Field", back_populates="plant_beds")
    plant = relationship("Plant")


class PetZone(Base):
    __tablename__ = "pet_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col1 = Column(Integer, nullable=False)
    row1 = Column(Integer, nullable=False)
    col2 = Column(Integer, nullable=False)
    row2 = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    field = relationship("Field", back_populates="pet_zones")


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
    image_harvested_url = Column(String, nullable=True)


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
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=True)
    source_product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False, default=1, server_default="1")

    plant = relationship("Plant")
    source_product = relationship("Product", foreign_keys=[source_product_id])
    product = relationship("Product", foreign_keys=[product_id])

    __table_args__ = (
        UniqueConstraint("plant_id", name="uq_recipe_plant"),
        UniqueConstraint("source_product_id", name="uq_recipe_source_product"),
    )


class UserRecipe(Base):
    __tablename__ = "user_recipes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="locked", server_default="locked")
    required = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_userrecipe_user_recipe"),
    )


class CraftSession(Base):
    __tablename__ = "craft_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=True)
    source_product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    qty = Column(Integer, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    required = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(String, nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class LevelGate(Base):
    __tablename__ = "level_gates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False, unique=True)
    coins_required = Column(Integer, nullable=False, default=0, server_default="0")
    plots_required = Column(Integer, nullable=False, default=0, server_default="0")
    unlock_type = Column(String, nullable=True)
    image_url = Column(String, nullable=True)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    image_url = Column(String, nullable=True)


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
    cell_id = Column(Integer, ForeignKey("field_cells.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    animal = relationship("Animal")


class BarnyardStorage(Base):
    __tablename__ = "barnyard_storage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False, default=0, server_default="0")

    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_barnyard_storage_user_product"),
    )


class BarnyardWithdrawal(Base):
    __tablename__ = "barnyard_withdrawals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False)
    required = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(String, nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    product = relationship("Product")


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
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    card_image_url = Column(String, nullable=True)


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
    used = Column(Boolean, nullable=False, default=False, server_default="0")
    acquired_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    condition_kind = Column(String, nullable=False)
    condition_value = Column(Integer, nullable=False, default=1, server_default="1")
    production_code = Column(String, nullable=True)
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


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    level = Column(String, nullable=False, default="info", server_default="info")
    event = Column(String, nullable=True)
    method = Column(String, nullable=True)
    path = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=True)
    client_ip = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow, index=True)


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")


class UserIngredient(Base):
    __tablename__ = "user_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False, default=0, server_default="0")

    ingredient = relationship("Ingredient")

    __table_args__ = (
        UniqueConstraint("user_id", "ingredient_id", name="uq_useringredient_user_ingredient"),
    )


GATHER_WINDOW_KINDS = ("morning", "day", "night", "always")


class GatherCell(Base):
    __tablename__ = "gather_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col = Column(Integer, nullable=False)
    row = Column(Integer, nullable=False)
    window = Column(String, nullable=False, default="always", server_default="always")

    field = relationship("Field")
    ingredients = relationship("GatherCellIngredient", back_populates="gather_cell", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("field_id", "col", "row", name="uq_gathercell_field_col_row"),
    )


class GatherCellIngredient(Base):
    __tablename__ = "gather_cell_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gather_cell_id = Column(Integer, ForeignKey("gather_cells.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)

    gather_cell = relationship("GatherCell", back_populates="ingredients")
    ingredient = relationship("Ingredient")

    __table_args__ = (
        UniqueConstraint("gather_cell_id", "ingredient_id", name="uq_gathercell_ingredient"),
    )


class UserGatherLog(Base):
    __tablename__ = "user_gather_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    gather_cell_id = Column(Integer, ForeignKey("gather_cells.id", ondelete="CASCADE"), nullable=False)
    date = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "gather_cell_id", "date", name="uq_usergatherlog_user_cell_date"),
    )


class TradeCell(Base):
    __tablename__ = "trade_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col = Column(Integer, nullable=False)
    row = Column(Integer, nullable=False)

    field = relationship("Field")
    ingredients = relationship("TradeCellIngredient", back_populates="trade_cell", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("field_id", "col", "row", name="uq_tradecell_field_col_row"),
    )


class TradeCellIngredient(Base):
    __tablename__ = "trade_cell_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_cell_id = Column(Integer, ForeignKey("trade_cells.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)

    trade_cell = relationship("TradeCell", back_populates="ingredients")
    ingredient = relationship("Ingredient")

    __table_args__ = (
        UniqueConstraint("trade_cell_id", "ingredient_id", name="uq_tradecell_ingredient"),
    )


PATIENT_LEVELS = (1, 2, 3)
PATIENT_STATE_STATUSES = ("sick", "diagnosed", "treated", "released")


class Remedy(Base):
    __tablename__ = "remedies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)

    recipe_items = relationship("RemedyRecipeItem", back_populates="remedy", cascade="all, delete-orphan")


class RemedyRecipeItem(Base):
    __tablename__ = "remedy_recipe_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    remedy_id = Column(Integer, ForeignKey("remedies.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=True)
    plant_id = Column(Integer, ForeignKey("plants.id", ondelete="CASCADE"), nullable=True)
    qty = Column(Integer, nullable=False, default=1, server_default="1")

    remedy = relationship("Remedy", back_populates="recipe_items")
    ingredient = relationship("Ingredient")
    plant = relationship("Plant")

    __table_args__ = (
        UniqueConstraint("remedy_id", "ingredient_id", name="uq_remedyrecipe_remedy_ingredient"),
        UniqueConstraint("remedy_id", "plant_id", name="uq_remedyrecipe_remedy_plant"),
        CheckConstraint(
            "(ingredient_id IS NOT NULL AND plant_id IS NULL) OR (ingredient_id IS NULL AND plant_id IS NOT NULL)",
            name="ck_remedyrecipe_single_source",
        ),
    )


class Disease(Base):
    __tablename__ = "diseases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    remedy_id = Column(Integer, ForeignKey("remedies.id", ondelete="SET NULL"), nullable=True)

    remedy = relationship("Remedy")
    symptoms = relationship("DiseaseSymptom", back_populates="disease", cascade="all, delete-orphan")


class DiseaseSymptom(Base):
    __tablename__ = "disease_symptoms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disease_id = Column(Integer, ForeignKey("diseases.id", ondelete="CASCADE"), nullable=False)
    part_code = Column(String, nullable=False)
    text = Column(Text, nullable=False)

    disease = relationship("Disease", back_populates="symptoms")


class ClinicAnimalType(Base):
    __tablename__ = "clinic_animal_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")

    animals = relationship("PatientAnimal", back_populates="animal_type")


class PatientAnimal(Base):
    __tablename__ = "patient_animals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False, default=1, server_default="1")
    card_image_url = Column(String, nullable=True)
    animal_image_url = Column(String, nullable=True)
    animal_type_id = Column(Integer, ForeignKey("clinic_animal_types.id", ondelete="SET NULL"), nullable=True)
    disease_id = Column(Integer, ForeignKey("diseases.id", ondelete="SET NULL"), nullable=True)

    disease = relationship("Disease")
    animal_type = relationship("ClinicAnimalType", back_populates="animals")
    scenes = relationship("Field", back_populates="clinic_animal", cascade="all, delete-orphan")


class ClinicPartCell(Base):
    __tablename__ = "clinic_part_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col = Column(Integer, nullable=False)
    row = Column(Integer, nullable=False)
    part_code = Column(String, nullable=False)

    field = relationship("Field", back_populates="part_cells")

    __table_args__ = (
        UniqueConstraint("field_id", "col", "row", name="uq_clinicpartcell_field_col_row"),
    )


class UserPatientState(Base):
    __tablename__ = "user_patient_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patient_animals.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="sick", server_default="sick")
    current_field_id = Column(Integer, ForeignKey("fields.id", ondelete="SET NULL"), nullable=True)
    healed_at = Column(DateTime, nullable=True)
    penalty_due = Column(Integer, nullable=False, default=0, server_default="0")

    patient = relationship("PatientAnimal")

    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", name="uq_userpatientstate_user_patient"),
    )


class UserExamineLog(Base):
    __tablename__ = "user_examine_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patient_animals.id", ondelete="CASCADE"), nullable=False)
    part_code = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", "part_code", name="uq_userexaminelog_user_patient_part"),
    )


class UserRemedyCard(Base):
    __tablename__ = "user_remedy_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patient_animals.id", ondelete="CASCADE"), nullable=False)
    remedy_id = Column(Integer, ForeignKey("remedies.id", ondelete="CASCADE"), nullable=False)

    patient = relationship("PatientAnimal")
    remedy = relationship("Remedy")

    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", name="uq_userremedycard_user_patient"),
    )


class UserCard(Base):
    __tablename__ = "user_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patient_animals.id", ondelete="CASCADE"), nullable=False)
    earned_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    patient = relationship("PatientAnimal")

    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", name="uq_usercard_user_patient"),
    )


REMEDY_DEVICE_LIMIT = 5


class RemedyDeviceCell(Base):
    __tablename__ = "remedy_device_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    col = Column(Integer, nullable=False)
    row = Column(Integer, nullable=False)
    col2 = Column(Integer, nullable=False, default=0, server_default="0")
    row2 = Column(Integer, nullable=False, default=0, server_default="0")
    install_cards = Column(Integer, nullable=False, default=10, server_default="10")

    field = relationship("Field")
    remedies = relationship("RemedyDeviceRemedy", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("field_id", "col", "row", name="uq_remedydevicecell_field_col_row"),
    )


class RemedyDeviceRemedy(Base):
    __tablename__ = "remedy_device_remedies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cell_id = Column(Integer, ForeignKey("remedy_device_cells.id", ondelete="CASCADE"), nullable=False)
    remedy_id = Column(Integer, ForeignKey("remedies.id", ondelete="CASCADE"), nullable=False)

    remedy = relationship("Remedy")

    __table_args__ = (
        UniqueConstraint("cell_id", "remedy_id", name="uq_remedydeviceremedy_cell_remedy"),
    )


class UserRemedyDevice(Base):
    __tablename__ = "user_remedy_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(Integer, ForeignKey("remedy_device_cells.id", ondelete="CASCADE"), nullable=False)
    build_status = Column(String, nullable=False, default="building", server_default="building")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    required = Column(Integer, nullable=False, default=0, server_default="0")
    drawn_cards_json = Column(Text, nullable=True)
    brew_card_id = Column(Integer, ForeignKey("user_remedy_cards.id", ondelete="SET NULL"), nullable=True)
    brew_required = Column(Integer, nullable=True)
    brew_accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    brew_dice_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    cell = relationship("RemedyDeviceCell")
    brew_card = relationship("UserRemedyCard")

    __table_args__ = (
        UniqueConstraint("user_id", "cell_id", name="uq_userremedydevice_user_cell"),
    )


class UserRemedy(Base):
    __tablename__ = "user_remedies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    remedy_id = Column(Integer, ForeignKey("remedies.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False, default=0, server_default="0")

    remedy = relationship("Remedy")

    __table_args__ = (
        UniqueConstraint("user_id", "remedy_id", name="uq_userremedy_user_remedy"),
    )


FOREST_PET_CODES = ("vydra", "otter")


class PetActionLog(Base):
    __tablename__ = "pet_action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)
    date = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "pet_id", "action", "date", name="uq_practionlog_user_pet_action_date"),
    )


class PetForestTask(Base):
    __tablename__ = "pet_forest_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.vk_id", ondelete="CASCADE"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    date = Column(String, nullable=False)
    required = Column(Integer, nullable=False, default=200, server_default="200")
    accumulated = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(String, nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime, nullable=False, default=__import__("datetime").datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "pet_id", "date", name="uq_petforesttask_user_pet_date"),
    )
