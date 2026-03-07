from aiogram import Router, F, types
from services.api_client import get_admin_dashboard_api, manage_admins_api
from aiogram.fsm.context import FSMContext
from states.admin_state import AdminState

router = Router()

@router.message(F.text == "👨💼 Adminlar")
async def admin_list(message: types.Message):
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"): return

    s, d = await manage_admins_api(str(message.from_user.id), action="list")
    if s != 200:
        return await message.answer("❌ Adminlar ro'yxatini yuklashda xatolik.")

    admins = d.get("admins", [])
    text = "👨💼 **Bot Adminlari ro'yxati**\n\n"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[])
    
    for a in admins:
        text += f"• {a['full_name']} (@{a['username']})\n"
        text += f"  ID: `{a['tg_id']}` | Qo'shildi: {a['created_at']}\n\n"
        
        # Add button to remove if not self
        if str(a['tg_id']) != str(message.from_user.id):
            kb.inline_keyboard.append([
                types.InlineKeyboardButton(text=f"❌ {a['full_name']}ni o'chirish", 
                                           callback_data=f"remove_admin:{a['tg_id']}")
            ])

    kb.inline_keyboard.append([
        types.InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="add_admin_init")
    ])

    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "add_admin_init")
async def add_admin_init(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_admin_id)
    await callback.message.answer(
        "📝 Yangi admin qo'shish uchun uning **Telegram ID** raqamini yuboring.\n\n"
        "ℹ️ Eslatma: Foydalanuvchi avval botdan o'z profili bilan ro'yxatdan o'tgan bo'lishi shart."
    )

@router.message(AdminState.waiting_for_admin_id)
async def process_add_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Telegram ID faqat raqamlardan iborat bo'lishi kerak.")
    
    status, data = await manage_admins_api(
        str(message.from_user.id), 
        action="add", 
        target_tg_id=message.text,
        target_username="Noma'lum"
    )
    
    if status == 200:
        await message.answer(f"✅ Foydalanuvchi ({message.text}) adminlar qatoriga qo'shildi.")
        await state.clear()
        await admin_list(message)
    else:
        error_msg = data.get('error') if data.get('error') else "Noma'lum xatolik"
        await message.answer(f"❌ Xatolik: {error_msg}")
        await state.clear()

@router.callback_query(F.data.startswith("remove_admin:"))
async def remove_admin(callback: types.CallbackQuery):
    target_id = callback.data.split(":")[1]
    s, d = await manage_admins_api(str(callback.from_user.id), action="remove", target_tg_id=target_id)
    
    if s == 200:
        await callback.answer("✅ Admin o'chirildi", show_alert=True)
        await admin_list(callback.message) # Refresh
    else:
        error_msg = d.get('error') if d.get('error') else "Noma'lum xatolik"
        await callback.answer(f"❌ Xatolik: {error_msg}", show_alert=True)
