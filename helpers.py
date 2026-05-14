"""Хендлеры дуэлей"""

import asyncio
import random
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from states import MainMenu, DuelState
from keyboards import duel_opponent_select_kb, duel_invite_kb, main_menu_kb, back_to_menu_kb
from helpers import format_user_name, get_duel_frames

router = Router()

# Хранилище активных таймеров дуэлей: {duel_id: asyncio.Task}
active_timers = {}


@router.message(F.text == "⚔️ Дуэль")
async def start_duel(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await message.answer("❌ Сначала нажмите /start")
        return

    duel_cost = await db.get_economy_setting_int("duel_cost", 1)

    if user["balance_coins"] < duel_cost:
        can_recover = await db.can_recover(user_id)
        if can_recover:
            await db.recover_coin(user_id)
            user = await db.get_user(user_id)
            recovery_limit = await db.get_recovery_limit(user_id)
            await message.answer(
                f"💰 <b>Восстановление!</b>\n\n"
                f"Вам начислена 1 монета (восстановление {user['recoveries_today']}/"
                f"{recovery_limit}).\n"
                f"Теперь у вас {user['balance_coins']} монет."
            )
        else:
            limit = await db.get_recovery_limit(user_id)
            if user["recoveries_today"] >= limit:
                await message.answer(
                    f"❌ <b>Монеты закончились!</b>\n\n"
                    f"Вы использовали все восстановления на сегодня ({limit}/{limit}).\n"
                    f"Следующее обновление в 00:00 по МСК.\n\n"
                    f"💎 Можно купить монеты в магазине или приобрести VIP!",
                    reply_markup=main_menu_kb()
                )
            else:
                recovery_min = await db.get_economy_setting_int("recovery_interval_minutes", 6)
                await message.answer(
                    f"❌ <b>Недостаточно монет!</b>\n\n"
                    f"Баланс: {user['balance_coins']} монет\n"
                    f"Следующее восстановление через {recovery_min} минут.\n\n"
                    f"💎 Или купите монеты в магазине!",
                    reply_markup=main_menu_kb()
                )
            return

    all_users = await db.get_all_users()
    opponents = [u for u in all_users if u["telegram_id"] != user_id and u["subscribed_channel"]]

    if not opponents:
        await message.answer(
            "😕 <b>Пока нет доступных соперников!</b>\n\n"
            "Пригласите друзей по реферальной ссылке или введите @username!",
            reply_markup=main_menu_kb()
        )
        return

    await state.set_state(DuelState.selecting_opponent)
    await message.answer(
        "🎯 <b>Выберите соперника для дуэли:</b>\n\n"
        f"💰 Ваш баланс: {user['balance_coins']} монет\n\n"
        "Или пригласите друга по @username:",
        reply_markup=duel_opponent_select_kb(opponents)
    )


@router.callback_query(F.data.startswith("duel_page:"))
async def duel_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":")[1])
    all_users = await db.get_all_users()
    user_id = callback.from_user.id
    opponents = [u for u in all_users if u["telegram_id"] != user_id and u["subscribed_channel"]]

    await callback.message.edit_reply_markup(
        reply_markup=duel_opponent_select_kb(opponents, page=page)
    )
    await callback.answer()


@router.callback_query(F.data == "duel_by_username")
async def duel_by_username_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DuelState.entering_username)
    await callback.message.edit_text(
        "✏️ <b>Пригласить на дуэль по @username</b>\n\n"
        "Введите юзернейм соперника (например: @ivan):\n\n"
        "⚠️ Соперник должен быть зарегистрирован в боте и подписан на канал.",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(DuelState.entering_username)
async def duel_by_username_process(message: Message, state: FSMContext, bot: Bot):
    username_input = message.text.strip().lstrip("@")
    challenger_id = message.from_user.id

    if not username_input:
        await message.answer("❌ Введите корректный @username!")
        return

    all_users = await db.get_all_users()
    opponent = None
    for u in all_users:
        if u.get("username") and u["username"].lower() == username_input.lower():
            opponent = u
            break

    if not opponent:
        await message.answer(
            f"❌ Игрок <b>@{username_input}</b> не найден!\n\n"
            f"Убедитесь, что он:\n"
            f"• Зарегистрирован в боте\n"
            f"• Имеет установленный @username\n"
            f"• Подписан на канал",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
        await state.set_state(DuelState.selecting_opponent)
        return

    opponent_id = opponent["telegram_id"]

    if opponent_id == challenger_id:
        await message.answer("❌ Нельзя вызвать самого себя!")
        return

    if not opponent.get("subscribed_channel"):
        await message.answer(
            f"❌ <b>@{username_input}</b> не подписан на канал и не может участвовать в дуэлях.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
        await state.set_state(DuelState.selecting_opponent)
        return

    challenger = await db.get_user(challenger_id)
    duel_cost = await db.get_economy_setting_int("duel_cost", 1)

    if challenger["balance_coins"] < duel_cost:
        await message.answer("❌ Недостаточно монет!")
        await state.set_state(MainMenu.main)
        return

    await state.set_state(MainMenu.main)
    await send_duel_invite(bot, challenger_id, opponent_id, message, state)


async def _timer_task(bot: Bot, duel_id: int, dots_msg, timeout: int):
    """Фоновая задача таймера с обратным отсчётом"""
    start_time = asyncio.get_event_loop().time()

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            break

        remaining = int(timeout - elapsed)
        dots = [".", "..", "..."][int(elapsed * 2) % 3]

        try:
            await dots_msg.edit_text(f"⏳ Ждём ответа{dots} ({remaining} сек)")
        except:
            pass

        await asyncio.sleep(0.5)

        # Проверяем, не отменена ли дуэль
        duel = await db.get_duel(duel_id)
        if duel and duel["status"] != "pending":
            try:
                await dots_msg.delete()
            except:
                pass
            return

    # Таймаут — проверяем ещё раз
    duel = await db.get_duel(duel_id)
    if duel and duel["status"] == "pending":
        await _handle_timeout(bot, duel_id)


async def _handle_timeout(bot: Bot, duel_id: int):
    """Обработка таймаута дуэли"""
    duel = await db.get_duel(duel_id)
    if not duel or duel["status"] != "pending":
        return

    challenger_id = duel["challenger_id"]
    opponent_id = duel["opponent_id"]
    duel_cost = duel["bet"]

    challenger = await db.get_user(challenger_id)
    opponent = await db.get_user(opponent_id)

    await db.update_duel_status(duel_id, "expired")
    await db.add_coins(challenger_id, duel_cost, "Возврат ставки (таймаут)")

    try:
        await bot.send_message(
            opponent_id,
            "⏰ <b>Время вышло!</b> Заявка истекла.",
            parse_mode="HTML"
        )
    except:
        pass

    try:
        await bot.send_message(
            challenger_id,
            f"😏 <b>{format_user_name(opponent)} испугался!</b>\n\n"
            f"Соперник не ответил на вызов в течение 30 секунд.\n"
            f"💰 {duel_cost} монета возвращена.\n\n"
            f"🔥 Попробуйте вызвать кого-то другого!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    except:
        pass

    active_timers.pop(duel_id, None)


async def send_duel_invite(bot: Bot, challenger_id: int, opponent_id: int, message_or_callback, state: FSMContext):
    """Отправляет приглашение на дуэль с таймаутом 30 секунд"""

    challenger = await db.get_user(challenger_id)
    opponent = await db.get_user(opponent_id)
    duel_cost = await db.get_economy_setting_int("duel_cost", 1)

    await db.remove_coins(challenger_id, duel_cost, "Ставка в дуэли")

    duel_id = await db.create_duel(challenger_id, opponent_id, duel_cost)

    challenger_name = format_user_name(challenger)
    opponent_name = format_user_name(opponent)

    await bot.send_message(
        opponent_id,
        f"⚔️ <b>Вас вызывают на дуэль!</b>\n\n"
        f"👤 <b>{challenger_name}</b> бросает вам вызов!\n\n"
        f"💰 Ставка: <b>{duel_cost} монета</b>\n\n"
        f"⏳ У вас есть <b>30 секунд</b> на ответ!",
        reply_markup=duel_invite_kb(duel_id),
        parse_mode="HTML"
    )

    await bot.send_message(
        challenger_id,
        f"⚔️ <b>Заявка отправлена!</b>\n\n"
        f"Вы бросили вызов <b>{opponent_name}</b>\n"
        f"💰 Ставка: <b>{duel_cost} монета</b>\n\n"
        f"⏳ Ждём ответа соперника в течение <b>30 секунд</b>...",
        parse_mode="HTML"
    )

    dots_msg = await bot.send_message(opponent_id, "⏳ Ждём ответа... (30 сек)")

    task = asyncio.create_task(_timer_task(bot, duel_id, dots_msg, 30))
    active_timers[duel_id] = task


@router.callback_query(F.data.startswith("duel_challenge:"))
async def send_duel_invite_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    challenger_id = callback.from_user.id
    opponent_id = int(callback.data.split(":")[1])

    if challenger_id == opponent_id:
        await callback.answer("❌ Нельзя вызвать самого себя!", show_alert=True)
        return

    challenger = await db.get_user(challenger_id)
    opponent = await db.get_user(opponent_id)

    if not challenger or not opponent:
        await callback.answer("❌ Ошибка!", show_alert=True)
        return

    duel_cost = await db.get_economy_setting_int("duel_cost", 1)

    if challenger["balance_coins"] < duel_cost:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return

    await callback.answer("⚔️ Заявка отправлена!")
    await state.set_state(MainMenu.main)
    await send_duel_invite(bot, challenger_id, opponent_id, callback, state)


@router.callback_query(F.data.startswith("duel_accept:"))
async def accept_duel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    duel_id = int(callback.data.split(":")[1])
    opponent_id = callback.from_user.id

    duel = await db.get_duel(duel_id)
    if not duel or duel["status"] != "pending":
        await callback.answer("❌ Дуэль уже недоступна!", show_alert=True)
        return

    challenger_id = duel["challenger_id"]

    if opponent_id != duel["opponent_id"]:
        await callback.answer("❌ Это не ваша дуэль!", show_alert=True)
        return

    # Отменяем таймер
    task = active_timers.pop(duel_id, None)
    if task:
        task.cancel()

    opponent = await db.get_user(opponent_id)
    duel_cost = await db.get_economy_setting_int("duel_cost", 1)

    if opponent["balance_coins"] < duel_cost:
        await callback.answer("❌ У вас недостаточно монет!", show_alert=True)
        await db.add_coins(challenger_id, duel_cost, "Возврат ставки (недостаточно монет)")
        await db.update_duel_status(duel_id, "cancelled")
        return

    await db.remove_coins(opponent_id, duel_cost, "Ставка в дуэли")
    await db.update_duel_status(duel_id, "active")

    await callback.message.edit_text("✅ <b>Вы приняли вызов!</b>\n\nДуэль начинается...")

    await run_duel_animation(bot, challenger_id, opponent_id, duel_id)

    await callback.answer()


@router.callback_query(F.data.startswith("duel_decline:"))
async def decline_duel(callback: CallbackQuery, bot: Bot):
    duel_id = int(callback.data.split(":")[1])
    opponent_id = callback.from_user.id

    duel = await db.get_duel(duel_id)
    if not duel or duel["status"] != "pending":
        await callback.answer("❌ Дуэль уже недоступна!", show_alert=True)
        return

    # Отменяем таймер
    task = active_timers.pop(duel_id, None)
    if task:
        task.cancel()

    challenger_id = duel["challenger_id"]
    duel_cost = duel["bet"]

    await db.add_coins(challenger_id, duel_cost, "Возврат ставки (отказ)")
    await db.update_duel_status(duel_id, "declined")

    await callback.message.edit_text("❌ <b>Вы отклонили вызов.</b>")
    await bot.send_message(
        challenger_id,
        f"❌ <b>{format_user_name(await db.get_user(opponent_id))}</b> отклонил ваш вызов.\n"
        f"💰 {duel_cost} монета возвращена.",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


async def run_duel_animation(bot: Bot, challenger_id: int, opponent_id: int, duel_id: int):
    """Анимация перестрелки для обоих игроков"""
    frames = get_duel_frames()
    duel_cost = await db.get_economy_setting_int("duel_cost", 1)

    msg_ch = await bot.send_message(challenger_id, "⚔️ <b>ДУЭЛЬ НАЧАЛАСЬ!</b>\n\n" + frames[0], parse_mode="HTML")
    msg_op = await bot.send_message(opponent_id, "⚔️ <b>ДУЭЛЬ НАЧАЛАСЬ!</b>\n\n" + frames[0], parse_mode="HTML")

    for i, frame in enumerate(frames[1:], 1):
        await asyncio.sleep(1.2)
        text = f"⚔️ <b>ДУЭЛЬ НАЧАЛАСЬ!</b>\n\n{frame}"
        try:
            await msg_ch.edit_text(text, parse_mode="HTML")
        except:
            pass
        try:
            await msg_op.edit_text(text, parse_mode="HTML")
        except:
            pass

    await asyncio.sleep(0.5)

    winner_id = random.choice([challenger_id, opponent_id])
    loser_id = opponent_id if winner_id == challenger_id else challenger_id

    await db.add_win(winner_id)
    await db.add_loss(loser_id)
    await db.update_duel_status(duel_id, "completed", winner_id)

    win_multiplier = await db.get_economy_setting_int("win_multiplier", 2)
    await db.add_coins(winner_id, duel_cost * win_multiplier, "Выигрыш в дуэли")

    for uid in [challenger_id, opponent_id]:
        user = await db.get_user(uid)
        if user and user["referred_by"]:
            await db.update_referral_duels(uid)
            if await db.check_referral_reward(user["referred_by"], uid):
                from config import REFERRAL_REWARD_DC
                await db.add_donate(user["referred_by"], REFERRAL_REWARD_DC, 
                                   f"Бонус за 18 дуэлей реферала {uid}")
                await db.mark_referral_rewarded(user["referred_by"], uid)
                await bot.send_message(
                    user["referred_by"],
                    f"🎉 <b>Реферальный бонус!</b>\n\n"
                    f"Ваш реферал сыграл 18 дуэлей!\n"
                    f"💎 Получено {REFERRAL_REWARD_DC} донат-коина!"
                )

    winner = await db.get_user(winner_id)
    loser = await db.get_user(loser_id)

    await msg_ch.edit_text(
        f"{'🏆' if winner_id == challenger_id else '💀'} <b>РЕЗУЛЬТАТ ДУЭЛИ</b>\n\n"
        f"{'🎉 Вы победили!' if winner_id == challenger_id else '💔 Вы проиграли...'}\n\n"
        f"💰 {'+' if winner_id == challenger_id else '-'}{duel_cost} монета\n"
        f"📊 Баланс: {winner['balance_coins'] if winner_id == challenger_id else loser['balance_coins']} монет",
        parse_mode="HTML"
    )

    await msg_op.edit_text(
        f"{'🏆' if winner_id == opponent_id else '💀'} <b>РЕЗУЛЬТАТ ДУЭЛИ</b>\n\n"
        f"{'🎉 Вы победили!' if winner_id == opponent_id else '💔 Вы проиграли...'}\n\n"
        f"💰 {'+' if winner_id == opponent_id else '-'}{duel_cost} монета\n"
        f"📊 Баланс: {winner['balance_coins'] if winner_id == opponent_id else loser['balance_coins']} монет",
        parse_mode="HTML"
    )

    await asyncio.sleep(3)
    await bot.send_message(challenger_id, "🏠 Возвращаемся в меню...", reply_markup=main_menu_kb())
    await bot.send_message(opponent_id, "🏠 Возвращаемся в меню...", reply_markup=main_menu_kb())
