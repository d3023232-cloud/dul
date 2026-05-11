"""Хендлеры профиля"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu
from keyboards import profile_kb, main_menu_kb
from helpers import calculate_winrate

router = Router()


@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await message.answer("❌ Сначала нажмите /start")
        return

    winrate = calculate_winrate(user["wins"], user["losses"])
    status = "👑 VIP" if user["is_vip"] else "🤠 Обычный"
    limit = await db.get_recovery_limit(user_id)

    text = f"""
🆔 <b>ID:</b> <code>{user['telegram_id']}</code>

👤 <b>Имя:</b> {user.get('first_name') or 'Неизвестно'}
📛 <b>Юзернейм:</b> @{user.get('username') or 'Нет'}

💰 <b>Монеты:</b> {user['balance_coins']}
💎 <b>Донат-коины:</b> {user['balance_donate']}

⚔️ <b>Статистика дуэлей:</b>
   🏆 Побед: {user['wins']}
   💀 Поражений: {user['losses']}
   📊 Всего игр: {user['duels_played']}
   📈 Винрейт: {winrate}%

🔄 <b>Восстановления сегодня:</b> {user['recoveries_today']}/{limit}
⭐ <b>Статус:</b> {status}

📅 <b>Дата регистрации:</b> {user['created_at'][:10]}
"""

    await message.answer(text, reply_markup=profile_kb(), parse_mode="HTML")


@router.callback_query(F.data == "refresh_profile")
async def refresh_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Ошибка!", show_alert=True)
        return

    winrate = calculate_winrate(user["wins"], user["losses"])
    status = "👑 VIP" if user["is_vip"] else "🤠 Обычный"
    limit = await db.get_recovery_limit(user_id)

    text = f"""
🆔 <b>ID:</b> <code>{user['telegram_id']}</code>

👤 <b>Имя:</b> {user.get('first_name') or 'Неизвестно'}
📛 <b>Юзернейм:</b> @{user.get('username') or 'Нет'}

💰 <b>Монеты:</b> {user['balance_coins']}
💎 <b>Донат-коины:</b> {user['balance_donate']}

⚔️ <b>Статистика дуэлей:</b>
   🏆 Побед: {user['wins']}
   💀 Поражений: {user['losses']}
   📊 Всего игр: {user['duels_played']}
   📈 Винрейт: {winrate}%

🔄 <b>Восстановления сегодня:</b> {user['recoveries_today']}/{limit}
⭐ <b>Статус:</b> {status}

📅 <b>Дата регистрации:</b> {user['created_at'][:10]}
"""

    await callback.message.edit_text(text, reply_markup=profile_kb(), parse_mode="HTML")
    await callback.answer("🔄 Обновлено!")
