from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    main = State()


class DuelState(StatesGroup):
    selecting_opponent = State()
    entering_username = State()


class ShopState(StatesGroup):
    main = State()
    buying_coins = State()
    entering_custom_amount = State()
    confirming = State()


class AdminState(StatesGroup):
    main = State()
    entering_amount = State()
    searching_user = State()
    broadcasting = State()
    editing_economy = State()
    entering_economy_value = State()
