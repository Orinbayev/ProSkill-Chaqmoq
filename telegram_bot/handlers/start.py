from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from keyboards.profile_selector import get_profile_selection_keyboard
from keyboards.contact_button import get_contact_keyboard
from keyboards.menu import get_main_menu
from states.link_state import LinkAccountState
from services.api_client import connect_parent_link_api, get_user_status_api
from services.deep_link_service import render_deep_link

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    await state.clear()
    start_param = (command.args or "").strip() if command else ""
    if start_param:
        await state.update_data(pending_start_param=start_param)

    if start_param.startswith("parent_"):
        token = start_param.split("parent_", 1)[1].strip()
        status_code, response = await connect_parent_link_api(
            token=token,
            telegram_id=str(message.from_user.id),
            telegram_username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        if status_code == 200 and response.get("ok"):
            parent = response.get("parent") or {}
            student = response.get("student") or {}
            await state.update_data(
                current_user_email=parent.get("email"),
                current_user_role="parent",
                current_user_name=parent.get("full_name") or parent.get("email"),
                pending_start_param=None,
            )
            await message.answer(
                "✅ <b>Ota-ona botga ulandi</b>\n\n"
                f"Farzand: <b>{student.get('full_name', 'Oquvchi')}</b>\n"
                f"Markaz: <b>{student.get('center') or '—'}</b>\n\n"
                "Endi farzandingiz bo'yicha ma'lumotlarni bot orqali kuzatishingiz mumkin.",
                reply_markup=get_main_menu("parent"),
                parse_mode="HTML",
            )
            return

        error_text = response.get("error") or "Link noto'g'ri yoki muddati tugagan."
        await message.answer(
            "❌ <b>Ota-onani ulab bo'lmadi</b>\n\n"
            f"{error_text}\n\n"
            "Iltimos, admin yuborgan yangi linkdan foydalaning.",
            parse_mode="HTML",
        )
        return
    
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
            await state.update_data(
                current_user_email=user_info.get("email"),
                current_user_role=user_info.get("role"),
                current_user_name=user_info.get("ism"),
            )
            
            welcome_msg = (
                f"👤 <b>Assalomu alaykum, {user_info.get('ism')}!</b>\n\n"
                f"Telegram botimizga xush kelibsiz. Hisobingiz muvaffaqiyatli bog'langan.\n"
                f"Quyidagi menyu orqali botdan foydalanishingiz mumkin."
            )
            await message.answer(
                welcome_msg,
                reply_markup=get_main_menu(user_info.get("role")),
                parse_mode="HTML",
            )
            if start_param:
                await render_deep_link(message, str(message.from_user.id), user_info.get("email"), start_param)
                await state.update_data(pending_start_param=None)
    else:
        # Not linked or error
        await message.answer(
            "Assalomu alaykum. Hisobingizni ulash uchun avval telefon raqamingizni yuboring. \nBu orqali siz bitta raqamga ulangan bir nechta profillarni (Ota-ona, O'quvchi) kuzatib borishingiz mumkin.",
            reply_markup=get_contact_keyboard()
        )
        await state.set_state(LinkAccountState.waiting_for_contact)
