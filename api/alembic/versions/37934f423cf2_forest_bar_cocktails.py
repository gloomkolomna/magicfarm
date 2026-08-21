"""forest_bar_cocktails

Revision ID: 37934f423cf2
Revises: c8311485ce5d
Create Date: 2026-08-21 11:21:23.470886
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '37934f423cf2'
down_revision: Union[str, None] = 'c8311485ce5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS cocktail_recipes ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "code VARCHAR NOT NULL UNIQUE, "
        "name VARCHAR NOT NULL, "
        "description TEXT, "
        "image_url VARCHAR, "
        "card_image_url VARCHAR, "
        "patient_id INTEGER, "
        "FOREIGN KEY(patient_id) REFERENCES patient_animals (id) ON DELETE SET NULL)"
    ))

    bind.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS bar_zones ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "field_id INTEGER NOT NULL, "
        "zone_kind VARCHAR NOT NULL, "
        "col1 INTEGER NOT NULL, "
        "row1 INTEGER NOT NULL, "
        "col2 INTEGER NOT NULL, "
        "row2 INTEGER NOT NULL, "
        "image_url VARCHAR, "
        "cocktail_recipe_id INTEGER, "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(cocktail_recipe_id) REFERENCES cocktail_recipes (id) ON DELETE CASCADE, "
        "FOREIGN KEY(field_id) REFERENCES fields (id) ON DELETE CASCADE)"
    ))

    bind.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS cocktail_recipe_items ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "cocktail_recipe_id INTEGER NOT NULL, "
        "product_id INTEGER, "
        "plant_id INTEGER, "
        "ingredient_id INTEGER, "
        "remedy_id INTEGER, "
        "qty INTEGER NOT NULL DEFAULT 1, "
        "CONSTRAINT ck_cocktailrecipeitem_single_source CHECK ("
        "(product_id IS NOT NULL AND plant_id IS NULL AND ingredient_id IS NULL AND remedy_id IS NULL) OR "
        "(product_id IS NULL AND plant_id IS NOT NULL AND ingredient_id IS NULL AND remedy_id IS NULL) OR "
        "(product_id IS NULL AND plant_id IS NULL AND ingredient_id IS NOT NULL AND remedy_id IS NULL) OR "
        "(product_id IS NULL AND plant_id IS NULL AND ingredient_id IS NULL AND remedy_id IS NOT NULL)), "
        "FOREIGN KEY(cocktail_recipe_id) REFERENCES cocktail_recipes (id) ON DELETE CASCADE, "
        "FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE, "
        "FOREIGN KEY(plant_id) REFERENCES plants (id) ON DELETE CASCADE, "
        "FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, "
        "FOREIGN KEY(remedy_id) REFERENCES remedies (id) ON DELETE CASCADE)"
    ))

    bind.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS field_cocktail_recipes ("
        "field_id INTEGER NOT NULL, "
        "cocktail_recipe_id INTEGER NOT NULL, "
        "PRIMARY KEY (field_id, cocktail_recipe_id), "
        "FOREIGN KEY(cocktail_recipe_id) REFERENCES cocktail_recipes (id) ON DELETE CASCADE, "
        "FOREIGN KEY(field_id) REFERENCES fields (id) ON DELETE CASCADE)"
    ))

    bind.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS shakers ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "cocktail_recipe_id INTEGER, "
        "status VARCHAR NOT NULL DEFAULT 'empty', "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(cocktail_recipe_id) REFERENCES cocktail_recipes (id) ON DELETE CASCADE, "
        "FOREIGN KEY(user_id) REFERENCES users (vk_id) ON DELETE CASCADE)"
    ))


def downgrade() -> None:
    bind = op.get_bind()

    for table in ("shakers", "field_cocktail_recipes", "cocktail_recipe_items", "bar_zones", "cocktail_recipes"):
        bind.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))
