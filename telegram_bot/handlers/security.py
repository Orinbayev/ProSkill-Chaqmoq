from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from services.api_client import get_user_details_api

router = Router()


@router.message(F.text == "🔐 Xavfsizlik")
async def show_security(message: types.Message, state: FSMContext):
    """Xavfsizlik + faoliyat — yagona professional ko'rinish.
    (Oldingi '📜 Faoliyat tarixi' shu yerга birlashtirildi.)"""
    data = await state.get_data()
    email = data.get("current_user_email")
    status_code, response = await get_user_details_api(str(message.from_user.id), email=email)

    if status_code != 200:
        await message.answer("❌ Ma'lumotni yuklashda xatolik yuz berdi.")
        return

    activities = response.get("activities", [])
    logins = [a for a in activities if "Login successful" in a["raw_action"]]
    failures = [a for a in activities if "Failed login" in a["raw_action"]]

    parts = ["🔐 <b>Xavfsizlik va faoliyat</b>\n"]

    if logins:
        parts.append("🔓 <b>Oxirgi kirishlar:</b>")
        for l in logins[:3]:
            parts.append(f"  • {l['created_at']} <i>({l['device']}, IP: {l['ip']})</i>")
        parts.append("")

    if failures:
        parts.append("🛑 <b>Muvaffaqiyatsiz urinishlar:</b>")
        for f in failures[:3]:
            parts.append(f"  • {f['created_at']} <i>({f['device']})</i>")
        parts.append("")

    if activities:
        parts.append("📜 <b>So'nggi faoliyat:</b>")
        for a in activities[:8]:
            parts.append(f"  • {a['created_at']} — {a['action']}")
    else:
        parts.append("Faoliyat tarixi hali bo'sh.")

    parts.append("\n<i>Shubhali harakat sezsangiz, parolingizni darhol o'zgartiring.</i>")
    await message.answer("\n".join(parts), parse_mode="HTML")
