"""Вспомогательные функции"""

import random
import string
import datetime
import pytz
from config import RESET_TIMEZONE, RESET_HOUR, RESET_MINUTE


def generate_referral_code(telegram_id: int) -> str:
    """Генерация реферального кода"""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"REF{telegram_id}{suffix}"


def get_msk_now() -> datetime.datetime:
    """Текущее время по МСК"""
    tz = pytz.timezone(RESET_TIMEZONE)
    return datetime.datetime.now(tz)


def get_today_msk() -> str:
    """Сегодняшняя дата по МСК в формате YYYY-MM-DD"""
    return get_msk_now().strftime("%Y-%m-%d")


def should_reset_daily(last_reset_date: str | None) -> bool:
    """Проверка, нужно ли сбросить дневной лимит"""
    today = get_today_msk()
    return last_reset_date != today


def format_user_name(user_data: dict) -> str:
    """Форматирование имени пользователя"""
    name = user_data.get("first_name") or user_data.get("username")
    if not name:
        name = f"User {user_data.get('telegram_id', '?')}"
    return name


def calculate_winrate(wins: int, losses: int) -> float:
    """Расчёт винрейта"""
    total = wins + losses
    if total == 0:
        return 0.0
    return round((wins / total) * 100, 1)


# === АНИМАЦИИ ===

DUEL_FRAMES = [
    """
🌵        🤠
  🔫  ————►
        💥
    """,
    """
🌵        🤠
    🔫————►
        💥
    """,
    """
🌵        🤠
      🔫——►
        💥
    """,
    """
🌵        🤠
        🔫►
        💥
    """,
    """
🌵        🤠
        💥🔫

    """,
    """
🌵        💀
        💥 

    """,
]


def get_duel_frames() -> list:
    return DUEL_FRAMES
