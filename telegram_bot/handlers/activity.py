from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from services.api_client import get_user_details_api

router = Router()

@router.message(F.text == "📜 Faoliyat tarixi")
async def show_activity(message: types.Message, state: FSMContext):
    data = await state.get_data()
    email = data.get("current_user_email")
    status_code, response = await get_user_details_api(str(message.from_user.id), email=email)
    
    if status_code == 200:
        activities = response.get("activities", [])
        if not activities:
            await message.answer("📜 Faoliyat tarixi hali bo'sh.")
            return

        # Show exactly last 15 as requested
        msg_body = ""
        for act in activities[:15]:
            # Example: • 06.03.2026 12:45 — Kirish kodi so'raldi (Windows, IP: 127.0.0.1)
            msg_body += f"• <b>{act['created_at']}</b> — {act['action']} "
            msg_body += f"<i>({act['device']}, IP: {act['ip']})</i>\n"

        msg = f"📜 <b>Oxirgi 15 ta faoliyat tarixi</b>\n\n{msg_body}"
        await message.answer(msg, parse_mode="HTML")
    else:
        await message.answer("❌ Faoliyat tarixini yuklashda xatolik yuz berdi.")
