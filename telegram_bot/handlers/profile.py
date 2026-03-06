from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states.link_state import LinkAccountState
from keyboards.profile_selector import get_profile_selection_keyboard, get_confirmation_keyboard
from keyboards.contact_button import get_contact_keyboard
from keyboards.menu import get_main_menu
from services.api_client import get_user_details_api, unlink_account_api, get_user_status_api

router = Router()

@router.message(F.text == "👤 Profil")
async def show_profile(message: types.Message, state: FSMContext):
    data = await state.get_data()
    email = data.get("current_user_email")
    
    status_code, response = await get_user_details_api(str(message.from_user.id), email=email)
    
    if status_code == 200:
        profile = response.get("profile", {})
        username = message.from_user.username or "mavjud emas"
        msg = (
            f"👤 <b>Profil ma'lumotlari</b>\n\n"
            f"Foydalanuvchi: <b>{profile.get('full_name')}</b>\n"
            f"Email: <code>{profile.get('email')}</code>\n"
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
async def switch_profile_menu(message: types.Message, state: FSMContext):
    # Fetch all linked profiles
    status_code, response = await get_user_status_api(str(message.from_user.id))
    
    if status_code == 200 and response.get("status") == "linked":
        users = response.get("users", [])
        await message.answer(
            "🔄 <b>Profilingizni tanlang yoki amallarni bajaring:</b>",
            reply_markup=get_profile_selection_keyboard(users),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Hisobingiz bog'lanmagan.")

# Callback handlers for selection and confirmation
@router.callback_query(F.data.startswith("select_profile:"))
async def select_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    email = callback.data.split(":")[1]
    await state.update_data(current_user_email=email)
    
    # Get user info and confirm
    status_code, response = await get_user_details_api(str(callback.from_user.id), email=email)
    if status_code == 200:
        profile = response.get("profile", {})
        await callback.answer(f"✅ Profil o'zgartirildi: {profile.get('asm')}")
        await callback.message.answer(
            f"✅ Faol profil: <b>{profile.get('full_name')}</b> ({profile.get('role')})",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Profil yuklanmadi.")

@router.callback_query(F.data == "confirm_unlink_all")
async def prompt_unlink_all(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ <b>Haqiqatan ham barcha profillarni Telegramdan uzmoqchimisiz?</b>",
        reply_markup=get_confirmation_keyboard("unlink_all"),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "confirm:unlink_all:")
async def execute_unlink_all(callback: types.CallbackQuery, state: FSMContext):
    status_code, response = await unlink_account_api(str(callback.from_user.id))
    if status_code == 200:
        await state.clear()
        await callback.message.edit_text("✅ Barcha profillar hisobingizdan uzildi.")
        await callback.message.answer(
            "Yangi profil bog'lash uchun /start buyrug'ini bosing.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await callback.answer(f"❌ Xatolik: {response.get('error')}")

@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: types.CallbackQuery):
    await callback.answer("Bekor qilindi.")
    await callback.message.delete()

@router.callback_query(F.data == "add_profile")
async def add_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Yangi profil qo'shish uchun telefon raqamingizni yuboring.",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(LinkAccountState.waiting_for_contact)
    await callback.answer()
