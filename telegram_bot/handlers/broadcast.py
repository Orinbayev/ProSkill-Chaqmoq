from aiogram import Router, F, types, Bot, html
from aiogram.fsm.context import FSMContext
from states.broadcast_state import BroadcastState
from keyboards.admin_menu import get_role_filter_kb, get_admin_main_kb
from services.api_client import get_admin_dashboard_api, get_broadcast_list_api
import asyncio

router = Router()

ROLE_MAP = {
    "Barchaga": "all",
    "Ota-onalar": "parent",
    "Studentlar": "student",
    "Teacherlar": "teacher",
    "Managerlar": "manager",
    "Directorlar": "director",
    "Superadminlar": "superadmin"
}

@router.message(F.text == "📢 Reklama yuborish")
async def broadcast_init(message: types.Message, state: FSMContext):
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"): return

    await state.set_state(BroadcastState.waiting_for_message)
    await message.answer("📝 Iltimos, reklama xabarini yuboring (Matn, rasm yoki hujjat):", 
                         reply_markup=types.ReplyKeyboardRemove())

@router.message(BroadcastState.waiting_for_message)
async def broadcast_get_msg(message: types.Message, state: FSMContext):
    # Store the message details
    msg_data = {
        "text": message.text or message.caption,
        "photo": message.photo[-1].file_id if message.photo else None,
        "document": message.document.file_id if message.document else None,
        "content_type": message.content_type,
        "entities": message.entities or message.caption_entities
    }
    
    await state.update_data(broadcast_msg=msg_data)
    await state.set_state(BroadcastState.waiting_for_audience)
    await message.answer("🎯 Kimlarga yubormoqchisiz?", reply_markup=get_role_filter_kb())

@router.message(BroadcastState.waiting_for_audience, F.text.in_(ROLE_MAP.keys()))
async def broadcast_get_audience(message: types.Message, state: FSMContext):
    role_key = ROLE_MAP[message.text]
    await state.update_data(audience=role_key, audience_name=message.text)
    
    await state.set_state(BroadcastState.confirm_send)
    await message.answer(f"❓ Xabar {message.text} guruhiga yuborilsinmi?", 
                         reply_markup=types.ReplyKeyboardMarkup(
                             keyboard=[[types.KeyboardButton(text="✅ Tasdiqlayman"), 
                                        types.KeyboardButton(text="❌ Bekor qilish")]],
                             resize_keyboard=True
                         ))

@router.message(BroadcastState.confirm_send, F.text == "✅ Tasdiqlayman")
async def broadcast_send(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg = data["broadcast_msg"]
    role = data["audience"]
    
    status, d = await get_broadcast_list_api(str(message.from_user.id), role=role)
    if status != 200:
        return await message.answer("❌ Ro'yxatni olishda xatolik yuz berdi.", reply_markup=get_admin_main_kb())

    tg_ids = d.get("tg_ids", [])
    if not tg_ids:
        return await message.answer("ℹ️ Tanlangan guruhda hech kim topilmadi.", reply_markup=get_admin_main_kb())

    sent = 0
    failed = 0
    
    progress_msg = await message.answer(f"🚀 Yuborilmoqda: 0/{len(tg_ids)}...")

    for i, tg_id in enumerate(tg_ids):
        try:
            if msg["content_type"] == "text":
                await bot.send_message(tg_id, msg["text"], entities=msg["entities"])
            elif msg["content_type"] == "photo":
                await bot.send_photo(tg_id, msg["photo"], caption=msg["text"], caption_entities=msg["entities"])
            elif msg["content_type"] == "document":
                await bot.send_document(tg_id, msg["document"], caption=msg["text"], caption_entities=msg["entities"])
            sent += 1
        except Exception:
            failed += 1
        
        # Update progress every 50 messages
        if i % 50 == 0 and i > 0:
            try:
                await progress_msg.edit_text(f"🚀 Yuborilmoqda: {i}/{len(tg_ids)}...")
            except: pass
        
        # Rate limit protection
        await asyncio.sleep(0.05)

    await progress_msg.delete()
    await message.answer(
        f"✅ <b>Yuborish yakunlandi!</b>\n\n"
        f"Muvaffaqiyatli: {sent}\n"
        f"Muvaffaqiyatsiz: {failed}",
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML"
    )
    await state.clear()

@router.message(F.text == "❌ Bekor qilish")
async def broadcast_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Jaraayon bekor qilindi.", reply_markup=get_admin_main_kb())
