"""Хендлеры магазина"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu, ShopState
from keyboards import shop_kb, buy_coins_kb, confirm_purchase_kb, main_menu_kb, back_to_menu_kb
from config import VIP_PRICE, RESET_LIMIT_PRICE, COIN_PRICE_DC

router = Router()


@router.message(F.text == "🛒 Магазин")
async def open_shop(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала нажмите /start")
        return

    await state.set_state(ShopState.main)
    await message.answer(
        f"🛒 <b>Донат-магазин</b>

"
        f"💎 Ваш баланс: <b>{user['balance_donate']} DC</b>

"
        f"👑 <b>VIP Premium</b> — {VIP_PRICE} DC
"
        f"   └ Увеличивает лимит восстановлений с 5 до 15

"
        f"🔄 <b>Сброс лимита</b> — {RESET_LIMIT_PRICE} DC
"
        f"   └ Обнуляет счётчик восстановлений на сегодня

"
        f"💰 <b>Покупка монет</b> — {COIN_PRICE_DC} DC = 1 монета",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "shop_vip", ShopState.main)
async def buy_vip(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user["is_vip"]:
        await callback.answer("❌ У вас уже есть VIP!", show_alert=True)
        return

    if user["balance_donate"] < VIP_PRICE:
        await callback.answer(f"❌ Недостаточно DC! Нужно {VIP_PRICE} DC", show_alert=True)
        return

    await callback.message.edit_text(
        f"👑 <b>Покупка VIP Premium</b>

"
        f"Цена: <b>{VIP_PRICE} DC</b>
"
        f"Ваш баланс: <b>{user['balance_donate']} DC</b>

"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb("vip", VIP_PRICE),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "shop_reset", ShopState.main)
async def buy_reset(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user["balance_donate"] < RESET_LIMIT_PRICE:
        await callback.answer(f"❌ Недостаточно DC! Нужно {RESET_LIMIT_PRICE} DC", show_alert=True)
        return

    await callback.message.edit_text(
        f"🔄 <b>Сброс лимита восстановлений</b>

"
        f"Цена: <b>{RESET_LIMIT_PRICE} DC</b>
"
        f"Ваш баланс: <b>{user['balance_donate']} DC</b>

"
        f"Сбросит счётчик восстановлений на сегодня.
"
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
        f"💰 <b>Покупка монет</b>

"
        f"Курс: <b>{COIN_PRICE_DC} DC = 1 монета</b>
"
        f"Ваш баланс DC: <b>{user['balance_donate']}</b>

"
        f"Выберите количество:",
        reply_markup=buy_coins_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_coins:"), ShopState.buying_coins)
async def buy_coins_package(callback: CallbackQuery):
    amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    cost = amount * COIN_PRICE_DC

    if user["balance_donate"] < cost:
        await callback.answer(f"❌ Недостаточно DC! Нужно {cost} DC", show_alert=True)
        return

    await callback.message.edit_text(
        f"💰 <b>Покупка монет</b>

"
        f"Количество: <b>{amount} монет</b>
"
        f"Стоимость: <b>{cost} DC</b>

"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb(f"coins:{amount}", cost),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "buy_coins_custom", ShopState.buying_coins)
async def buy_coins_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ShopState.entering_custom_amount)
    await callback.message.edit_text(
        "✏️ <b>Введите количество монет для покупки:</b>

"
        f"Курс: {COIN_PRICE_DC} DC = 1 монета
"
        "Отправьте число:",
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
    except ValueError:
        await message.answer("❌ Введите корректное положительное число!")
        return

    user_id = message.from_user.id
    user = await db.get_user(user_id)
    cost = amount * COIN_PRICE_DC

    if user["balance_donate"] < cost:
        await message.answer(
            f"❌ Недостаточно DC!

"
            f"Нужно: <b>{cost} DC</b>
"
            f"У вас: <b>{user['balance_donate']} DC</b>",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
        await state.set_state(ShopState.main)
        return

    await state.set_state(ShopState.main)
    await message.answer(
        f"💰 <b>Покупка монет</b>

"
        f"Количество: <b>{amount} монет</b>
"
        f"Стоимость: <b>{cost} DC</b>

"
        f"Подтвердите покупку:",
        reply_markup=confirm_purchase_kb(f"coins:{amount}", cost),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_purchase(callback: CallbackQuery):
    parts = callback.data.split(":")
    item = parts[1]
    price = int(parts[2])
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user["balance_donate"] < price:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.remove_donate(user_id, price, f"Покупка {item}")

    if item == "vip":
        await db.set_vip(user_id, True)
        await callback.message.edit_text(
            "🎉 <b>VIP Premium активирован!</b>

"
            "Теперь ваш лимит восстановлений: <b>15</b> в сутки!",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )

    elif item == "reset":
        await db.reset_recovery_count(user_id)
        await callback.message.edit_text(
            "🔄 <b>Лимит восстановлений сброшен!</b>

"
            "Счётчик обнулён. Можно снова получать монеты при балансе 0.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )

    elif item.startswith("coins"):
        amount = int(item.split(":")[1])
        await db.add_coins(user_id, amount, f"Покупка за {price} DC")
        await callback.message.edit_text(
            f"💰 <b>Монеты получены!</b>

"
            f"Добавлено: <b>{amount} монет</b>
"
            f"Списано: <b>{price} DC</b>",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )

    await callback.answer("✅ Покупка совершена!")


@router.callback_query(F.data == "shop_back")
async def shop_back(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ShopState.main)
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"🛒 <b>Донат-магазин</b>

"
        f"💎 Ваш баланс: <b>{user['balance_donate']} DC</b>

"
        f"👑 <b>VIP Premium</b> — {VIP_PRICE} DC
"
        f"🔄 <b>Сброс лимита</b> — {RESET_LIMIT_PRICE} DC
"
        f"💰 <b>Покупка монет</b> — {COIN_PRICE_DC} DC = 1 монета",
        reply_markup=shop_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
