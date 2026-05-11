"""Хендлеры реферальной системы"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu
from keyboards import referral_kb, main_menu_kb

router = Router()


@router.message(F.text == "🔗 Рефералка")
async def show_referral(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await message.answer("❌ Сначала нажмите /start")
        return

    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user['referral_code']}"
    stats = await db.get_referral_stats(user_id)

    text = f"""
🔗 <b>Реферальная программа</b>

📢 <b>Ваша ссылка:</b>
<code>{ref_link}</code>

📊 <b>Статистика:</b>
   👥 Всего рефералов: {stats['total']}
   🎁 Получили бонус: {stats['rewarded']}

🎁 <b>Награды за реферала:</b>
   • Вы получаете: <b>2 монеты + 1 DC</b>
   • Реферал получает: <b>5 монет</b>
   • Когда реферал сыграет 18 дуэлей: <b>3 DC</b>

📤 Поделитесь ссылкой с друзьями!
"""

    await message.answer(text, reply_markup=referral_kb(ref_link), parse_mode="HTML")


@router.message(F.text == "📊 Топ игроков")
async def show_top(message: Message):
    users = await db.get_all_users()

    # Сортируем по победам
    sorted_users = sorted(users, key=lambda x: x["wins"], reverse=True)[:10]

    text = "🏆 <b>Топ 10 игроков</b>

"

    for i, user in enumerate(sorted_users, 1):
        name = user.get("first_name") or user.get("username") or f"User {user['telegram_id']}"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {name} — 🏆{user['wins']} / 💀{user['losses']}
"

    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")
