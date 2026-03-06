from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from services.api_client import get_user_details_api

router = Router()

@router.message(F.text == "🔐 Xavfsizlik")
async def show_security(message: types.Message, state: FSMContext):
    data = await state.get_data()
    email = data.get("current_user_email")
    status_code, response = await get_user_details_api(str(message.from_user.id), email=email)
    
    if status_code == 200:
        activities = response.get("activities", [])
        
        # Categorize
        # Note: sorting in API is newer first.
        logins = [a for a in activities if "Login successful" in a['raw_action']]
        failures = [a for a in activities if "Failed login" in a['raw_action']]
        audit = [a for a in activities if any(k in a['raw_action'].lower() for k in ["code", "password", "linked"])]
        
        msg = "🔐 <b>Xavfsizlik bo'limi</b>\n\n"
        
        # 🔓 Last Success
        if logins:
            msg += "🔓 <b>Oxirgi muvaffaqiyatli kirishlar:</b>\n"
            for l in logins[:3]:
                # Format: 📅 06.03.2026 12:45 (Windows, IP: 84.54..)
                msg += f"  - 📅 {l['created_at']} (<i>{l['device']}, IP: {l['ip']}</i>)\n"
        
        # 🛑 Recent Failures
        if failures:
            msg += "\n🛑 <b>Muvaffaqiyatsiz urinishlar:</b>\n"
            for f in failures[:3]:
                msg += f"  - 📅 {f['created_at']} (<i>{f['device']}</i>)\n"
        
        # 🛡️ Audit
        if audit:
            msg += "\n🛡️ <b>Tizim auditi:</b>\n"
            for a in audit[:5]:
                msg += f"  - 📅 {a['created_at']} — {a['action']}\n"
        
        if not (logins or failures or audit):
            msg += "Xavfsizlik tarixi hali mavjud emas."
            
        await message.answer(msg, parse_mode="HTML")
    else:
        await message.answer("❌ Xavfsizlik ma'lumotlarini yuklashda xatolik yuz berdi.")
