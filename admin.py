"""Админ-панель — полный контроль над игроками"""

import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu, AdminState
from keyboards import admin_main_kb, admin_user_list_kb, admin_user_actions_kb, admin_confirm_kb, main_menu_kb, back_to_menu_kb, economy_settings_kb, economy_edit_kb
from config import ADMIN_IDS
from helpers import format_user_name, calculate_winrate

router = Router()

# ====== ПРОВЕРКА АДМИНА ======

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ====== ГЛАВНОЕ МЕНЮ АДМИНА ======

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminState.main)
    await message.answer(
        "🛡️ <b>АДМИН-ПАНЕЛЬ</b>

"
        "Выберите раздел:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.main)
    await callback.message.edit_text(
        "🛡️ <b>АДМИН-ПАНЕЛЬ</b>

Выберите раздел:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== СПИСОК ИГРОКОВ ======

@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AdminState.main)
    users, total = await db.get_users_paginated(page=0)

    await state.update_data(admin_users=users, admin_total=total, admin_page=0)

    await callback.message.edit_text(
        f"👥 <b>Список игроков</b> (всего: {total})

"
        f"Нажмите на игрока для управления:",
        reply_markup=admin_user_list_kb(users),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_page:"))
async def admin_pagination(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    page = int(callback.data.split(":")[1])
    users, total = await db.get_users_paginated(page=page)

    await state.update_data(admin_users=users, admin_total=total, admin_page=page)

    await callback.message.edit_text(
        f"👥 <b>Список игроков</b> (всего: {total})

"
        f"Нажмите на игрока для управления:",
        reply_markup=admin_user_list_kb(users, page=page),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== ПРОСМОТР ИГРОКА ======

@router.callback_query(F.data.startswith("admin_view_user:"))
async def admin_view_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return

    await state.update_data(admin_target_id=user_id)

    winrate = calculate_winrate(user["wins"], user["losses"])
    status = "👑 VIP" if user["is_vip"] else "🤠 Обычный"
    ban_status = "🚫 ЗАБАНЕН" if user.get("is_banned") else "✅ Активен"
    limit = await db.get_recovery_limit(user_id)

    text = f"""
🆔 <b>ID:</b> <code>{user['telegram_id']}</code>
👤 <b>Имя:</b> {user.get('first_name') or '—'}
📛 <b>Юзернейм:</b> @{user.get('username') or 'Нет'}

💰 <b>Монеты:</b> {user['balance_coins']}
💎 <b>Донат-коины:</b> {user['balance_donate']}

⚔️ <b>Статистика:</b>
   🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}
   📊 Всего: {user['duels_played']} | 📈 Винрейт: {winrate}%

🔄 <b>Восстановления:</b> {user['recoveries_today']}/{limit}
⭐ <b>Статус:</b> {status}
🔒 <b>Состояние:</b> {ban_status}

📅 <b>Регистрация:</b> {user['created_at'][:10]}
"""

    await callback.message.edit_text(
        text,
        reply_markup=admin_user_actions_kb(user_id, is_banned=user.get("is_banned", False), is_vip=user["is_vip"]),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== ВЫДАЧА / ЗАБОР МОНЕТ ======

@router.callback_query(F.data.startswith("admin_give_coins:"))
async def admin_give_coins_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await state.update_data(admin_action="give_coins", admin_target_id=user_id)
    await state.set_state(AdminState.entering_amount)

    await callback.message.edit_text(
        f"➕ <b>Выдача монет</b>

"
        f"Игрок: <code>{user_id}</code>
"
        f"Введите количество монет для выдачи:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_take_coins:"))
async def admin_take_coins_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await state.update_data(admin_action="take_coins", admin_target_id=user_id)
    await state.set_state(AdminState.entering_amount)

    await callback.message.edit_text(
        f"➖ <b>Забор монет</b>

"
        f"Игрок: <code>{user_id}</code>
"
        f"Введите количество монет для забора:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== ВЫДАЧА / ЗАБОР DC ======

@router.callback_query(F.data.startswith("admin_give_dc:"))
async def admin_give_dc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await state.update_data(admin_action="give_dc", admin_target_id=user_id)
    await state.set_state(AdminState.entering_amount)

    await callback.message.edit_text(
        f"➕ <b>Выдача донат-коинов</b>

"
        f"Игрок: <code>{user_id}</code>
"
        f"Введите количество DC для выдачи:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_take_dc:"))
async def admin_take_dc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await state.update_data(admin_action="take_dc", admin_target_id=user_id)
    await state.set_state(AdminState.entering_amount)

    await callback.message.edit_text(
        f"➖ <b>Забор донат-коинов</b>

"
        f"Игрок: <code>{user_id}</code>
"
        f"Введите количество DC для забора:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== ОБРАБОТКА ВВОДА СУММЫ ======

@router.message(AdminState.entering_amount)
async def admin_process_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число!")
        return

    data = await state.get_data()
    action = data.get("admin_action")
    target_id = data.get("admin_target_id")

    if not action or not target_id:
        await message.answer("❌ Ошибка состояния. Начните заново.")
        await state.set_state(AdminState.main)
        return

    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return

    # Формируем текст подтверждения
    action_texts = {
        "give_coins": ("выдачи монет", "монет", "give_coins"),
        "take_coins": ("забора монет", "монет", "take_coins"),
        "give_dc": ("выдачи DC", "DC", "give_dc"),
        "take_dc": ("забора DC", "DC", "take_dc"),
    }

    text, currency, confirm_action = action_texts[action]

    await state.set_state(AdminState.main)
    await message.answer(
        f"⚠️ <b>Подтвердите {text}</b>

"
        f"Игрок: <code>{target_id}</code> ({format_user_name(user)})
"
        f"Количество: <b>{amount} {currency}</b>

"
        f"Текущий баланс: {user['balance_coins'] if 'coins' in action else user['balance_donate']} {currency}",
        reply_markup=admin_confirm_kb(confirm_action, target_id, amount),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_action(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    action = parts[1]
    target_id = int(parts[2])
    amount = int(parts[3])
    admin_id = callback.from_user.id

    user = await db.get_user(target_id)
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return

    # Выполняем действие
    if action == "give_coins":
        await db.add_coins(target_id, amount, f"Выдано админом {admin_id}")
        await db.admin_log(admin_id, "give_coins", target_id, f"+{amount}")
        text = f"✅ Выдано <b>{amount} монет</b> игроку <code>{target_id}</code>"

    elif action == "take_coins":
        # Не уходим в минус
        take_amount = min(amount, user["balance_coins"])
        if take_amount > 0:
            await db.remove_coins(target_id, take_amount, f"Забрано админом {admin_id}")
            await db.admin_log(admin_id, "take_coins", target_id, f"-{take_amount}")
        text = f"✅ Забрано <b>{take_amount} монет</b> у игрока <code>{target_id}</code>"

    elif action == "give_dc":
        await db.add_donate(target_id, amount, f"Выдано админом {admin_id}")
        await db.admin_log(admin_id, "give_dc", target_id, f"+{amount}")
        text = f"✅ Выдано <b>{amount} DC</b> игроку <code>{target_id}</code>"

    elif action == "take_dc":
        take_amount = min(amount, user["balance_donate"])
        if take_amount > 0:
            await db.remove_donate(target_id, take_amount, f"Забрано админом {admin_id}")
            await db.admin_log(admin_id, "take_dc", target_id, f"-{take_amount}")
        text = f"✅ Забрано <b>{take_amount} DC</b> у игрока <code>{target_id}</code>"

    else:
        await callback.answer("❌ Неизвестное действие!", show_alert=True)
        return

    await callback.message.edit_text(
        text + "

" + f"Новый баланс игрока:
💰 {user['balance_coins']} монет | 💎 {user['balance_donate']} DC",
        reply_markup=admin_user_actions_kb(target_id, is_banned=user.get("is_banned", False), is_vip=user["is_vip"]),
        parse_mode="HTML"
    )
    await callback.answer("✅ Выполнено!")


# ====== VIP / БАН ======

@router.callback_query(F.data.startswith("admin_give_vip:"))
async def admin_give_vip(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await db.set_vip(user_id, True)
    await db.admin_log(callback.from_user.id, "give_vip", user_id, "VIP выдан")

    user = await db.get_user(user_id)
    await callback.message.edit_text(
        f"👑 <b>VIP выдан!</b>

Игрок: <code>{user_id}</code>",
        reply_markup=admin_user_actions_kb(user_id, is_banned=user.get("is_banned", False), is_vip=True),
        parse_mode="HTML"
    )
    await callback.answer("✅ VIP выдан!")


@router.callback_query(F.data.startswith("admin_remove_vip:"))
async def admin_remove_vip(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await db.set_vip(user_id, False)
    await db.admin_log(callback.from_user.id, "remove_vip", user_id, "VIP снят")

    user = await db.get_user(user_id)
    await callback.message.edit_text(
        f"❌ <b>VIP снят!</b>

Игрок: <code>{user_id}</code>",
        reply_markup=admin_user_actions_kb(user_id, is_banned=user.get("is_banned", False), is_vip=False),
        parse_mode="HTML"
    )
    await callback.answer("✅ VIP снят!")


@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await db.ban_user(user_id, f"Админ {callback.from_user.id}")
    await db.admin_log(callback.from_user.id, "ban", user_id, "Забанен")

    user = await db.get_user(user_id)
    await callback.message.edit_text(
        f"🚫 <b>Игрок забанен!</b>

ID: <code>{user_id}</code>

"
        f"Игрок больше не сможет использовать бота.",
        reply_markup=admin_user_actions_kb(user_id, is_banned=True, is_vip=user["is_vip"]),
        parse_mode="HTML"
    )
    await callback.answer("✅ Забанен!")


@router.callback_query(F.data.startswith("admin_unban:"))
async def admin_unban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    await db.unban_user(user_id)
    await db.admin_log(callback.from_user.id, "unban", user_id, "Разбанен")

    user = await db.get_user(user_id)
    await callback.message.edit_text(
        f"✅ <b>Игрок разбанен!</b>

ID: <code>{user_id}</code>",
        reply_markup=admin_user_actions_kb(user_id, is_banned=False, is_vip=user["is_vip"]),
        parse_mode="HTML"
    )
    await callback.answer("✅ Разбанен!")


# ====== ТРАНЗАКЦИИ ИГРОКА ======

@router.callback_query(F.data.startswith("admin_transactions:"))
async def admin_view_transactions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    transactions = await db.get_user_transactions(user_id, limit=20)
    user = await db.get_user(user_id)

    if not transactions:
        text = "📜 <b>Транзакции не найдены</b>"
    else:
        text = f"📜 <b>Транзакции игрока</b> <code>{user_id}</code>

"
        for tx in transactions:
            emoji = "➕" if tx["type"] == "add" else ("➖" if tx["type"] == "remove" else "🔄")
            text += (
                f"{emoji} <b>{tx['amount']}</b> {tx['currency']} | {tx['type']}
"
                f"   📝 {tx['description'] or '—'}
"
                f"   🕐 {tx['created_at'][:16]}

"
            )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад к игроку", callback_data=f"admin_view_user:{user_id}")]
            ]
        ),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== ПОИСК ИГРОКА ======

@router.callback_query(F.data == "admin_search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AdminState.searching_user)
    await callback.message.edit_text(
        "🔍 <b>Поиск игрока</b>

"
        "Введите ID, юзернейм или имя игрока:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminState.searching_user)
async def admin_search_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    query = message.text.strip()
    results = await db.search_users(query)

    if not results:
        await message.answer(
            "❌ Игроки не найдены. Попробуйте другой запрос.",
            reply_markup=back_to_menu_kb()
        )
        return

    if len(results) == 1:
        # Сразу показываем профиль
        user = results[0]
        await state.update_data(admin_target_id=user["telegram_id"])
        await state.set_state(AdminState.main)

        winrate = calculate_winrate(user["wins"], user["losses"])
        status = "👑 VIP" if user["is_vip"] else "🤠 Обычный"
        ban_status = "🚫 ЗАБАНЕН" if user.get("is_banned") else "✅ Активен"

        await message.answer(
            f"🆔 <b>ID:</b> <code>{user['telegram_id']}</code>
"
            f"👤 <b>Имя:</b> {user.get('first_name') or '—'}
"
            f"📛 <b>Юзернейм:</b> @{user.get('username') or 'Нет'}
"
            f"💰 <b>Монеты:</b> {user['balance_coins']} | 💎 <b>DC:</b> {user['balance_donate']}
"
            f"🏆 <b>Побед:</b> {user['wins']} | 💀 <b>Поражений:</b> {user['losses']} | 📈 <b>Винрейт:</b> {winrate}%
"
            f"⭐ <b>Статус:</b> {status} | 🔒 <b>Состояние:</b> {ban_status}",
            reply_markup=admin_user_actions_kb(user["telegram_id"], is_banned=user.get("is_banned", False), is_vip=user["is_vip"]),
            parse_mode="HTML"
        )
    else:
        # Показываем список найденных
        await state.update_data(admin_users=results, admin_total=len(results), admin_page=0)
        await state.set_state(AdminState.main)
        await message.answer(
            f"🔍 <b>Найдено игроков: {len(results)}</b>

Выберите:",
            reply_markup=admin_user_list_kb(results),
            parse_mode="HTML"
        )


# ====== СТАТИСТИКА БОТА ======

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    stats = await db.get_bot_stats()

    text = f"""
📊 <b>СТАТИСТИКА БОТА</b>

👥 <b>Пользователи:</b>
   Всего: <b>{stats['total_users']}</b>
   VIP: <b>{stats['vip_users']}</b>
   Забанено: <b>{stats['banned_users']}</b>

⚔️ <b>Дуэли:</b>
   Всего создано: <b>{stats['total_duels']}</b>
   Завершено: <b>{stats['completed_duels']}</b>

💰 <b>Экономика:</b>
   Монет в обороте: <b>{stats['total_coins']}</b>
   DC в обороте: <b>{stats['total_donate']}</b>

🏆 <b>Топ победителей:</b>
"""
    for i, u in enumerate(stats["top_winners"], 1):
        name = u.get("first_name") or u.get("username") or f"ID:{u['telegram_id']}"
        text += f"   {i}. {name} — {u['wins']} побед
"

    await callback.message.edit_text(
        text,
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== АКТИВНЫЕ ДУЭЛИ ======

@router.callback_query(F.data == "admin_duels")
async def admin_duels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    duels = await db.get_all_duels(limit=20)

    if not duels:
        text = "⚔️ <b>Дуэлей пока нет</b>"
    else:
        text = "⚔️ <b>Последние дуэли:</b>

"
        status_emojis = {
            "pending": "⏳", "active": "🔥", "completed": "✅",
            "expired": "⏰", "declined": "❌"
        }
        for d in duels:
            emoji = status_emojis.get(d["status"], "❓")
            text += (
                f"{emoji} ID: <code>{d['id']}</code> | Статус: <b>{d['status']}</b>
"
                f"   Вызывающий: <code>{d['challenger_id']}</code>
"
                f"   Оппонент: <code>{d['opponent_id']}</code>
"
                f"   Ставка: {d['bet']} монет
"
                f"   🕐 {d['created_at'][:16]}

"
            )

    await callback.message.edit_text(
        text,
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ====== РАССЫЛКА ======

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AdminState.broadcasting)
    await callback.message.edit_text(
        "📢 <b>Рассылка всем пользователям</b>

"
        "Отправьте сообщение для рассылки (поддерживается HTML):

"
        "⚠️ Будьте осторожны — сообщение уйдёт ВСЕМ игрокам!",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminState.broadcasting)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    users = await db.get_all_users()
    total = len(users)
    sent = 0
    failed = 0

    status_msg = await message.answer(f"📤 Рассылка начата... 0/{total}")

    for user in users:
        try:
            await bot.send_message(user["telegram_id"], message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        if (sent + failed) % 10 == 0:
            try:
                await status_msg.edit_text(f"📤 Рассылка... {sent + failed}/{total} (✅{sent} ❌{failed})")
            except:
                pass
        await asyncio.sleep(0.05)  # Антифлуд

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>

"
        f"📤 Отправлено: <b>{sent}</b>
"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML"
    )

    await db.admin_log(message.from_user.id, "broadcast", 0, f"Отправлено {sent}, ошибок {failed}")
    await state.set_state(AdminState.main)


# ====== НАСТРОЙКИ ЭКОНОМИКИ ======

@router.callback_query(F.data == "admin_economy")
async def admin_economy_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AdminState.editing_economy)
    settings = await db.get_all_economy_settings()

    text = "⚙️ <b>НАСТРОЙКИ ЭКОНОМИКИ</b>

"
    text += "Нажмите на параметр для изменения:

"

    for s in settings:
        text += f"• <b>{s['key']}</b> = <code>{s['value']}</code>
"
        if s.get('description'):
            text += f"   <i>{s['description']}</i>
"

    await callback.message.edit_text(
        text,
        reply_markup=economy_settings_kb(settings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("economy_edit:"))
async def economy_edit_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    key = callback.data.split(":")[1]
    value = await db.get_economy_setting(key, "не задано")

    descriptions = {
        "max_coins": "Максимальный баланс монет у игрока. При достижении — начисления блокируются.",
        "recovery_interval_minutes": "Сколько минут ждать между восстановлениями 1 монеты при балансе 0.",
        "win_multiplier": "Во сколько раз умножается ставка при победе. Стандарт: 2 (забираешь 2 монеты).",
        "daily_recovery_limit_default": "Сколько раз обычный игрок может восстановить монеты за день.",
        "daily_recovery_limit_vip": "Сколько раз VIP может восстановить монеты за день.",
        "start_coins": "Сколько монет получает новый игрок при регистрации.",
        "duel_cost": "Сколько монет стоит одна дуэль.",
    }

    await state.update_data(economy_key=key)
    await state.set_state(AdminState.entering_economy_value)

    await callback.message.edit_text(
        f"⚙️ <b>Редактирование: {key}</b>

"
        f"Текущее значение: <code>{value}</code>

"
        f"📖 <i>{descriptions.get(key, 'Нет описания')}</i>

"
        f"Введите новое значение (только число):",
        reply_markup=economy_edit_kb(key),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminState.entering_economy_value)
async def economy_edit_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    key = data.get("economy_key")

    if not key:
        await message.answer("❌ Ошибка состояния. Начните заново.")
        await state.set_state(AdminState.main)
        return

    try:
        # Проверяем что введено число
        new_value = message.text.strip()
        int(new_value)  # Валидация

        old_value = await db.get_economy_setting(key, "не задано")
        await db.set_economy_setting(key, new_value)
        await db.admin_log(message.from_user.id, "economy_edit", 0, f"{key}: {old_value} → {new_value}")

        await state.set_state(AdminState.editing_economy)
        settings = await db.get_all_economy_settings()

        await message.answer(
            f"✅ <b>Обновлено!</b>

"
            f"{key}: <code>{old_value}</code> → <code>{new_value}</code>

"
            f"⚠️ Изменения вступают в силу <b>немедленно</b> для всех игроков!",
            reply_markup=economy_settings_kb(settings),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите целое число!")


@router.callback_query(F.data == "economy_reset")
async def economy_reset_defaults(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    defaults = {
        "max_coins": "99999",
        "recovery_interval_minutes": "6",
        "win_multiplier": "2",
        "daily_recovery_limit_default": "5",
        "daily_recovery_limit_vip": "15",
        "start_coins": "10",
        "duel_cost": "1",
    }

    for key, value in defaults.items():
        await db.set_economy_setting(key, value)

    await db.admin_log(callback.from_user.id, "economy_reset", 0, "Сброс до дефолтов")

    settings = await db.get_all_economy_settings()
    await callback.message.edit_text(
        "🔄 <b>Настройки сброшены до значений по умолчанию!</b>

",
        reply_markup=economy_settings_kb(settings),
        parse_mode="HTML"
    )
    await callback.answer("✅ Сброшено!")
