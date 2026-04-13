import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from keyboards.student_menu import get_store_products_keyboard, get_student_settings_keyboard
from services.api_client import (
    create_purchase_request_api,
    get_bot_dashboard_api,
    update_notification_settings_api,
)
from services.profile_context import ensure_active_profile

router = Router()
logger = logging.getLogger(__name__)


async def _load_student_dashboard(message: types.Message, state: FSMContext):
    profile = await ensure_active_profile(message, state, allowed_roles=("student",))
    if not profile:
        return None

    status_code, response = await get_bot_dashboard_api(str(message.from_user.id), profile["email"])
    if status_code != 200 or not response.get("ok"):
        await message.answer("❌ O'quvchi ma'lumotlarini yuklab bo'lmadi.")
        return None
    return response.get("student", {})


def _format_top5(items: list[dict], my_position: int | None):
    if not items:
        return "Reyting hozircha shakllanmagan."
    lines = []
    for item in items:
        prefix = "👉 " if my_position and item.get("position") == my_position else ""
        score = item.get("score")
        if isinstance(score, float):
            score_text = f"{score:.1f}"
        else:
            score_text = str(score)
        lines.append(f"{prefix}{item['position']}. {item['full_name']} — {score_text}")
    return "\n".join(lines)


@router.message(F.text == "📊 Mening holatim")
async def student_status(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        status = payload.get("status", {})
        groups = ", ".join(status.get("active_groups", [])) or "Faol guruh yo'q"
        text = (
            "📊 <b>Mening holatim</b>\n\n"
            f"Davomat: <b>{status.get('attendance_rate', 0)}%</b>\n"
            f"Kelgan darslar: <b>{status.get('present_lessons', 0)}/{status.get('total_lessons', 0)}</b>\n"
            f"Qarz: <b>{status.get('debt', 0):,} so'm</b>\n"
            f"Faol guruhlar: <b>{groups}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("student_status failed")
        await message.answer("❌ Holatni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "⚡ Chaqmoq Balans")
async def student_balance(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        balance = payload.get("balance", {})
        ranking = balance.get("group_ranking", {})
        text = (
            "⚡ <b>Chaqmoq Balans</b>\n\n"
            f"Joriy balans: <b>{balance.get('current_balance', 0)}</b>\n"
            f"Guruh: <b>{ranking.get('group_name', '—')}</b>\n"
            f"Reytingdagi o'rningiz: <b>{ranking.get('rank_position') or '—'}</b> / {ranking.get('total_students', 0)}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("student_balance failed")
        await message.answer("❌ Balansni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "📅 Dars Jadvali")
async def student_schedule(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        schedule = payload.get("schedule", [])
        if not schedule:
            await message.answer("ℹ️ Siz uchun faol dars jadvali topilmadi.")
            return

        lines = ["📅 <b>Shu haftadagi darslar</b>\n"]
        for item in schedule:
            lines.append(
                f"• <b>{item['group_name']}</b>\n"
                f"  O'qituvchi: {item['teacher_name']}\n"
                f"  Jadval: {item['weekday_label']}\n"
                f"  Vaqt: {item['time_label']}"
            )
        await message.answer("\n\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("student_schedule failed")
        await message.answer("❌ Jadvalni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "💰 To'lov Holati")
async def student_payment(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        payment = payload.get("payment", {})
        recent = payment.get("recent_payments", [])
        history = "\n".join(
            f"• {item['paid_date']} — {item['amount']:,} so'm ({item['group_name']})"
            for item in recent[:5]
        ) or "To'lov tarixi topilmadi."
        text = (
            "💰 <b>To'lov holati</b>\n\n"
            f"Joriy qarz: <b>{payment.get('debt', 0):,} so'm</b>\n"
            f"Oxirgi to'lov: <b>{payment.get('last_payment_date', '—')}</b>\n\n"
            "<b>Oxirgi to'lovlar:</b>\n"
            f"{history}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("student_payment failed")
        await message.answer("❌ To'lov holatini ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "🏆 Reyting")
async def student_ranking(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        ranking = payload.get("ranking", {})
        text = (
            "🏆 <b>Guruh reytingi</b>\n\n"
            f"Guruh: <b>{ranking.get('group_name', '—')}</b>\n"
            f"Sizning o'rningiz: <b>{ranking.get('rank_position') or '—'}</b>\n\n"
            f"{_format_top5(ranking.get('top5', []), ranking.get('rank_position'))}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("student_ranking failed")
        await message.answer("❌ Reytingni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "🛍 Do'kon")
async def student_store(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        store = payload.get("store", {})
        products = store.get("products", [])
        requests = store.get("purchase_requests", [])
        if not products:
            await message.answer("ℹ️ Hozircha do'konda mahsulotlar yo'q.")
            return

        recent_requests = "\n".join(
            f"• {item['product_name']} ×{item['qty']} — {item['status']}"
            for item in requests[:5]
        ) or "So'rovlar yo'q."
        text = (
            "🛍 <b>Do'kon</b>\n\n"
            "Mahsulotni tanlasangiz, xarid so'rovi yuboriladi.\n\n"
            "<b>So'nggi so'rovlar:</b>\n"
            f"{recent_requests}"
        )
        await message.answer(text, reply_markup=get_store_products_keyboard(products), parse_mode="HTML")
    except Exception:
        logger.exception("student_store failed")
        await message.answer("❌ Do'konni ko'rsatishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("student:buy:"))
async def student_buy_product(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        product_id = int(callback.data.split(":")[2])
        status_code, response = await create_purchase_request_api(
            str(callback.from_user.id),
            profile["email"],
            product_id,
            qty=1,
        )
        if status_code == 201:
            await callback.answer("✅ Xarid so'rovi yuborildi.", show_alert=True)
        else:
            await callback.answer(response.get("error", "Xatolik yuz berdi."), show_alert=True)
    except Exception:
        logger.exception("student_buy_product failed")
        await callback.answer("❌ Xarid so'rovini yuborib bo'lmadi.", show_alert=True)


@router.message(F.text == "🔔 Sozlamalar")
async def student_settings(message: types.Message, state: FSMContext):
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        settings = payload.get("settings", {})
        enabled = bool(settings.get("notifications_enabled"))
        status_label = "Yoqilgan" if enabled else "O'chirilgan"
        text = (
            "🔔 <b>Sozlamalar</b>\n\n"
            f"Bildirishnomalar: <b>{status_label}</b>\n"
            "Quyidagi tugma orqali holatni o'zgartirishingiz mumkin."
        )
        await message.answer(text, reply_markup=get_student_settings_keyboard(enabled), parse_mode="HTML")
    except Exception:
        logger.exception("student_settings failed")
        await message.answer("❌ Sozlamalarni ochishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("student:notifications:"))
async def student_toggle_notifications(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        enabled = bool(int(callback.data.split(":")[2]))
        status_code, response = await update_notification_settings_api(
            str(callback.from_user.id),
            profile["email"],
            enabled,
        )
        if status_code == 200 and response.get("ok"):
            label = "yoqildi" if enabled else "o'chirildi"
            await callback.answer(f"✅ Bildirishnomalar {label}.", show_alert=True)
        else:
            await callback.answer(response.get("error", "Xatolik yuz berdi."), show_alert=True)
    except Exception:
        logger.exception("student_toggle_notifications failed")
        await callback.answer("❌ Sozlama saqlanmadi.", show_alert=True)
