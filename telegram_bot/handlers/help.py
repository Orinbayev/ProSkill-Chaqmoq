from aiogram import Router, types, F

router = Router()

@router.message(F.text == "ℹ️ Yordam")
async def show_help(message: types.Message):
    msg = (
        "ℹ️ <b>Yordam bo'limi</b>\n\n"
        "Ushbu bot sizning hisobingiz xavfsizligini ta'minlash uchun xizmat qiladi.\n\n"
        "<b>Asosiy buyruqlar:</b>\n"
        "👤 Profil — Hisob ma'lumotlarini ko'rish\n"
        "📜 Faoliyat tarixi — Oxirgi 10 ta amalni ko'rish\n"
        "🔐 Xavfsizlik — Kirish va kod yuborish tarixi\n\n"
        "Agar sizdan boshqa birov hisobingizga kirayotganini bilsangiz, darhol parolingizni o'zgartiring."
    )
    await message.answer(msg, parse_mode="HTML")
