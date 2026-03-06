from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states.link_state import LinkAccountState
from services.api_client import get_user_details_api, unlink_account_api
from keyboards.contact_button import get_contact_keyboard

router = Router()

@router.message(F.text == "👤 Profil")
async def show_profile(message: types.Message):
    status_code, response = await get_user_details_api(str(message.from_user.id))
    
    if status_code == 200:
        profile = response.get("profile", {})
        username = message.from_user.username or "mavjud emas"
        msg = (
            f"👤 <b>Profil ma'lumotlari</b>\n\n"
            f"Foydalanuvchi: <b>{profile.get('full_name')}</b>\n"
            f"Telefon: <code>{profile.get('phone')}</code>\n"
            f"Rol: {profile.get('role')}\n"
            f"Bog'langan sana: {profile.get('linked_at')}\n\n"
            f"Telegram ID: <code>{message.from_user.id}</code>\n"
            f"Username: @{username}"
        )
        await message.answer(msg, parse_mode="HTML")
    else:
        await message.answer("❌ Profil ma'lumotlarini yuklashda xatolik yuz berdi.")

@router.message(F.text == "🔄 Profilni almashtirish")
async def switch_profile(message: types.Message, state: FSMContext):
    # Unlink account via API
    status_code, response = await unlink_account_api(str(message.from_user.id))
    
    if status_code == 200:
        await state.clear()
        msg = (
            "🔄 <b>Hisobingiz muvaffaqiyatli uzildi!</b>\n\n"
            "Endi yangi hisobni ulash uchun avval telefon raqamingizni yuboring."
        )
        await message.answer(
            msg, 
            reply_markup=get_contact_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(LinkAccountState.waiting_for_contact)
    else:
        error_msg = response.get("error", "Hisobni uzishda xatolik yuz berdi.")
        await message.answer(f"❌ {error_msg}")
