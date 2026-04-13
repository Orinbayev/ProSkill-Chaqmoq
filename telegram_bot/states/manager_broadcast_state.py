from aiogram.fsm.state import State, StatesGroup


class ManagerBroadcastState(StatesGroup):
    waiting_for_audience = State()
    waiting_for_message = State()
