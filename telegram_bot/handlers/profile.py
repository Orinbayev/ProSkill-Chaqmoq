from aiogram import Router, types, F
from services.api_client import get_user_details_api

router = Router()

@router.message(F.text == "👤 Profil")
async def show_profile(message: types.Message):
    status_code, response = await get_user_details_api(str(message.from_user.id))
    
    if status_code == 200:
        profile = response.get("profile", {})
        username = message.from_user.username or "mavjud emas"
        msg = (
            f"👤 <b>Profil ma'lumotlari</b>\n\n"
            f"Telefon: <code>{profile.get('phone')}</code>\n"
            f"Rol: {profile.get('role')}\n"
            f"Bog'langan sana: {profile.get('linked_at')}\n\n"
            f"Telegram ID: <code>{message.from_user.id}</code>\n"
            f"Username: @{username}"
        )
        await message.answer(msg, parse_mode="HTML")
    else:
        await message.answer("❌ Profil ma'lumotlarini yuklashda xatolik yuz berdi.")
