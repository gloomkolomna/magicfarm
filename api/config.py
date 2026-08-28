from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Абсолютный путь к каталогу api/ — основа для относительных путей (БД, загрузки).
API_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return default


def _env_list_int(name: str) -> set[int]:
    raw = os.getenv(name, "")
    if not raw:
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes")


# ── Общие ──
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 259200)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///farm.db")
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
DEV_LOGIN_ENABLED = APP_ENV == "dev"
ADMIN_ONLY = _env_bool("ADMIN_ONLY", APP_ENV != "dev")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5175")

# ── VK Mini App ──
VK_APP_ID = _env_int("VK_APP_ID", 0)
VK_APP_SECRET = os.getenv("VK_APP_SECRET", "")
VK_SERVICE_TOKEN = os.getenv("VK_SERVICE_TOKEN", "")
ADMIN_VK_IDS = _env_list_int("ADMIN_VK_IDS")

# ── Логи ──
LOG_RETENTION_DAYS = _env_int("LOG_RETENTION_DAYS", 30)


# ── Платёжный шлюз ProxyPay ──
PAY_GATEWAY_URL = os.getenv("PAY_GATEWAY_URL", "").strip().rstrip("/")
PAY_GATEWAY_GAME_ID = os.getenv("PAY_GATEWAY_GAME_ID", "farm")
PAY_GATEWAY_API_KEY = os.getenv("PAY_GATEWAY_API_KEY", "")
PAY_GATEWAY_WEBHOOK_SECRET = os.getenv("PAY_GATEWAY_WEBHOOK_SECRET", "")
PAY_GATEWAY_TIMEOUT_SECONDS = _env_int("PAY_GATEWAY_TIMEOUT_SECONDS", 15)
PAY_GATEWAY_ENABLED = bool(PAY_GATEWAY_URL and PAY_GATEWAY_API_KEY)


# ── Донат-бот группы «Крестики от Корги» (donut-backend) ──
DONUT_API_URL = os.getenv("DONUT_API_URL", "").strip().rstrip("/")
DONUT_API_KEY = os.getenv("DONUT_API_KEY", "")
DONUT_TIMEOUT_SECONDS = _env_int("DONUT_TIMEOUT_SECONDS", 5)
DONOR_SYNC_INTERVAL_MINUTES = _env_int("DONOR_SYNC_INTERVAL_MINUTES", 60)

# ── Фоновые задачи подписки (уведомления 5/3/1 день, авто-readonly) ──
SUBSCRIPTION_TASKS_ENABLED = _env_bool("SUBSCRIPTION_TASKS_ENABLED", True)


# ── Загрузки (фото вышивки) ──
UPLOADS_DIR = os.getenv("UPLOADS_DIR", os.path.join(API_DIR, "uploads"))
os.makedirs(UPLOADS_DIR, exist_ok=True)
UPLOAD_MAX_BYTES = _env_int("UPLOAD_MAX_BYTES", 8 * 1024 * 1024)
UPLOAD_VIDEO_MAX_BYTES = _env_int("UPLOAD_VIDEO_MAX_BYTES", 500 * 1024 * 1024)

# ── S3 / Yandex Object Storage ──
S3_ENABLED = os.getenv("S3_ENABLED", "").strip().lower() in ("1", "true", "yes")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://storage.yandexcloud.net")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", "")
STITCH_PHOTO_TTL_DAYS = _env_int("STITCH_PHOTO_TTL_DAYS", 30)


def get_admin_vk_ids() -> set[int]:
    return ADMIN_VK_IDS
