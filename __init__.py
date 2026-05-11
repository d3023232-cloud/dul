"""Хендлеры старта и проверки подписки"""

import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu
from keyboards import main_menu_kb, subscribe_kb, back_to_menu_kb
from utils.helpers import generate_referral_code, should_reset_daily, get_today_msk
from config import CHANNEL_ID, CHANNEL_LINK

router = Router()


async def get_welcome_text() -> str:
    """Генерирует приветствие с актуальными значениями из БД"""
    start_coins = await db.get_economy_setting_int("start_coins", 10)
    recovery = await db.get_economy_setting_int("recovery_interval_minutes", 6)
    duel_cost = await db.get_economy_setting_int("duel_cost", 1)
    limit_default = await db.get_economy_setting_int("daily_recovery_limit_default", 5)
    limit_vip = await db.get_economy_setting_int("daily_recovery_limit_vip", 15)

    return f"""
🤠 <b>Добро пожаловать в Дуэль Бот!</b> 🤠

Здесь ты можешь бросить вызов другим ковбоям на перестрелку!

📜 <b>Правила:</b>
• У каждого игрока <b>{start_coins} монет</b>
• Дуэль стоит <b>{duel_cost} монету</b>
• При балансе <b>0</b> — восстановление <b>1 монеты</b> каждые <b>{recovery} минут</b>
• Обычный игрок: <b>{limit_default} восстановлений</b> в сутки
• VIP игрок: <b>{limit_vip} восстановлений</b> в сутки
• Сброс лимита каждый день в <b>00:00 по МСК</b>

💰 <b>Донат:</b>
• VIP Premium — увеличивает лимит восстановлений
• Сброс лимита — сбрасывает счётчик восстановлений
• Покупка монет — 5 DC = 1 монета

⚔️ <b>Готов к дуэли?</b> Выбирай соперника и стреляй первым!
"""


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Игрок"

    # Проверяем, есть ли пользователь в БД
    user = await db.get_user(user_id)

    if not user:
        # Новый пользователь — проверяем рефералку
        args = message.text.split() if message.text else []
        referred_by = None

        if len(args) > 1:
            ref_code = args[1]
            ref_user = await db.get_user_by_referral(ref_code)
            if ref_user and ref_user["telegram_id"] != user_id:
                referred_by = ref_user["telegram_id"]
                # Награждаем пригласившего
                await db.add_coins(referred_by, 2, f"Реферал {user_id}")
                await db.add_donate(referred_by, 1, f"Реферал {user_id}")
                await db.create_referral_reward(referred_by, user_id)

        ref_code = generate_referral_code(user_id)
        start_coins = await db.get_economy_setting_int('start_coins', 10)
        await db.create_user(user_id, username, first_name, ref_code, referred_by, start_coins)

        if referred_by:
            await db.add_coins(user_id, 5, "Бонус за реферальную регистрацию")
    else:
        await db.update_username(user_id, username, first_name)

    # Проверяем подписку
    is_subscribed = await check_subscription(bot, user_id)
    await db.set_subscribed(user_id, is_subscribed)

    if not is_subscribed:
        await message.answer(
            f"👋 <b>Привет, {first_name}!</b>

"
            f"Для использования бота необходимо подписаться на наш канал:",
            reply_markup=subscribe_kb(CHANNEL_LINK),
            parse_mode="HTML"
        )
        return

    # Проверяем сброс дневного лимита
    user = await db.get_user(user_id)
    if user and should_reset_daily(user.get("last_reset_date")):
        await db.reset_recovery_count(user_id)
        await db.set_last_reset_date(user_id, get_today_msk())

    await state.set_state(MainMenu.main)
    await message.answer(
        await get_welcome_text(),
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(bot, user_id)

    if is_subscribed:
        await db.set_subscribed(user_id, True)
        await db.update_username(user_id, callback.from_user.username or "", callback.from_user.first_name or "")

        # Проверяем сброс дневного лимита
        user = await db.get_user(user_id)
        if user and should_reset_daily(user.get("last_reset_date")):
            await db.reset_recovery_count(user_id)
            await db.set_last_reset_date(user_id, get_today_msk())

        await state.set_state(MainMenu.main)
        await callback.message.edit_text(
            await get_welcome_text(),
            parse_mode="HTML"
        )
        await callback.message.answer(
            "✅ Доступ открыт! Выбирай действие:",
            reply_markup=main_menu_kb()
        )
    else:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)


@router.message(F.text == "🔙 В меню")
@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(event, state: FSMContext):
    await state.set_state(MainMenu.main)
    text = "🏠 <b>Главное меню</b>

Выбирай действие, ковбой!"

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML")
        await event.message.answer("👇", reply_markup=main_menu_kb())
    else:
        await event.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")
