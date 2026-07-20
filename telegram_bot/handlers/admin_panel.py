from aiogram import Router, F, types, html
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api_client import (
    get_admin_dashboard_api,
    get_app_adoption_api,
    get_bot_centers_api,
    toggle_bot_center_api,
    get_bot_center_detail_api,
    get_bot_finance_api,
)
from keyboards.admin_menu import get_admin_main_kb

router = Router()


def _fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


def _centers_list_view(data: dict):
    """Markazlar ro'yxati — har biri detail'ga ochiladi."""
    t = data.get("totals", {})
    lines = [
        "🏢 <b>Markazlar</b>\n",
        f"📊 {t.get('centers', 0)} markaz · {t.get('enabled', 0)} bot yoqilgan",
        f"👨‍👩‍👧 {t.get('parents', 0)} ota-ona · 🎓 {t.get('students', 0)} o'quvchi (botда)\n",
        "<i>Batafsil ma'lumot uchun markazni tanlang 👇</i>",
    ]
    rows = []
    for c in data.get("centers", [])[:40]:
        dot = "🟢" if c.get("enabled") else "🔴"
        name = str(c.get("name", "—"))
        if len(name) > 25:
            name = name[:24] + "…"
        rows.append([InlineKeyboardButton(text=f"{dot} {name}", callback_data=f"acenter:detail:{c.get('id')}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _center_detail_view(c: dict):
    """Bitta markaz — to'liq statistika + toggle + orqaga."""
    status = "🟢 Yoqilgan" if c.get("enabled") else "🔴 O'chirilgan"
    lines = [
        f"🏢 <b>{html.quote(str(c.get('name', '—')))}</b>",
        f"🤖 Bot: <b>{status}</b>\n",
        f"🎓 O'quvchilar: <b>{c.get('students', 0)}</b>",
        f"👨‍🏫 Ustozlar: <b>{c.get('teachers', 0)}</b>",
        f"📚 Guruhlar: <b>{c.get('groups', 0)}</b>\n",
        f"📥 Bu oy daromad: <b>{_fmt(c.get('revenue', 0))} so'm</b>",
        f"📤 Bu oy xarajat: <b>{_fmt(c.get('expense', 0))} so'm</b>",
        f"📈 Sof foyda: <b>{_fmt(c.get('net', 0))} so'm</b>",
        f"🔴 Qarzdorlik: <b>{_fmt(c.get('debt', 0))} so'm</b> ({c.get('debtors', 0)} ta)\n",
        f"📱 Botда: {c.get('bot_parents', 0)} ota-ona · {c.get('bot_students', 0)} o'quvchi",
    ]
    new_state = 0 if c.get("enabled") else 1
    toggle_txt = "🔴 Botni o'chirish" if c.get("enabled") else "🟢 Botni yoqish"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_txt, callback_data=f"acenter:toggle:{c.get('id')}:{new_state}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="acenter:list")],
    ])
    return "\n".join(lines), kb


@router.message(F.text == "🏢 Markazlar")
async def admin_centers(message: types.Message):
    status, data = await get_bot_centers_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"):
        return
    text, kb = _centers_list_view(data)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "acenter:list")
async def admin_centers_list_cb(callback: types.CallbackQuery):
    status, data = await get_bot_centers_api(str(callback.from_user.id))
    if status != 200 or not data.get("is_admin"):
        await callback.answer()
        return
    text, kb = _centers_list_view(data)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("acenter:detail:"))
async def admin_center_detail_cb(callback: types.CallbackQuery):
    try:
        cid = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Xato", show_alert=True)
        return
    status, data = await get_bot_center_detail_api(str(callback.from_user.id), cid)
    if status != 200 or not data.get("ok"):
        await callback.answer("❌ Ma'lumot topilmadi", show_alert=True)
        return
    text, kb = _center_detail_view(data["center"])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("acenter:toggle:"))
async def admin_center_toggle_cb(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    try:
        cid = int(parts[2])
        new_state = bool(int(parts[3]))
    except (IndexError, ValueError):
        await callback.answer("Xato", show_alert=True)
        return
    st, resp = await toggle_bot_center_api(str(callback.from_user.id), cid, new_state)
    if st != 200 or not resp.get("ok"):
        await callback.answer("❌ Bajarilmadi", show_alert=True)
        return
    s2, data = await get_bot_center_detail_api(str(callback.from_user.id), cid)
    if s2 == 200 and data.get("ok"):
        text, kb = _center_detail_view(data["center"])
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    await callback.answer("✅ Yoqildi" if new_state else "⭕️ O'chirildi")


@router.message(F.text == "💰 Moliyaviy")
async def admin_finance(message: types.Message):
    status, data = await get_bot_finance_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"):
        return
    t = data.get("totals", {})
    lines = [
        "💰 <b>Moliyaviy hisobot — joriy oy</b>",
        "<i>(barcha markazlar bo'yicha)</i>\n",
        f"📥 Daromad: <b>{_fmt(t.get('revenue', 0))} so'm</b>",
        f"📤 Xarajat: <b>{_fmt(t.get('expense', 0))} so'm</b>",
        f"📈 Sof foyda: <b>{_fmt(t.get('net', 0))} so'm</b>\n",
        "<b>Markazlar (foydaga ko'ra):</b>",
    ]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    centers = data.get("centers", [])
    if not centers:
        lines.append("<i>Ma'lumot yo'q.</i>")
    for i, c in enumerate(centers[:15]):
        pre = medals.get(i, f"{i + 1}.")
        name = html.quote(str(c.get("name", "—")))
        lines.append(
            f"{pre} {name} — <b>{_fmt(c.get('net', 0))}</b> "
            f"(D:{_fmt(c.get('revenue', 0))} / X:{_fmt(c.get('expense', 0))})"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")

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
