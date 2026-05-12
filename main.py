"""
🤠 ДУЭЛЬ БОТ 🤠
Telegram-бот для дуэлей между пользователями

Запуск: python main.py
"""

import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from scheduler import daily_reset_scheduler
from start import router as start_router
from duel import router as duel_router
from profile import router as profile_router
from shop import router as shop_router
from referral import router as referral_router
from admin import router as admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ====== MIDDLEWARE: ПРОВЕРКА БАНА ======
class BanCheckMiddleware(BaseMiddleware):
    """Блокирует сообщения от забаненных пользователей"""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Update):
            user_id = None
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

            if user_id:
                user = await db.get_user(user_id)
                if user and user.get("is_banned"):
                    try:
                        if event.message:
                            await event.message.answer(
                                "🚫 <b>Ваш аккаунт заблокирован.</b>\n\nОбратитесь к администратору.",
                                parse_mode="HTML"
                            )
                        elif event.callback_query:
                            await event.callback_query.answer("🚫 Вы заблокированы!", show_alert=True)
                    except:
                        pass
                    return None

        return await handler(event, data)


# ====== ВЕБ-СЕРВЕР (для хостинга) ======
async def health_handler(request):
    """Health-check для хостинга"""
    return web.Response(text="🤠 Duel Bot is running!", status=200)


async def run_web_server():
    """Запускает HTTP-сервер для health-check"""
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    # BotHost и другие хостинги задают PORT
    port = int(os.getenv("PORT", "8080"))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"🌐 Веб-сервер запущен на порту {port}")

    # Держим сервер живым
    while True:
        await asyncio.sleep(3600)


# ====== ЗАПУСК БОТА ======
async def run_bot():
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(BanCheckMiddleware())

    await db.init()
    logger.info("База данных инициализирована")

    dp.include_router(start_router)
    dp.include_router(duel_router)
    dp.include_router(profile_router)
    dp.include_router(shop_router)
    dp.include_router(referral_router)
    dp.include_router(admin_router)

    asyncio.create_task(daily_reset_scheduler())
    logger.info("Планировщик запущен")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")

    await dp.start_polling(bot)


async def main():
    """Запускает бота и веб-сервер параллельно"""
    await asyncio.gather(
        run_bot(),
        run_web_server()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
