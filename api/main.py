from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import config
from db import init_db
from middleware import log_failed_requests
from routes.auth import router as auth_router
from routes.me import router as me_router
from routes.settings import router as settings_router
from routes.stitches import router as stitches_router
from routes.plants import router as plants_router
from routes.farm import router as farm_router
from routes.orders import router as orders_router, admin_router as admin_orders_router, customer_router as admin_customers_router
from routes.admin_fields import router as admin_fields_router
from routes.admin_catalog import router as admin_catalog_router, public_router as crystal_cards_public_router
from routes.admin_players import router as admin_players_router
from routes.admin_access import router as admin_access_router
from routes.fields import router as fields_router
from routes.house import router as house_router
from routes.crystal_norms import router as crystal_norms_router
from routes.library import router as library_router
from routes.levels import router as levels_router, admin_router as admin_levels_router
from routes.barnyard import router as barnyard_router
from routes.pets import router as pets_router
from routes.potions import router as potions_router, admin_router as admin_potions_router
from routes.cocktails import router as cocktails_router, admin_router as admin_cocktails_router
from routes.achievements import router as achievements_router, admin_router as admin_achievements_router
from routes.game_media import router as game_media_admin_router, public_router as game_media_public_router
from routes.logs import router as logs_router
from routes.ingredients import router as ingredients_router, admin_router as admin_ingredients_router
from routes.meadow import router as meadow_router
from routes.shop import router as shop_router
from routes.admin_infirmary import router as admin_infirmary_router
from routes.infirmary import router as infirmary_router
from routes.remedy_lab import router as remedy_lab_router
from routes.story import router as story_router, admin_router as admin_story_router
from routes.lessons import router as lessons_router, admin_router as admin_lessons_router
from routes.public_players import router as public_players_router
from routes.trades import router as trades_router
from routes.chat import router as chat_router
from routes.gifts import router as gifts_router
from routes.notifications import router as notifications_router
from routes.payment import router as payment_router, admin_router as admin_payment_router, public_router as payment_public_router

init_db()


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title="Farm API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL, "http://localhost:5175", "https://vk.com", "https://m.vk.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BaseHTTPMiddleware, dispatch=log_failed_requests)

# Раздача загруженных файлов (фото вышивки) из UPLOADS_DIR.
app.mount("/api/uploads", StaticFiles(directory=config.UPLOADS_DIR), name="uploads")

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(settings_router)
app.include_router(stitches_router)
app.include_router(plants_router)
app.include_router(farm_router)
app.include_router(orders_router)
app.include_router(admin_orders_router)
app.include_router(admin_customers_router)
app.include_router(admin_fields_router)
app.include_router(admin_catalog_router)
app.include_router(admin_players_router)
app.include_router(admin_access_router)
app.include_router(fields_router)
app.include_router(house_router)
app.include_router(crystal_norms_router)
app.include_router(library_router)
app.include_router(levels_router)
app.include_router(admin_levels_router)
app.include_router(barnyard_router)
app.include_router(pets_router)
app.include_router(potions_router)
app.include_router(admin_potions_router)
app.include_router(cocktails_router)
app.include_router(admin_cocktails_router)
app.include_router(achievements_router)
app.include_router(admin_achievements_router)
app.include_router(game_media_admin_router)
app.include_router(game_media_public_router)
app.include_router(crystal_cards_public_router)
app.include_router(logs_router)
app.include_router(ingredients_router)
app.include_router(admin_ingredients_router)
app.include_router(meadow_router)
app.include_router(shop_router)
app.include_router(admin_infirmary_router)
app.include_router(infirmary_router)
app.include_router(remedy_lab_router)
app.include_router(story_router)
app.include_router(admin_story_router)
app.include_router(lessons_router)
app.include_router(admin_lessons_router)
app.include_router(public_players_router)
app.include_router(trades_router)
app.include_router(chat_router)
app.include_router(gifts_router)
app.include_router(notifications_router)
app.include_router(payment_router)
app.include_router(admin_payment_router)
app.include_router(payment_public_router)


@app.get("/api/")
def health():
    return {"status": "ok", "service": "farm-api"}
