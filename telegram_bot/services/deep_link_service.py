import logging

from services.api_client import resolve_deep_link_api

logger = logging.getLogger(__name__)


async def render_deep_link(message, telegram_id: str, email: str, param: str):
    status_code, response = await resolve_deep_link_api(telegram_id, email, param)
    if status_code != 200 or not response.get("ok"):
        await message.answer("❌ Deep link ma'lumotini yuklab bo'lmadi.")
        return

    payload = response.get("payload") or {}
    kind = response.get("type")

    if kind == "pay_reminder":
        debt = payload.get("debt", 0)
        last_payment = payload.get("last_payment_date", "—")
        text = (
            "💰 <b>To'lov sahifasi</b>\n\n"
            f"Joriy qarz: <b>{debt:,} so'm</b>\n"
            f"Oxirgi to'lov: <b>{last_payment}</b>"
        )
        await message.answer(text, parse_mode="HTML")
        return

    if kind == "group":
        text = (
            "📚 <b>Guruh ma'lumoti</b>\n\n"
            f"Nomi: <b>{payload.get('name')}</b>\n"
            f"O'qituvchi: <b>{payload.get('teacher_name')}</b>\n"
            f"O'quvchilar soni: <b>{payload.get('student_count')}</b>\n"
            f"Oylik narx: <b>{payload.get('monthly_price'):,} so'm</b>\n"
            f"Haftalik darslar: <b>{payload.get('lessons_per_week')}</b>\n"
            f"Taxminiy tugash: <b>{payload.get('estimated_end_date')}</b>"
        )
        await message.answer(text, parse_mode="HTML")
        return

    if kind == "certificate":
        text = (
            "🎓 <b>Sertifikat ma'lumoti</b>\n\n"
            f"Raqam: <code>{payload.get('certificate_number')}</code>\n"
            f"O'quvchi: <b>{payload.get('student_name')}</b>\n"
            f"Guruh: <b>{payload.get('group_name')}</b>\n"
            f"Berilgan sana: <b>{payload.get('issue_date')}</b>\n"
            f"Holat: <b>{payload.get('status')}</b>"
        )
        await message.answer(text, parse_mode="HTML")
        return

    await message.answer("ℹ️ Deep link bo'yicha maxsus ma'lumot topilmadi.")
