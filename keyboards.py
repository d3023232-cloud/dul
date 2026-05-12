"""Клавиатуры бота"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import COIN_PACKAGES, ADMIN_USERS_PER_PAGE


# === ГЛАВНОЕ МЕНЮ ===
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚔️ Дуэль"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="🔗 Рефералка")],
            [KeyboardButton(text="📊 Топ игроков")],
        ],
        resize_keyboard=True
    )


# === АДМИН-МЕНЮ ===
def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Список игроков", callback_data="admin_users")],
            [InlineKeyboardButton(text="🔍 Поиск игрока", callback_data="admin_search")],
            [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="⚔️ Активные дуэли", callback_data="admin_duels")],
            [InlineKeyboardButton(text="⚙️ Настройки экономики", callback_data="admin_economy")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
        ]
    )


def admin_user_list_kb(users: list, page: int = 0, per_page: int = ADMIN_USERS_PER_PAGE) -> InlineKeyboardMarkup:
    """Список пользователей для админа"""
    buttons = []
    start = page * per_page
    end = start + per_page

    for user in users[start:end]:
        name = user.get("first_name") or user.get("username") or f"ID:{user['telegram_id']}"
        status = "🚫" if user.get("is_banned") else ("👑" if user.get("is_vip") else "👤")
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {name} | 💰{user['balance_coins']} | 💎{user['balance_donate']}",
                callback_data=f"admin_view_user:{user['telegram_id']}"
            )
        ])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page+1}", callback_data="admin_nop"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_page:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_user_actions_kb(user_id: int, is_banned: bool = False, is_vip: bool = False) -> InlineKeyboardMarkup:
    """Действия над конкретным пользователем"""
    buttons = [
        [InlineKeyboardButton(text="➕ Выдать монеты", callback_data=f"admin_give_coins:{user_id}")],
        [InlineKeyboardButton(text="➖ Забрать монеты", callback_data=f"admin_take_coins:{user_id}")],
        [InlineKeyboardButton(text="➕ Выдать DC", callback_data=f"admin_give_dc:{user_id}")],
        [InlineKeyboardButton(text="➖ Забрать DC", callback_data=f"admin_take_dc:{user_id}")],
    ]

    if is_vip:
        buttons.append([InlineKeyboardButton(text="❌ Снять VIP", callback_data=f"admin_remove_vip:{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="👑 Дать VIP", callback_data=f"admin_give_vip:{user_id}")])

    if is_banned:
        buttons.append([InlineKeyboardButton(text="✅ Разбанить", callback_data=f"admin_unban:{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_ban:{user_id}")])

    buttons.append([InlineKeyboardButton(text="📜 Транзакции", callback_data=f"admin_transactions:{user_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_users")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_confirm_kb(action: str, user_id: int, amount: int = 0) -> InlineKeyboardMarkup:
    """Подтверждение админ-действия"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm:{action}:{user_id}:{amount}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_view_user:{user_id}"),
            ]
        ]
    )


# === ПОДПИСКА НА КАНАЛ ===
def subscribe_kb(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_link)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscribe")],
        ]
    )


# === ДУЭЛЬ ===
def duel_invite_kb(duel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"duel_accept:{duel_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"duel_decline:{duel_id}"),
            ]
        ]
    )


def duel_opponent_select_kb(users: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Список пользователей для вызова на дуэль"""
    buttons = []
    start = page * per_page
    end = start + per_page

    for user in users[start:end]:
        name = user.get("first_name") or user.get("username") or f"User {user['telegram_id']}"
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {name}", 
                callback_data=f"duel_challenge:{user['telegram_id']}"
            )
        ])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"duel_page:{page-1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"duel_page:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="✏️ Пригласить по @username", callback_data="duel_by_username")])
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# === МАГАЗИН ===
def shop_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 VIP Premium (299 DC)", callback_data="shop_vip")],
            [InlineKeyboardButton(text="🔄 Сброс лимита (50 DC)", callback_data="shop_reset")],
            [InlineKeyboardButton(text="💰 Купить монеты", callback_data="shop_coins")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
        ]
    )


def buy_coins_kb() -> InlineKeyboardMarkup:
    buttons = []
    for pkg in COIN_PACKAGES:
        cost = pkg * 5
        buttons.append([
            InlineKeyboardButton(
                text=f"{pkg} монет — {cost} DC", 
                callback_data=f"buy_coins:{pkg}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="✏️ Свое количество", callback_data="buy_coins_custom")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="shop_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_purchase_kb(item: str, price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Купить", callback_data=f"confirm_buy:{item}:{price}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="shop_back"),
            ]
        ]
    )


# === РЕФЕРАЛКА ===
def referral_kb(referral_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться", url=f"https://t.me/share/url?url={referral_link}")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
        ]
    )


# === ПРОФИЛЬ ===
def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_profile")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
        ]
    )


# === УТИЛИТЫ ===
def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
        ]
    )

# === ЭКОНОМИКА (АДМИН) ===
def economy_settings_kb(settings: list) -> InlineKeyboardMarkup:
    """Клавиатура настроек экономики"""
    buttons = []
    for s in settings:
        buttons.append([
            InlineKeyboardButton(
                text=f"⚙️ {s['key']} = {s['value']}",
                callback_data=f"economy_edit:{s['key']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔄 Сбросить дефолты", callback_data="economy_reset")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def economy_edit_kb(key: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения редактирования"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ввести новое значение", callback_data=f"economy_input:{key}")],
            [InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="admin_economy")],
        ]
    )
