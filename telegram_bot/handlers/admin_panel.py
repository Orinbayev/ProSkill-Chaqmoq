from aiogram import Router, F, types, html
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api_client import (
    get_admin_dashboard_api,
    get_app_adoption_api,
    get_bot_centers_api,
    toggle_bot_center_api,
)
from keyboards.admin_menu import get_admin_main_kb

router = Router()


def _centers_view(data: dict):
    """Markazlar ro'yxati matni + inline toggle klaviaturasi."""
    t = data.get("totals", {})
    lines = [
        "🏢 <b>Markazlar — Telegram bot boshqaruvi</b>\n",
        f"📊 Jami: <b>{t.get('centers', 0)}</b> markaz · <b>{t.get('enabled', 0)}</b> yoqilgan",
        f"👨‍👩‍👧 <b>{t.get('parents', 0)}</b> ota-ona · 🎓 <b>{t.get('students', 0)}</b> o'quvchi\n",
        "<i>Yoqish/o'chirish uchun markaz tugmasini bosing 👇</i>",
    ]
    rows = []
    for c in data.get("centers", [])[:30]:
        dot = "🟢" if c.get("enabled") else "🔴"
        name = str(c.get("name", "—"))
        if len(name) > 22:
            name = name[:21] + "…"
        new_state = 0 if c.get("enabled") else 1
        rows.append([InlineKeyboardButton(
            text=f"{dot} {name} · {c.get('total', 0)}👤",
            callback_data=f"acenter:{c.get('id')}:{new_state}",
        )])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "🏢 Markazlar")
async def admin_centers(message: types.Message):
    status, data = await get_bot_centers_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"):
        return
    text, kb = _centers_view(data)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("acenter:"))
async def admin_center_toggle(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    try:
        center_id = int(parts[1])
        new_state = bool(int(parts[2]))
    except (IndexError, ValueError):
        await callback.answer("Xato", show_alert=True)
        return
    status, resp = await toggle_bot_center_api(str(callback.from_user.id), center_id, new_state)
    if status != 200 or not resp.get("ok"):
        await callback.answer("❌ Bajarilmadi", show_alert=True)
        return
    s2, data = await get_bot_centers_api(str(callback.from_user.id))
    if s2 == 200 and data.get("is_admin"):
        text, kb = _centers_view(data)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    await callback.answer("✅ Yoqildi" if new_state else "⭕️ O'chirildi")

@router.message(Command("admin"))
async def admin_start(message: types.Message):
    """Admin panel main entry."""
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    
    if status != 200 or not data.get("is_admin"):
        # For security, don't even tell them it exists if not admin, or show a polite error
        return # Do nothing for non-admins

    await message.answer(
        "⚡️ <b>ChaqmoqApp — Admin Panel</b>\n\n"
        "Xush kelibsiz! Kerakli bo'limni tanlang:",
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML"
    )

@router.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"): return

    stats = data.get("stats", {})
    roles = stats.get("roles", {})
    
    text = (
        "📊 <b>Umumiy statistika</b>\n\n"
        f"Jami ulangan profillar: <b>{stats.get('total', 0)}</b>\n\n"
        "<b>Rolelar bo‘yicha:</b>\n"
        f"- Ota-ona: {roles.get('parent', 0)}\n"
        f"- Student: {roles.get('student', 0)}\n"
        f"- O‘qituvchi: {roles.get('teacher', 0)}\n"
        f"- Manager: {roles.get('manager', 0)}\n"
        f"- Direktor: {roles.get('director', 0)}\n"
        f"- Superadmin: {roles.get('superadmin', 0)}\n\n"
        f"🗓 <b>Bugun:</b> {stats.get('today', 0)}\n"
        f"📅 <b>Haftada:</b> {stats.get('week', 0)}\n"
        f"🕒 <b>Oyda:</b> {stats.get('month', 0)}"
    )
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📱 Ilova statistikasi")
async def show_app_adoption(message: types.Message):
    """Mobil ilova (ChaqmoqApp) qamrovi — har markazda nechta o'quvchi ishlatyapti."""
    status, data = await get_app_adoption_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"):
        return

    summary = data.get("summary", {})
    centers = data.get("centers", [])

    lines = [
        "📱 <b>Mobil ilova qamrovi — ChaqmoqApp</b>\n",
        f"👥 Ilova foydalanuvchi: <b>{summary.get('app_users', 0)}</b>",
        f"🟢 Faol (30 kun): <b>{summary.get('active_users', 0)}</b>",
        f"📊 O'rtacha qamrov: <b>{summary.get('adoption_pct', 0)}%</b>\n",
        "<b>Markazlar</b> (ko'pdan kamiga):",
    ]

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    shown = [c for c in centers if c.get("app_users", 0) > 0]
    if not shown:
        lines.append("\n<i>Hozircha hech bir markazda ilova foydalanuvchisi yo'q.</i>")
    for i, c in enumerate(shown[:20], start=1):
        prefix = medals.get(i, f"{i}.")
        name = html.quote(str(c.get("name", "—")))
        active = c.get("active_users", 0)
        active_txt = f" · {active} faol" if active else ""
        lines.append(
            f"{prefix} {name} — <b>{c.get('app_users', 0)}</b>/{c.get('total_students', 0)} "
            f"({c.get('adoption_pct', 0)}%){active_txt}"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: types.Message):
    from services.api_client import get_settings_api
    status, data = await get_settings_api(str(message.from_user.id))
    if status != 200: return

    report_time = data.get("parent_report_time", "20:00")
    
    text = (
        "⚙️ <b>Tizim sozlamalari</b>\n\n"
        f"Ota-onalarga kunlik hisobot vaqti: <b>{report_time}</b>\n\n"
        "Vaqtni o'zgartirish uchun yangi vaqtni formatda yuboring (masalan: <code>19:30</code>)."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🏠 Asosiy menyu")
async def back_to_main(message: types.Message):
    from keyboards.menu import get_main_menu
    await message.answer("🏠 Asosiy menyuga qaytdingiz.", reply_markup=get_main_menu())

@router.message(F.text == "📁 Excel yuklab olish")
async def export_excel(message: types.Message):
    from services.api_client import download_excel_api
    from aiogram.types import BufferedInputFile
    
    await message.answer("🔄 Excel fayl tayyorlanmoqda, iltimos kuting...")
    
    status, content = await download_excel_api(str(message.from_user.id))
    if status == 200 and content:
        file = BufferedInputFile(content, filename="linked_users.xlsx")
        await message.answer_document(file, caption="✅ Barcha ulangan profillar ro'yxati (Excel)")
    else:
        await message.answer("❌ Excel yuklashda xatolik yuz berdi.")
