from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards.contact_button import get_contact_keyboard
from keyboards.menu import get_main_menu
from states.link_state import LinkAccountState
from services.api_client import get_user_status_api

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Check if user is already linked
    status_code, response = await get_user_status_api(str(message.from_user.id))
    
    if status_code == 200 and response.get("status") == "linked":
        user_info = response.get("user", {})
        welcome_msg = (
            f"👤 <b>Assalomu alaykum, {user_info.get('ism')}!</b>\n\n"
            f"Telegram botimizga xush kelibsiz. Hisobingiz muvaffaqiyatli bog'langan.\n"
            f"Quyidagi menyu orqali botdan foydalanishingiz mumkin."
        )
        await message.answer(welcome_msg, reply_markup=get_main_menu(), parse_mode="HTML")
    else:
        # Not linked or error
        await message.answer(
            "Assalomu alaykum. Hisobingizni ulash uchun avval telefon raqamingizni yuboring.",
            reply_markup=get_contact_keyboard()
        )
        await state.set_state(LinkAccountState.waiting_for_contact)
