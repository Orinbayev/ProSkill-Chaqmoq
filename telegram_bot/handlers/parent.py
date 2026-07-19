import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from keyboards.parent_menu import get_children_selector_keyboard
from services.api_client import get_bot_dashboard_api
from services.profile_context import ensure_active_profile, get_active_profile, set_selected_child
from i18n import t, btn_is, get_lang

router = Router()
logger = logging.getLogger(__name__)


async def _load_parent_dashboard(message: types.Message, state: FSMContext, child_id: int | None = None):
    lang = get_lang(message.from_user.id)
    profile = await ensure_active_profile(message, state, allowed_roles=("parent",))
    if not profile:
        return None

    selected_child_id = child_id or profile.get("child_id")
    status_code, response = await get_bot_dashboard_api(
        str(message.from_user.id), profile["email"], child_id=selected_child_id,
    )
    if status_code != 200 or not response.get("ok"):
        await message.answer(t("generic_error", lang))
        return None
    return response.get("parent", {})


@router.message(btn_is("p_children"))
async def parent_children(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        children = payload.get("children", [])
        if not children:
            await message.answer(t("no_children", lang))
            return
        await set_selected_child(state, payload.get("selected_child_id"))
        await message.answer(
            t("p_children_title", lang),
            reply_markup=get_children_selector_keyboard(children, payload.get("selected_child_id")),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("parent_children failed")
        await message.answer(t("generic_error", lang))


@router.callback_query(F.data.startswith("parent:child:"))
async def parent_select_child(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        child_id = int(callback.data.split(":")[2])
        await set_selected_child(state, child_id)
        profile = await get_active_profile(state)
        status_code, response = await get_bot_dashboard_api(
            str(callback.from_user.id), profile["email"], child_id=child_id,
        )
        if status_code == 200 and response.get("ok"):
            payload = response.get("parent", {})
            await callback.message.edit_text(
                t("p_child_selected", lang, name=payload.get("child", {}).get("full_name", "—")),
                reply_markup=get_children_selector_keyboard(payload.get("children", []), child_id),
                parse_mode="HTML",
            )
            await callback.answer("✅")
            return
        await callback.answer(t("generic_error", lang), show_alert=True)
    except Exception:
        logger.exception("parent_select_child failed")
        await callback.answer(t("generic_error", lang), show_alert=True)


@router.message(btn_is("p_attendance"))
async def parent_attendance(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer(t("pick_child_first", lang))
            return
        a = child.get("attendance", {})
        await message.answer(
            t("p_attendance", lang, name=child.get("full_name"),
              rate=a.get("recent_rate", 0), present=a.get("recent_present", 0), total=a.get("recent_total", 0)),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("parent_attendance failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("p_payment"))
async def parent_payment(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer(t("pick_child_first", lang))
            return
        p = child.get("payment", {})
        await message.answer(
            t("p_payment", lang, name=child.get("full_name"),
              debt=f"{p.get('debt', 0):,}", last=p.get("last_payment_date", "—")),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("parent_payment failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("p_balance"))
async def parent_balance(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer(t("pick_child_first", lang))
            return
        bal = child.get("balance", {})
        rank = bal.get("group_ranking", {})
        await message.answer(
            t("p_balance", lang, name=child.get("full_name"),
              balance=bal.get("current_balance", 0), rank=rank.get("rank_position") or "—"),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("parent_balance failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("p_teacher"))
async def parent_teacher_contact(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_parent_dashboard(message, state)
        if not payload:
            return
        child = payload.get("child")
        if not child:
            await message.answer(t("pick_child_first", lang))
            return
        teacher = child.get("teacher", {})
        await message.answer(
            t("p_teacher", lang, name=child.get("full_name"),
              group=teacher.get("group_name", "—"),
              teacher=teacher.get("teacher_name", "—"),
              phone=teacher.get("teacher_phone") or "—"),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("parent_teacher_contact failed")
        await message.answer(t("generic_error", lang))
