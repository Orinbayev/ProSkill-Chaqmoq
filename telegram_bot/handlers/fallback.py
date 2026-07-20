"""
Asosiy bot uchun "fallback" — hech bir handler ushlamagan matn shu yerga keladi.

Sabab: Telegram reply-klaviaturani keshlaydi. Menyu o'zgargach, foydalanuvchida
ESKI tugmalar qolib ketishi mumkin (masalan eski o'quvchi paneli tugmalari),
ular esa asosiy botда handlersiz — javob bermaydi. Shu handler qaysi tugma
ushlanmasa, foydalanuvchini TO'G'RI menyuга qaytaradi.

MUHIM: bu router bot.py da ENG OXIRIDA ro'yxatga olinadi — shuning uchun barcha
aniq handlerlar (buyruq, tugma matni, state) undan oldin ishlaydi.
"""
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from keyboards.menu import get_main_menu
from services.api_client import get_user_status_api

router = Router()


@router.message(F.text)
async def fallback_unhandled_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("current_user_role")

    if not role:
        status, resp = await get_user_status_api(str(message.from_user.id))
        if status == 200 and (resp or {}).get("status") == "linked":
            users = (resp or {}).get("users") or []
            if users:
                role = users[0].get("role")
                await state.update_data(
                    current_user_email=users[0].get("email"),
                    current_user_role=role,
                    current_user_name=users[0].get("ism"),
                )
        else:
            await message.answer("ℹ️ Hisobingizni ulash uchun /start bosing.")
            return

    note = "ℹ️ Menyu yangilandi. Quyidagi tugmalardan foydalaning 👇"
    if role in ("student", "parent"):
        # O'quvchi/ota-ona paneli alohida "Oila" botда — bu bot asosan profil/xavfsizlik uchun.
        note = (
            "ℹ️ Bu tugma bu botда ishlamaydi.\n"
            "O'quvchi/ota-ona paneli (davomat, to'lov, reyting...) <b>alohida Oila botда</b>.\n\n"
            "Bu yerда profilingizni boshqarasiz 👇"
        )
    await message.answer(note, reply_markup=get_main_menu(role), parse_mode="HTML")
