from aiogram.fsm.state import State, StatesGroup

class LinkAccountState(StatesGroup):
    waiting_for_contact = State()
    waiting_for_code = State()
