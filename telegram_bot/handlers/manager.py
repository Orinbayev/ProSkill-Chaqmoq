import asyncio
import logging

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from keyboards.manager_menu import get_manager_broadcast_audience_keyboard
from services.api_client import (
    get_bot_dashboard_api,
    get_broadcast_audience_api,
    search_inline_students_api,
)
from services.profile_context import ensure_active_profile, get_active_profile
from states.manager_broadcast_state import ManagerBroadcastState

router = Router()
logger = logging.getLogger(__name__)


async def _load_management_dashboard(message: types.Message, state: FSMContext):
    profile = await ensure_active_profile(message, state, allowed_roles=("manager", "director"))
    if not profile:
        return None
    status_code, response = await get_bot_dashboard_api(str(message.from_user.id), profile["email"])
    if status_code != 200 or not response.get("ok"):
        await message.answer("❌ Menejer ma'lumotlarini yuklab bo'lmadi.")
        return None
    return response.get("management", {})


@router.message(F.text == "📊 Kunlik Hisobot")
async def manager_daily_report(message: types.Message, state: FSMContext):
    try:
        payload = await _load_management_dashboard(message, state)
        if not payload:
            return
        report = payload.get("daily_report", {})
        text = (
            "📊 <b>Kunlik hisobot</b>\n\n"
            f"Bugungi to'lovlar: <b>{report.get('today_payments', 0):,} so'm</b>\n"
            f"To'lovlar soni: <b>{report.get('payment_count', 0)}</b>\n"
            f"Kelganlar soni: <b>{report.get('arrivals_count', 0)}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("manager_daily_report failed")
        await message.answer("❌ Kunlik hisobotni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "⚠️ Xavfli O'quvchilar")
async def manager_risky_students(message: types.Message, state: FSMContext):
    try:
        payload = await _load_management_dashboard(message, state)
        if not payload:
            return
        items = payload.get("risky_students", [])
        if not items:
            await message.answer("✅ Hozircha HIGH risk o'quvchilar yo'q.")
            return
        lines = ["⚠️ <b>HIGH risk o'quvchilar</b>\n"]
        for item in items:
            reasons = ", ".join(item.get("reasons", [])[:2]) or "Sabab yo'q"
            lines.append(
                f"• {item['full_name']}\n"
                f"  Risk: {item['risk_score']}\n"
                f"  Davomat: {item['attendance_percent']}%\n"
                f"  Qarz: {item['debt_amount']:,} so'm\n"
                f"  Sabab: {reasons}"
            )
        await message.answer("\n\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("manager_risky_students failed")
        await message.answer("❌ Xavfli o'quvchilar ro'yxatini ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "👤 Yangi Lidlar")
async def manager_new_leads(message: types.Message, state: FSMContext):
    try:
        payload = await _load_management_dashboard(message, state)
        if not payload:
            return
        leads = payload.get("new_leads", [])
        if not leads:
            await message.answer("ℹ️ Bugun yangi lidlar qo'shilmagan.")
            return
        lines = ["👤 <b>Bugungi yangi lidlar</b>\n"]
        for item in leads:
            lines.append(
                f"• {item['full_name']}\n"
                f"  Telefon: {item['phone']}\n"
                f"  Status: {item['status']}\n"
                f"  Vaqt: {item['created_at']}"
            )
        await message.answer("\n\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("manager_new_leads failed")
        await message.answer("❌ Yangi lidlarni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "💰 Moliyaviy Holat")
async def manager_finance(message: types.Message, state: FSMContext):
    try:
        payload = await _load_management_dashboard(message, state)
        if not payload:
            return
        finance = payload.get("finance", {})
        text = (
            "💰 <b>Moliyaviy holat</b>\n\n"
            f"Joriy oy daromadi: <b>{finance.get('month_revenue', 0):,} so'm</b>\n"
            f"Joriy oy xarajati: <b>{finance.get('month_expense', 0):,} so'm</b>\n"
            f"Farq: <b>{finance.get('difference', 0):,} so'm</b>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("manager_finance failed")
        await message.answer("❌ Moliyaviy holatni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "👥 Xodimlar")
async def manager_staff(message: types.Message, state: FSMContext):
    try:
        payload = await _load_management_dashboard(message, state)
        if not payload:
            return
        staff = payload.get("staff", {})
        text = (
            "👥 <b>Xodimlar</b>\n\n"
            f"O'qituvchilar: <b>{staff.get('teachers_count', 0)}</b>\n"
            f"Managerlar: <b>{staff.get('managers_count', 0)}</b>\n"
            f"Direktorlar: <b>{staff.get('directors_count', 0)}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("manager_staff failed")
        await message.answer("❌ Xodimlar ma'lumotini ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "📣 Xabar Yuborish")
async def manager_broadcast_start(message: types.Message, state: FSMContext):
    try:
        profile = await ensure_active_profile(message, state, allowed_roles=("manager", "director"))
        if not profile:
            return
        await state.set_state(ManagerBroadcastState.waiting_for_audience)
        await message.answer(
            "📣 Kimlarga xabar yubormoqchisiz?",
            reply_markup=get_manager_broadcast_audience_keyboard(),
        )
    except Exception:
        logger.exception("manager_broadcast_start failed")
        await message.answer("❌ Broadcast bo'limini ochishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("manager:broadcast:"))
async def manager_broadcast_audience(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("manager", "director"))
        if not profile:
            return
        audience = callback.data.split(":")[2]
        await state.update_data(manager_broadcast_audience=audience)
        await state.set_state(ManagerBroadcastState.waiting_for_message)
        label = "o'quvchilarga" if audience == "students" else "o'qituvchilarga"
        await callback.message.answer(
            f"📝 Endi {label} yuboriladigan xabarni jo'nating.\n"
            "Matn, rasm yoki hujjat yuborishingiz mumkin."
        )
        await callback.answer()
    except Exception:
        logger.exception("manager_broadcast_audience failed")
        await callback.answer("❌ Auditoriyani tanlab bo'lmadi.", show_alert=True)


@router.message(ManagerBroadcastState.waiting_for_message)
async def manager_broadcast_send(message: types.Message, state: FSMContext, bot: Bot):
    try:
        profile = await ensure_active_profile(message, state, allowed_roles=("manager", "director"))
        if not profile:
            return
        data = await state.get_data()
        audience = data.get("manager_broadcast_audience")
        if audience not in {"students", "teachers"}:
            await state.clear()
            await message.answer("❌ Auditoriya tanlanmagan. Jarayon bekor qilindi.")
            return

        status_code, response = await get_broadcast_audience_api(
            str(message.from_user.id),
            profile["email"],
            audience,
        )
        if status_code != 200 or not response.get("ok"):
            await state.clear()
            await message.answer("❌ Qabul qiluvchilar ro'yxatini olib bo'lmadi.")
            return

        tg_ids = response.get("tg_ids", [])
        if not tg_ids:
            await state.clear()
            await message.answer("ℹ️ Tanlangan auditoriyada botga ulangan foydalanuvchilar yo'q.")
            return

        progress = await message.answer(f"🚀 Yuborilmoqda: 0/{len(tg_ids)}")
        sent = 0
        failed = 0
        for index, tg_id in enumerate(tg_ids, start=1):
            try:
                if message.photo:
                    await bot.send_photo(tg_id, message.photo[-1].file_id, caption=message.caption or "")
                elif message.document:
                    await bot.send_document(tg_id, message.document.file_id, caption=message.caption or "")
                else:
                    await bot.send_message(tg_id, message.text or "")
                sent += 1
            except Exception:
                failed += 1
            if index % 25 == 0 or index == len(tg_ids):
                try:
                    await progress.edit_text(f"🚀 Yuborilmoqda: {index}/{len(tg_ids)}")
                except Exception:
                    pass
            await asyncio.sleep(0.05)

        await state.clear()
        await progress.delete()
        await message.answer(
            f"✅ Broadcast yakunlandi.\nMuvaffaqiyatli: {sent}\nMuvaffaqiyatsiz: {failed}"
        )
    except Exception:
        logger.exception("manager_broadcast_send failed")
        await state.clear()
        await message.answer("❌ Broadcast yuborishda xatolik yuz berdi.")


@router.inline_query()
async def manager_inline_student_search(inline_query: types.InlineQuery):
    query = (inline_query.query or "").strip()
    if not query:
        await inline_query.answer([], cache_time=1, is_personal=True)
        return

    try:
        status_code, response = await search_inline_students_api(str(inline_query.from_user.id), query)
        if status_code != 200 or not response.get("ok"):
            await inline_query.answer([], cache_time=1, is_personal=True)
            return

        results = []
        for item in response.get("items", [])[:10]:
            debt = f"{item['debt']:,} so'm"
            text = (
                f"👤 {item['full_name']}\n"
                f"📚 Guruh: {item['group_name']}\n"
                f"📊 Davomat: {item['attendance_rate']}%\n"
                f"💰 To'lov holati: {debt}"
            )
            results.append(
                InlineQueryResultArticle(
                    id=str(item["id"]),
                    title=item["full_name"],
                    description=f"{item['group_name']} • {item['attendance_rate']}% • {debt}",
                    input_message_content=InputTextMessageContent(message_text=text),
                )
            )

        await inline_query.answer(results, cache_time=1, is_personal=True)
    except Exception:
        logger.exception("manager_inline_student_search failed")
        await inline_query.answer([], cache_time=1, is_personal=True)
