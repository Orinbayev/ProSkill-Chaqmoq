from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards.profile_selector import get_profile_selection_keyboard
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
        users = response.get("users", [])
        
        if len(users) > 1:
            # Tell user they have multiple profiles and must choose
            await message.answer(
                f"👋 <b>Assalomu alaykum!</b>\n\nHisobingizga {len(users)} ta profil biriktirilgan. Iltimos, foydalanmoqchi bo'lgan profilingizni tanlang:",
                reply_markup=get_profile_selection_keyboard(users),
                parse_mode="HTML"
            )
        else:
            # Only one profile
            user_info = users[0]
            # Save selected user in state permanently
            await state.update_data(current_user_email=user_info.get("email"))
            
            welcome_msg = (
                f"👤 <b>Assalomu alaykum, {user_info.get('ism')}!</b>\n\n"
                f"Telegram botimizga xush kelibsiz. Hisobingiz muvaffaqiyatli bog'langan.\n"
                f"Quyidagi menyu orqali botdan foydalanishingiz mumkin."
            )
            await message.answer(welcome_msg, reply_markup=get_main_menu(), parse_mode="HTML")
    else:
        # Not linked or error
        await message.answer(
            "Assalomu alaykum. Hisobingizni ulash uchun avval telefon raqamingizni yuboring. \nBu orqali siz bitta raqamga ulangan bir nechta profillarni (Ota-ona, O'quvchi) kuzatib borishingiz mumkin.",
            reply_markup=get_contact_keyboard()
        )
        await state.set_state(LinkAccountState.waiting_for_contact)
