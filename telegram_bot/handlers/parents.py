from aiogram import Router, F, types
from services.api_client import get_admin_dashboard_api, get_parent_reports_api
from keyboards.admin_menu import get_admin_main_kb

router = Router()

@router.message(F.text == "👨👩👧 Ota-onalar paneli")
async def parent_panel(message: types.Message):
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"): return

    text = (
        "👨👩👧 **Ota-onalar paneli**\n\n"
        "Ushbu bo'limda ota-onalarga farzandlari bo'yicha kunlik hisobotlarni boshqarishingiz mumkin.\n\n"
        "🔹 Hisobot vaqti **Sozlamalar** bo'limidan o'zgartiriladi.\n"
        "🔹 Hisobotlar avtomatik yuboriladi.\n\n"
        "Hozirda barcha ota-onalarga bugungi hisobotni yubormoqchimisiz?"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 Hozir yuborish", callback_data="send_reports_now")],
    ])
    
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "send_reports_now")
async def send_reports_now(callback: types.CallbackQuery, bot):
    # Check admin
    status, data = await get_admin_dashboard_api(str(callback.from_user.id))
    if status != 200 or not data.get("is_admin"): return

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
        text = "📘 **Farzandingiz bo‘yicha kunlik hisobot**\n\n"
        
        for student in children:
            text += f"👦 **O‘quvchi:** {student['name']}\n"
            text += f"📅 Sana: {timezone_now_str()}\n\n"
            text += f"✅ Bugun qo‘shilgan: **{student['total_today_plus']}**\n"
            text += f"❌ Bugun ayrilgan: **{student['total_today_minus']}**\n"
            text += f"⚡ Joriy jami chaqmoq: **{student['current_total']}**\n\n"
            
            if student['added']:
                text += "**Qo‘shilganlar:**\n"
                for pair in student['added']:
                    text += f"- {pair['ball']} ta — {pair['reason']} — {pair['by']}\n"
            
            if student['removed']:
                text += "\n**Ayrilganlar:**\n"
                for pair in student['removed']:
                    text += f"- {pair['ball']} ta — {pair['reason']} — {pair['by']}\n"
            
            text += "\n" + "—" * 15 + "\n\n"

        try:
            await bot.send_message(tg_id, text, parse_mode="Markdown")
            sent += 1
        except:
            pass
        
    await callback.message.answer(f"✅ {sent} ta ota-onaga hisobot yuborildi.")

def timezone_now_str():
    from datetime import datetime
    import pytz
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime("%Y-%m-%d")
