from aiogram import Router, F, types
from services.api_client import get_admin_dashboard_api, update_settings_api
import re

router = Router()

@router.message(F.text.regexp(r"^\d{2}:\d{2}$"))
async def update_time_setting(message: types.Message):
    """Handle HH:MM text for time updates."""
    # Check if admin
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"): return

    new_time = message.text
    # Basic validation
    h, m = map(int, new_time.split(":"))
    if h > 23 or m > 59:
        return await message.answer("❌ Noto'g'ri vaqt formati. (00:00 - 23:59)")

    s, d = await update_settings_api(str(message.from_user.id), {"parent_report_time": new_time})
    
    if s == 200:
        await message.answer(f"✅ Hisobot vaqti muvaffaqiyatli o'zgartirildi: **{new_time}**", 
                             parse_mode="Markdown")
    else:
        await message.answer(f"❌ Xatolik: {d.get('error')}")
