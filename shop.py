"""Хендлеры магазина"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu, ShopState
from keyboards import shop_kb, buy_coins_kb, confirm_purchase_kb, main_menu_kb, back_to_menu_kb
from config import VIP_PRICE, RESET_LIMIT_PRICE, COIN_PRICE_DC

router = Router()


async def _check_donate_balance(user_id: int, price: int) -> tuple:
    """Возвращает (user, error_text)"""
    user = await db.get_user(user_id)
    if not user:
        return None, "❌ Пользователь не найден"
    if user["balance_donate"] < price:
        return user, f"❌ Недостаточно DC!\nНужно: {price}\nУ вас: {user['balance_donate']}"
    return user, None


@router.message(F.text == "🛒 Магазин")
async def open_shop(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала нажмите /start")
        return

    await state.set_state(ShopState.main)
    await message.answer(
        f"🛒 <b>Донат-магазин</b>\n\n"
        f"💎 Ваш баланс: <b>{user['balance_donate']} DC</b>\n\n"
        f"👑 <b>VIP Premium</b> — {VIP_PRICE} DC\n"
        f"   └ Увеличивает лимит восстановлений с 5 до 15\n\n"
        f"🔄 <b>Сброс лимита</b> — {RESET_LIMIT_PRICE} DC\n"
        f"   └ Обнуляет счётчик восстановлений на сегодня\n\n"
        f"💰 <b>Покупка монет</b> — {COIN_PRICE_DC} DC = 1 монета",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "shop_vip", ShopState.main)
async def buy_vip(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user["is_vip"]:
        await callback.answer("❌ У вас уже есть VIP!", show_alert=True)
        return

    if user["balance_donate"] < VIP_PRICE:
        await callback.answer(f"❌ Недостаточно DC! Нужно {VIP_PRICE} DC", show_alert=True)
        return

    await state.update_data(purchase_item="vip", purchase_price=VIP_PRICE, purchase_amount=0)
    await state.set_state(ShopState.confirming)

    await callback.message.edit_text(
        f"👑 <b>Покупка VIP Premium</b>\n\n"
        f"Цена: <b>{VIP_PRICE} DC</b>\n"
        f"Ваш баланс: <b>{user['balance_donate']} DC</b>\n\n"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb("vip", VIP_PRICE),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "shop_reset", ShopState.main)
async def buy_reset(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user["balance_donate"] < RESET_LIMIT_PRICE:
        await callback.answer(f"❌ Недостаточно DC! Нужно {RESET_LIMIT_PRICE} DC", show_alert=True)
        return

    await state.update_data(purchase_item="reset", purchase_price=RESET_LIMIT_PRICE, purchase_amount=0)
    await state.set_state(ShopState.confirming)

    await callback.message.edit_text(
        f"🔄 <b>Сброс лимита восстановлений</b>\n\n"
        f"Цена: <b>{RESET_LIMIT_PRICE} DC</b>\n"
        f"Ваш баланс: <b>{user['balance_donate']} DC</b>\n\n"
        f"Сбросит счётчик восстановлений на сегодня.\n"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb("reset", RESET_LIMIT_PRICE),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "shop_coins", ShopState.main)
async def buy_coins_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ShopState.buying_coins)
    user = await db.get_user(callback.from_user.id)

    await callback.message.edit_text(
        f"💰 <b>Покупка монет</b>\n\n"
        f"Курс: <b>{COIN_PRICE_DC} DC = 1 монета</b>\n"
        f"Ваш баланс DC: <b>{user['balance_donate']}</b>\n\n"
        f"Выберите количество:",
        reply_markup=buy_coins_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_coins:"), ShopState.buying_coins)
async def buy_coins_package(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    cost = amount * COIN_PRICE_DC

    if user["balance_donate"] < cost:
        await callback.answer(f"❌ Недостаточно DC! Нужно {cost} DC", show_alert=True)
        return

    await state.update_data(purchase_item=f"coins:{amount}", purchase_price=cost, purchase_amount=amount)
    await state.set_state(ShopState.confirming)

    await callback.message.edit_text(
        f"💰 <b>Покупка монет</b>\n\n"
        f"Количество: <b>{amount} монет</b>\n"
        f"Стоимость: <b>{cost} DC</b>\n\n"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb(f"coins:{amount}", cost),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "buy_coins_custom", ShopState.buying_coins)
async def buy_coins_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ShopState.entering_custom_amount)
    await callback.message.edit_text(
        f"✏️ <b>Введите количество монет для покупки:</b>\n\n"
        f"Курс: {COIN_PRICE_DC} DC = 1 монета\n"
        f"Отправьте число:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ShopState.entering_custom_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
        if amount > 10000:
            await message.answer("❌ Максимум 10000 монет за раз!")
            return
    except ValueError:
        await message.answer("❌ Введите корректное положительное число!")
        return

    user_id = message.from_user.id
    user = await db.get_user(user_id)
    cost = amount * COIN_PRICE_DC

    if user["balance_donate"] < cost:
        await message.answer(
            f"❌ Недостаточно DC!\n\n"
            f"Нужно: <b>{cost} DC</b>\n"
            f"У вас: <b>{user['balance_donate']} DC</b>",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
        await state.set_state(ShopState.main)
        return

    await state.update_data(purchase_item=f"coins:{amount}", purchase_price=cost, purchase_amount=amount)
    await state.set_state(ShopState.confirming)

    await message.answer(
        f"💰 <b>Покупка монет</b>\n\n"
        f"Количество: <b>{amount} монет</b>\n"
        f"Стоимость: <b>{cost} DC</b>\n\n"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb(f"coins:{amount}", cost),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_buy:"), ShopState.confirming)
async def confirm_purchase(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    purchase_item = data.get("purchase_item")
    purchase_price = data.get("purchase_price")
    purchase_amount = data.get("purchase_amount")

    if not purchase_item or purchase_price is None:
        await callback.answer("❌ Ошибка: данные покупки не найдены", show_alert=True)
        await state.set_state(ShopState.main)
        return

    parts = callback.data.split(":")
    item_from_callback = parts[1]
    price_from_callback = int(parts[2])

    if item_from_callback != purchase_item or price_from_callback != purchase_price:
        await callback.answer("❌ Ошибка: несоответствие данных покупки", show_alert=True)
        await state.set_state(ShopState.main)
        return

    user, error = await _check_donate_balance(user_id, purchase_price)
    if error:
        await callback.answer(error, show_alert=True)
        await state.set_state(ShopState.main)
        return

    await db.remove_donate(user_id, purchase_price, f"Покупка {purchase_item}")

    if purchase_item == "vip":
        await db.set_vip(user_id, True)
        await callback.message.edit_text(
            "🎉 <b>VIP Premium активирован!</b>\n\n"
            "Теперь ваш лимит восстановлений: <b>15</b> в сутки!",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )

    elif purchase_item == "reset":
        await db.reset_recovery_count(user_id)
        await callback.message.edit_text(
            "🔄 <b>Лимит восстановлений сброшен!</b>\n\n"
            "Счётчик обнулён. Можно снова получать монеты при балансе 0.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )

    elif purchase_item.startswith("coins"):
        await db.add_coins(user_id, purchase_amount, f"Покупка за {purchase_price} DC")
        await callback.message.edit_text(
            f"💰 <b>Монеты получены!</b>\n\n"
            f"Добавлено: <b>{purchase_amount} монет</b>\n"
            f"Списано: <b>{purchase_price} DC</b>",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )

    await state.update_data(purchase_item=None, purchase_price=None, purchase_amount=None)
    await state.set_state(ShopState.main)
    await callback.answer("✅ Покупка совершена!")


@router.callback_query(F.data == "shop_back", ShopState.confirming)
async def cancel_purchase(callback: CallbackQuery, state: FSMContext):
    await state.update_data(purchase_item=None, purchase_price=None, purchase_amount=None)
    await state.set_state(ShopState.main)

    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"🛒 <b>Донат-магазин</b>\n\n"
        f"💎 Ваш баланс: <b>{user['balance_donate']} DC</b>\n\n"
        f"👑 <b>VIP Premium</b> — {VIP_PRICE} DC\n"
        f"🔄 <b>Сброс лимита</b> — {RESET_LIMIT_PRICE} DC\n"
        f"💰 <b>Покупка монет</b> — {COIN_PRICE_DC} DC = 1 монета",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )
    await callback.answer("❌ Покупка отменена")


@router.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_purchase_expired(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Сессия покупки устарела. Начните заново.", show_alert=True)
    await state.set_state(ShopState.main)
    user = await db.get_user(callback.from_user.id)
    try:
        await callback.message.edit_text(
            f"🛒 <b>Донат-магазин</b>\n\n"
            f"💎 Ваш баланс: <b>{user['balance_donate']} DC</b>\n\n"
            f"👑 <b>VIP Premium</b> — {VIP_PRICE} DC\n"
            f"🔄 <b>Сброс лимита</b> — {RESET_LIMIT_PRICE} DC\n"
            f"💰 <b>Покупка монет</b> — {COIN_PRICE_DC} DC = 1 монета",
            reply_markup=shop_kb(),
            parse_mode="HTML"
        )
    except:
        pass


@router.callback_query(F.data == "shop_back")
async def shop_back(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ShopState.main)
    await state.update_data(purchase_item=None, purchase_price=None, purchase_amount=None)
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"🛒 <b>Донат-магазин</b>\n\n"
        f"💎 Ваш баланс: <b>{user['balance_donate']} DC</b>\n\n"
        f"👑 <b>VIP Premium</b> — {VIP_PRICE} DC\n"
        f"🔄 <b>Сброс лимита</b> — {RESET_LIMIT_PRICE} DC\n"
        f"💰 <b>Покупка монет</b> — {COIN_PRICE_DC} DC = 1 монета",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
