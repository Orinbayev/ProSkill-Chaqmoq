from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states.link_state import LinkAccountState
from services.phone_utils import normalize_phone
from services.api_client import link_account_api
from keyboards.menu import get_main_menu
from services.deep_link_service import render_deep_link

router = Router()

@router.message(LinkAccountState.waiting_for_contact, F.contact)
async def handle_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.contact.phone_number)
    await state.update_data(phone=phone)
    await message.answer(
        "Rahmat. Endi saytdan olingan 6 xonali ulash kodini yuboring.",
        reply_markup=types.ReplyKeyboardRemove()
    )

    await state.set_state(LinkAccountState.waiting_for_code)

@router.message(LinkAccountState.waiting_for_code)
async def handle_code(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit() or len(message.text) != 6:
        await message.answer("Iltimos, saytdan olingan 6 xonali raqamli kodni yuboring.")
        return
    
    code = message.text.strip()
    user_data = await state.get_data()
    phone = user_data.get("phone")
    pending_start_param = user_data.get("pending_start_param")
    
    status_code, response = await link_account_api(
        phone=phone,
        code=code,
        telegram_id=str(message.from_user.id),
        telegram_username=message.from_user.username
    )
    
    if status_code == 200:
        updated_phone = response.get("updated_phone", phone)
        user_email = response.get("user", "")
        user_role = response.get("role")
        full_name = response.get("full_name")
        
        # Save current user email for multi-profile support
        await state.clear()
        await state.update_data(
            current_user_email=user_email,
            current_user_role=user_role,
            current_user_name=full_name,
        )
        
        # Proper Telegram formatting (using HTML parse_mode correctly)
        msg = (
            f"✅ <b>Hisobingiz muvaffaqiyatli bog'landi</b>\n\n"
            f"Tasdiqlangan telefon raqami: <b>{updated_phone}</b>\n"
            f"Ushbu raqam hisobingizga (<code>{user_email}</code>) biriktirildi.\n\n"
            f"Agar sizda bir nechta profil bo'lsa (masalan, ota-ona va o'quvchi), ularning barchasini bitta Telegramga ulashingiz mumkin."
        )
        await message.answer(msg, reply_markup=get_main_menu(user_role), parse_mode="HTML")
        if pending_start_param:
            await render_deep_link(message, str(message.from_user.id), user_email, pending_start_param)
            await state.update_data(pending_start_param=None)
    else:
        error_msg = response.get("error", "Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        await message.answer(f"❌ {error_msg}")
