from aiogram import Router, F, types
from services.api_client import get_linked_users_api, get_admin_dashboard_api

router = Router()

@router.message(F.text == "👥 Ulangan profillar")
async def linked_users_menu(message: types.Message):
    # Check admin
    status, data = await get_admin_dashboard_api(str(message.from_user.id))
    if status != 200 or not data.get("is_admin"): return

    # Get first page
    s, d = await get_linked_users_api(str(message.from_user.id), limit=15)
    if s != 200:
        return await message.answer("❌ Ma'lumotlarni yuklashda xatolik.")

    users = d.get("users", [])
    total = d.get("total", 0)

    if not users:
        return await message.answer("ℹ️ Hozircha hech qanday profil ulanmagan.")

    text = f"👥 **Ulangan profillar ({total} ta)**\n\n"
    for i, u in enumerate(users, 1):
        text += f"{i}. {u['full_name']} — *{u['role']}*\n"
        text += f"   📞 {u['phone']} | 🆔 {u['tg_id']}\n"
        text += f"   📅 {u['linked_at']}\n\n"

    if total > 15:
        text += f"ℹ️ Faqat oxirgi 15 ta ko'rsatildi. To'liq ro'yxatni Excel orqali yuklab oling."

    await message.answer(text, parse_mode="Markdown")
