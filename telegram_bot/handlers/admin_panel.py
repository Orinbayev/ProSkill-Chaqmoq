from aiogram import Router, F, types, html
from aiogram.filters import Command
from services.api_client import get_admin_dashboard_api, get_app_adoption_api
from keyboards.admin_menu import get_admin_main_kb

router = Router()

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
