import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from keyboards.parent_menu import get_children_selector_keyboard
from services.api_client import get_bot_dashboard_api
from services.profile_context import ensure_active_profile, get_active_profile, set_selected_child

router = Router()
logger = logging.getLogger(__name__)


async def _load_parent_dashboard(message: types.Message, state: FSMContext, child_id: int | None = None):
    profile = await ensure_active_profile(message, state, allowed_roles=("parent",))
    if not profile:
        return None

    selected_child_id = child_id or profile.get("child_id")
    status_code, response = await get_bot_dashboard_api(
        str(message.from_user.id),
        profile["email"],
        child_id=selected_child_id,
    )
    if status_code != 200 or not response.get("ok"):
        await message.answer("❌ Ota-ona ma'lumotlarini yuklab bo'lmadi.")
        return None
    return response.get("parent", {})


def _selected_child_text(parent_payload: dict):
    child = parent_payload.get("child")
    if not child:
        return "Tanlangan bola yo'q."
    return f"Tanlangan bola: <b>{child.get('full_name')}</b>"


@router.message(F.text == "👶 Bolalarim")
async def parent_children(message: types.Message, state: FSMContext):
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        children = payload.get("children", [])
        if not children:
            await message.answer("ℹ️ Sizga bog'langan bolalar topilmadi.")
            return
        await set_selected_child(state, payload.get("selected_child_id"))
        text = (
            "👶 <b>Bolalarim</b>\n\n"
            f"{_selected_child_text(payload)}\n"
            "Kerakli bolani tanlang."
        )
        await message.answer(
            text,
            reply_markup=get_children_selector_keyboard(children, payload.get("selected_child_id")),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("parent_children failed")
        await message.answer("❌ Bolalar ro'yxatini ko'rsatishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("parent:child:"))
async def parent_select_child(callback: types.CallbackQuery, state: FSMContext):
    try:
        child_id = int(callback.data.split(":")[2])
        await set_selected_child(state, child_id)
        profile = await get_active_profile(state)
        status_code, response = await get_bot_dashboard_api(
            str(callback.from_user.id),
            profile["email"],
            child_id=child_id,
        )
        if status_code == 200 and response.get("ok"):
            payload = response.get("parent", {})
            await callback.message.edit_text(
                f"✅ <b>{payload.get('child', {}).get('full_name', 'Bola')}</b> tanlandi.",
                reply_markup=get_children_selector_keyboard(payload.get("children", []), child_id),
                parse_mode="HTML",
            )
            await callback.answer("Bola tanlandi.")
            return
        await callback.answer("❌ Bolani tanlab bo'lmadi.", show_alert=True)
    except Exception:
        logger.exception("parent_select_child failed")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)


@router.message(F.text == "📊 Davomat")
async def parent_attendance(message: types.Message, state: FSMContext):
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer("ℹ️ Avval bolani tanlang.")
            return
        attendance = child.get("attendance", {})
        items = "\n".join(
            f"• {item['date']} — {item['status_label']} ({item['group_name']})"
            for item in attendance.get("items", [])[:10]
        ) or "Davomat yozuvlari topilmadi."
        text = (
            f"📊 <b>{child.get('full_name')} uchun davomat</b>\n\n"
            f"So'nggi 30 kun: <b>{attendance.get('recent_rate', 0)}%</b>\n"
            f"Kelgan darslar: <b>{attendance.get('recent_present', 0)}/{attendance.get('recent_total', 0)}</b>\n\n"
            "<b>Oxirgi yozuvlar:</b>\n"
            f"{items}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("parent_attendance failed")
        await message.answer("❌ Davomatni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "💰 To'lov Holati")
async def parent_payment(message: types.Message, state: FSMContext):
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer("ℹ️ Avval bolani tanlang.")
            return
        payment = child.get("payment", {})
        recent = "\n".join(
            f"• {item['paid_date']} — {item['amount']:,} so'm ({item['group_name']})"
            for item in payment.get("recent_payments", [])[:5]
        ) or "To'lov tarixi topilmadi."
        text = (
            f"💰 <b>{child.get('full_name')} uchun to'lov holati</b>\n\n"
            f"Qarz: <b>{payment.get('debt', 0):,} so'm</b>\n"
            f"Oxirgi to'lov: <b>{payment.get('last_payment_date', '—')}</b>\n\n"
            "<b>Tarix:</b>\n"
            f"{recent}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("parent_payment failed")
        await message.answer("❌ To'lov ma'lumotini ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "⚡ Chaqmoq Ballari")
async def parent_balance(message: types.Message, state: FSMContext):
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer("ℹ️ Avval bolani tanlang.")
            return
        balance = child.get("balance", {})
        ranking = balance.get("group_ranking", {})
        text = (
            f"⚡ <b>{child.get('full_name')} uchun chaqmoq</b>\n\n"
            f"Joriy balans: <b>{balance.get('current_balance', 0)}</b>\n"
            f"Guruh: <b>{ranking.get('group_name', '—')}</b>\n"
            f"Reytingdagi o'rni: <b>{ranking.get('rank_position') or '—'}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("parent_balance failed")
        await message.answer("❌ Chaqmoq ma'lumotini ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "📞 O'qituvchi")
async def parent_teacher_contact(message: types.Message, state: FSMContext):
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer("ℹ️ Avval bolani tanlang.")
            return
        teacher = child.get("teacher", {})
        text = (
            f"📞 <b>{child.get('full_name')} uchun o'qituvchi</b>\n\n"
            f"Guruh: <b>{teacher.get('group_name', '—')}</b>\n"
            f"O'qituvchi: <b>{teacher.get('teacher_name', 'Belgilanmagan')}</b>\n"
            f"Telefon: <code>{teacher.get('teacher_phone') or 'Mavjud emas'}</code>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("parent_teacher_contact failed")
        await message.answer("❌ O'qituvchi ma'lumotini ko'rsatishda xatolik yuz berdi.")
