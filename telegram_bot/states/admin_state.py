from aiogram.fsm.state import State, StatesGroup

class AdminState(StatesGroup):
    waiting_for_admin_id = State()
