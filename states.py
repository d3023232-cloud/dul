"""FSM (Finite State Machine) состояния бота"""

from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    main = State()


class DuelState(StatesGroup):
    selecting_opponent = State()
    waiting_response = State()
    entering_username = State()
    in_animation = State()
    result = State()


class ShopState(StatesGroup):
    main = State()
    buying_coins = State()
    entering_custom_amount = State()


class ReferralState(StatesGroup):
    entering_code = State()


class ProfileState(StatesGroup):
    viewing = State()


class AdminState(StatesGroup):
    main = State()
    viewing_user = State()
    editing_user = State()
    entering_amount = State()
    searching_user = State()
    broadcasting = State()
    editing_economy = State()
    entering_economy_value = State()
