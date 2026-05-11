"""Планировщик задач — сброс лимитов в 00:00 МСК"""

import asyncio
import datetime
import pytz
from database import db
from config import RESET_TIMEZONE, RESET_HOUR, RESET_MINUTE


async def daily_reset_scheduler():
    """Фоновая задача: сброс лимитов каждый день в 00:00 МСК"""
    tz = pytz.timezone(RESET_TIMEZONE)

    while True:
        now = datetime.datetime.now(tz)

        # Время следующего сброса
        next_reset = now.replace(hour=RESET_HOUR, minute=RESET_MINUTE, second=0, microsecond=0)
        if next_reset <= now:
            next_reset += datetime.timedelta(days=1)

        wait_seconds = (next_reset - now).total_seconds()
        print(f"[Scheduler] Следующий сброс через {wait_seconds/3600:.1f} часов")

        await asyncio.sleep(wait_seconds)

        # Сбрасываем лимиты всех пользователей
        users = await db.get_all_users()
        today = now.strftime("%Y-%m-%d")

        for user in users:
            await db.reset_recovery_count(user["telegram_id"])
            await db.set_last_reset_date(user["telegram_id"], today)

        print(f"[Scheduler] Лимиты сброшены для {len(users)} пользователей")
        await asyncio.sleep(60)  # Чтобы не сработало дважды
