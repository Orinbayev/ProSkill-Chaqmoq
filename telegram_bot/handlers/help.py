from aiogram import Router, types, F

router = Router()

@router.message(F.text == "ℹ️ Yordam")
async def show_help(message: types.Message):
    msg = (
        "ℹ️ <b>Yordam</b>\n\n"
        "Bu bot hisobingiz xavfsizligi va profilingizni boshqarish uchun.\n\n"
        "👤 <b>Profil</b> — profilingizni ko'rish; bir nechta profil bo'lsa, shu yerдан almashtirasiz.\n"
        "🔐 <b>Xavfsizlik</b> — kirishlar, urinishlar va so'nggi faoliyat bir joyда.\n"
        "🚪 <b>Chiqish</b> — profilni botдан uzish.\n\n"
        "🔑 Parolni unutsangiz — saytдаgi \"Parolni unutdingizmi?\" orqali shu botга kod keladi.\n\n"
        "Shubhali harakat sezsangiz, parolingizni darhol o'zgartiring."
    )
    await message.answer(msg, parse_mode="HTML")
