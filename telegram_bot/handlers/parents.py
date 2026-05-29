from aiogram import Bot, Router, F, types, html
from services.api_client import get_admin_dashboard_api, get_parent_reports_api
from keyboards.admin_menu import get_admin_main_kb

router = Router()

@router.message(F.text == "👨👩👧 Ota-onalar paneli")
async def parent_panel(message: types.Message):
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"):
        await message.answer("❌ Bu bo'lim faqat adminlar uchun.")
        return

    text = (
        "👨👩👧 <b>Ota-onalar paneli</b>\n\n"
        "Ushbu bo'limda ota-onalarga farzandlari bo'yicha kunlik hisobotlarni boshqarishingiz mumkin.\n\n"
        "🔹 Hisobot vaqti <b>Sozlamalar</b> bo'limidan o'zgartiriladi.\n"
        "🔹 Hisobotlar avtomatik yuboriladi.\n\n"
        "Hozirda barcha ota-onalarga bugungi hisobotni yubormoqchimisiz?"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 Hozir yuborish", callback_data="send_reports_now")],
    ])
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "send_reports_now")
async def send_reports_now(callback: types.CallbackQuery, bot: Bot):
    # Check admin
    status, data = await get_admin_dashboard_api(str(callback.from_user.id))
    if status != 200 or not data.get("is_admin"):
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return

    await callback.message.edit_text("🔄 Hisobotlar tayyorlanmoqda...")
    
    from services.api_client import get_parent_reports_api
    s, d = await get_parent_reports_api()
    if s != 200:
        return await callback.message.answer("❌ Ma'lumotlarni olishda xatolik.")

    reports = d.get("reports", {})
    if not reports:
        return await callback.message.answer("ℹ️ Bugun hech qanday chaqmoq qayd etilmadi, hisobot yuborilmadi.")

    sent = 0
    for tg_id, children in reports.items():
        text = "📘 <b>Farzandingiz bo‘yicha kunlik hisobot</b>\n\n"
        
        for student in children:
            student_name = html.quote(student['name'])
            text += f"👦 <b>O‘quvchi:</b> {student_name}\n"
            text += f"📅 Sana: {timezone_now_str()}\n\n"
            text += f"✅ Bugun qo‘shilgan: <b>{student['total_today_plus']}</b>\n"
            text += f"❌ Bugun ayrilgan: <b>{student['total_today_minus']}</b>\n"
            text += f"⚡ Joriy jami chaqmoq: <b>{student['current_total']}</b>\n\n"
            
            if student['added']:
                text += "<b>Qo‘shilganlar:</b>\n"
                for pair in student['added']:
                    reason = html.quote(pair['reason'])
                    by = html.quote(pair['by'])
                    text += f"- {pair['ball']} ta — {reason} — {by}\n"
            
            if student['removed']:
                text += "\n<b>Ayrilganlar:</b>\n"
                for pair in student['removed']:
                    reason = html.quote(pair['reason'])
                    by = html.quote(pair['by'])
                    text += f"- {pair['ball']} ta — {reason} — {by}\n"
            
            text += "\n" + "—" * 15 + "\n\n"

        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except:
            pass
        
    await callback.message.answer(f"✅ {sent} ta ota-onaga hisobot yuborildi.")
    await callback.answer()

def timezone_now_str():
    from datetime import datetime
    import pytz
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime("%Y-%m-%d")
