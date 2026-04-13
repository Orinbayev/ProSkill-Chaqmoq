from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states.link_state import LinkAccountState
from keyboards.profile_selector import get_profile_selection_keyboard, get_profile_management_keyboard, get_confirmation_keyboard
from keyboards.contact_button import get_contact_keyboard
from keyboards.menu import get_main_menu
from services.api_client import get_user_details_api, unlink_account_api, get_user_status_api
from services.deep_link_service import render_deep_link

router = Router()

@router.message(F.text == "👤 Profil")
async def list_profiles_for_view(message: types.Message, state: FSMContext):
    # Fetch all linked profiles
    status_code, response = await get_user_status_api(str(message.from_user.id))
    
    if status_code == 200 and response.get("status") == "linked":
        users = response.get("users", [])
        data = await state.get_data()
        current_email = data.get("current_user_email")
        
        await message.answer(
            f"👤 <b>Sizning profillaringiz ({len(users)} ta):</b>\n\nBatafsil ma'lumot ko'rish uchun tanlang:",
            reply_markup=get_profile_selection_keyboard(users, current_email, mode="view"),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Profilingiz bog'lanmagan. /start buyrug'ini bosing.")

@router.callback_query(F.data.startswith("view_profile_details:"))
async def view_single_profile_details(callback: types.CallbackQuery, state: FSMContext):
    email = callback.data.split(":")[2] if ":" in callback.data else callback.data.split(":")[1]
    # Handle both view_profile_details:email and view_profile_details:dummy:email formats if any
    email = callback.data.split(":")[-1]

    status_code, response = await get_user_details_api(str(callback.from_user.id), email=email)
    
    if status_code == 200:
        profile = response.get("profile", {})
        msg = (
            f"👤 <b>Profil: {profile.get('ism')}</b>\n\n"
            f"Foydalanuvchi: <b>{profile.get('full_name')}</b>\n"
            f"Email: <code>{profile.get('email')}</code>\n"
            f"Telefon: <code>{profile.get('phone')}</code>\n"
            f"Rol: {profile.get('role')}\n"
            f"Bog'langan sana: {profile.get('linked_at')}\n"
        )
        await callback.message.edit_text(
            msg, 
            reply_markup=get_profile_management_keyboard(email),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ma'lumotni yuklashda xatolik.")

@router.callback_query(F.data == "back_to_profiles")
async def back_to_profile_list(callback: types.CallbackQuery, state: FSMContext):
    status_code, response = await get_user_status_api(str(callback.from_user.id))
    if status_code == 200:
        users = response.get("users", [])
        data = await state.get_data()
        current_email = data.get("current_user_email")
        await callback.message.edit_text(
            f"👤 <b>Sizning profillaringiz ({len(users)} ta):</b>",
            reply_markup=get_profile_selection_keyboard(users, current_email, mode="view"),
            parse_mode="HTML"
        )

@router.message(F.text == "🔄 Profilni almashtirish")
async def switch_profile_menu(message: types.Message, state: FSMContext):
    status_code, response = await get_user_status_api(str(message.from_user.id))
    if status_code == 200 and response.get("status") == "linked":
        users = response.get("users", [])
        data = await state.get_data()
        current_email = data.get("current_user_email")
        await message.answer(
            "🔄 <b>Profilingizni tanlang yoki amallarni bajaring:</b>",
            reply_markup=get_profile_selection_keyboard(users, current_email, mode="select"),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Hisobingiz bog'lanmagan.")

@router.callback_query(F.data.startswith("select_profile:"))
async def select_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    email = callback.data.split(":")[1]
    
    status_code, response = await get_user_details_api(str(callback.from_user.id), email=email)
    if status_code == 200:
        profile = response.get("profile", {})
        data = await state.get_data()
        pending_start_param = data.get("pending_start_param")
        await state.update_data(
            current_user_email=email,
            current_user_role=profile.get("role_key"),
            current_user_name=profile.get("full_name"),
            current_user_id=profile.get("id"),
        )
        await callback.answer(f"✅ Profil o'zgartirildi: {profile.get('ism')}")
        await callback.message.answer(
            f"✅ Faol profil: <b>{profile.get('full_name')}</b> ({profile.get('role')})",
            reply_markup=get_main_menu(profile.get("role_key")),
            parse_mode="HTML"
        )
        if pending_start_param:
            await render_deep_link(callback.message, str(callback.from_user.id), email, pending_start_param)
            await state.update_data(pending_start_param=None)
    else:
        await callback.answer("❌ Profil yuklanmadi.")

@router.callback_query(F.data.startswith("prompt_unlink_single:"))
async def prompt_unlink_single(callback: types.CallbackQuery):
    email = callback.data.split(":")[1]
    await callback.message.edit_text(
        f"❓ <b>Haqiqatan ham ushbu profilni ({email}) uzib tashlamoqchimisiz?</b>",
        reply_markup=get_confirmation_keyboard("unlink_single", email),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm:unlink_single:"))
async def execute_unlink_single(callback: types.CallbackQuery, state: FSMContext):
    email = callback.data.split(":")[2]
    status_code, response = await unlink_account_api(str(callback.from_user.id), email=email)
    
    if status_code == 200:
        await callback.message.edit_text(f"✅ Profil ({email}) muvaffaqiyatli uzildi.")
        # Re-check if any profiles left
        status_code, status_response = await get_user_status_api(str(callback.from_user.id))
        if status_code == 200 and status_response.get("status") == "linked":
            # Select first available as fallback if the one unlinked was the current one
            data = await state.get_data()
            if data.get("current_user_email") == email:
                new_user = status_response.get("users")[0]
                await state.update_data(
                    current_user_email=new_user.get("email"),
                    current_user_role=new_user.get("role"),
                    current_user_name=new_user.get("ism"),
                )
                await callback.message.answer(f"🔄 Faol profil o'zgardi: <b>{new_user.get('ism')}</b>", parse_mode="HTML")
        else:
            await state.clear()
            await callback.message.answer("⚠️ Barcha profillar uzildi. Saytdan yangi kod oling.", reply_markup=types.ReplyKeyboardRemove())
    else:
        await callback.answer(f"❌ Xatolik: {response.get('error')}")

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
