from aiogram.fsm.state import State, StatesGroup

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_audience = State()
    confirm_send = State()
