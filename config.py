"""Конфигурация бота Дуэль — читается из переменных окружения"""

import os

# === ОСНОВНЫЕ НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан! Установите переменную окружения BOT_TOKEN.")

# === АДМИНИСТРАТОРЫ ===
# ID через запятую в env: ADMIN_IDS=123456789,987654321
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()]

# === КАНАЛ ===
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
# Автодополнение @ для CHANNEL_ID
if CHANNEL_ID and not CHANNEL_ID.startswith("@") and not CHANNEL_ID.startswith("-"):
    CHANNEL_ID = f"@{CHANNEL_ID}"
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/your_channel")

# === БАЗА ДАННЫХ ===
# SQLite (по умолчанию). Для PostgreSQL задайте DATABASE_URL
DB_PATH = os.getenv("DB_PATH", "/app/data/duel_bot.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Автодополнение URL если пользователь ввёл только юзернейм
if CHANNEL_LINK and not CHANNEL_LINK.startswith("http"):
    CHANNEL_LINK = f"https://t.me/{CHANNEL_LINK.lstrip('@')}"

# === СТАТИЧЕСКИЕ НАСТРОЙКИ ===
START_COINS = 10
DUEL_COST = 1
RECOVERY_AMOUNT = 1

VIP_PRICE = 299
RESET_LIMIT_PRICE = 50
COIN_PRICE_DC = 5
COIN_PACKAGES = [1, 5, 10, 15]

REFERRAL_REWARD_DC = 3
REFERRAL_DUELS_REQUIRED = 18
REFERRAL_BONUS_COINS_NEW = 5
REFERRAL_BONUS_COINS_INVITER = 2
REFERRAL_BONUS_DC_INVITER = 1

# === АНИМАЦИИ ===
TYPING_DOTS_INTERVAL = 0.5
DUEL_ANIMATION_INTERVAL = 1.2

# === АДМИН-ПАНЕЛЬ ===
ADMIN_USERS_PER_PAGE = 10

# === СБРОС ЛИМИТА ===
RESET_TIMEZONE = "Europe/Moscow"
RESET_HOUR = 0
RESET_MINUTE = 0
