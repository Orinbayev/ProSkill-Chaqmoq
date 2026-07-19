import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.student_menu import get_store_products_keyboard, get_student_settings_keyboard
from services.api_client import (
    create_purchase_request_api,
    get_bot_dashboard_api,
    update_notification_settings_api,
)
from services.profile_context import ensure_active_profile
from i18n import t, ik, btn_is, get_lang, render_payment

router = Router()
logger = logging.getLogger(__name__)


async def _load_student_dashboard(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    profile = await ensure_active_profile(message, state, allowed_roles=("student",))
    if not profile:
        return None

    status_code, response = await get_bot_dashboard_api(str(message.from_user.id), profile["email"])
    if status_code != 200 or not response.get("ok"):
        await message.answer(t("generic_error", lang))
        return None
    return response.get("student", {})


def _format_top5(items: list[dict], my_position: int | None) -> str:
    lines = []
    for item in items:
        prefix = "👉 " if my_position and item.get("position") == my_position else ""
        score = item.get("score")
        score_text = f"{score:.1f}" if isinstance(score, float) else str(score)
        lines.append(f"{prefix}{item['position']}. {item['full_name']} — {score_text}")
    return "\n".join(lines)


@router.message(btn_is("s_status"))
async def student_status(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        s = payload.get("status", {})
        await message.answer(
            t("s_status", lang, rate=s.get("attendance_rate", 0),
              present=s.get("present_lessons", 0), total=s.get("total_lessons", 0),
              debt=f"{s.get('debt', 0):,}"),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("student_status failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("s_balance"))
async def student_balance(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        bal = payload.get("balance", {})
        rank = bal.get("group_ranking", {})
        await message.answer(
            t("s_balance", lang, balance=bal.get("current_balance", 0),
              rank=rank.get("rank_position") or "—", total=rank.get("total_students", 0)),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("student_balance failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("s_schedule"))
async def student_schedule(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        schedule = payload.get("schedule", [])
        if not schedule:
            await message.answer(t("s_no_schedule", lang))
            return
        lines = [t("s_schedule_title", lang)]
        for item in schedule:
            lines.append(f"• <b>{item['group_name']}</b> — {item['weekday_label']}, {item['time_label']}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("student_schedule failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("s_payment"))
async def student_payment(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        await message.answer(
            render_payment(payload.get("payment", {}), lang, title=t("pay_title_s", lang)),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("student_payment failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("s_ranking"))
async def student_ranking(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        r = payload.get("ranking", {})
        top5 = _format_top5(r.get("top5", []), r.get("rank_position"))
        text = t("s_ranking", lang, group=r.get("group_name", "—"), rank=r.get("rank_position") or "—")
        if top5:
            text += "\n\n" + top5
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("student_ranking failed")
        await message.answer(t("generic_error", lang))


@router.message(btn_is("s_store"))
async def student_store(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        store = payload.get("store", {})
        products = store.get("products", [])
        if not products:
            await message.answer(t("s_no_products", lang))
            return

        cached = {
            int(p["id"]): {
                "name": p.get("name") or p.get("nom") or "—",
                "price_chaqmoq": p.get("price_chaqmoq") or p.get("narx_chaqmoq") or 0,
            }
            for p in products if p.get("id") is not None
        }
        await state.update_data(_cached_store_products=cached)
        await message.answer(t("s_store_title", lang), reply_markup=get_store_products_keyboard(products), parse_mode="HTML")
    except Exception:
        logger.exception("student_store failed")
        await message.answer(t("generic_error", lang))


@router.callback_query(F.data.startswith("student:buy:"))
async def student_buy_ask(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        try:
            product_id = int(callback.data.split(":")[2])
        except (ValueError, IndexError):
            await callback.answer("✗", show_alert=True)
            return

        data = await state.get_data()
        cached = data.get("_cached_store_products") or {}
        product = cached.get(product_id) or cached.get(str(product_id)) or {}
        name = product.get("name") or "—"
        price = product.get("price_chaqmoq") or 0

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=ik("buy_yes", lang), callback_data=f"student:buy_confirm:{product_id}")],
            [InlineKeyboardButton(text=ik("buy_no", lang), callback_data="student:buy_cancel")],
        ])
        await callback.message.answer(t("s_buy_ask", lang, name=name, price=price), reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception:
        logger.exception("student_buy_ask failed")
        await callback.answer(t("generic_error", lang), show_alert=True)


@router.callback_query(F.data.startswith("student:buy_confirm:"))
async def student_buy_confirm(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        try:
            product_id = int(callback.data.split(":")[2])
        except (ValueError, IndexError):
            await callback.answer("✗", show_alert=True)
            return

        data = await state.get_data()
        cached = data.get("_cached_store_products") or {}
        product = cached.get(product_id) or cached.get(str(product_id)) or {}
        name = product.get("name") or "—"

        status_code, response = await create_purchase_request_api(
            str(callback.from_user.id), profile["email"], product_id, qty=1,
        )
        if status_code == 201:
            backend_name = (response or {}).get("product_name") or name
            await callback.message.edit_text(t("s_buy_sent", lang, name=backend_name), parse_mode="HTML")
            await callback.answer("✅")
        else:
            err = (response or {}).get("error", t("generic_error", lang))
            await callback.answer(err, show_alert=True)
    except Exception:
        logger.exception("student_buy_confirm failed")
        await callback.answer(t("generic_error", lang), show_alert=True)


@router.callback_query(F.data == "student:buy_cancel")
async def student_buy_cancel(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        await callback.message.edit_text(t("s_buy_cancel", lang))
    except Exception:
        pass
    await callback.answer(t("s_buy_cancel", lang))


@router.message(btn_is("s_settings"))
async def student_settings(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    try:
        payload = await _load_student_dashboard(message, state)
        if not payload:
            return
        settings = payload.get("settings", {})
        enabled = bool(settings.get("notifications_enabled"))
        status_label = t("on", lang) if enabled else t("off", lang)
        await message.answer(
            t("s_settings", lang, status=status_label),
            reply_markup=get_student_settings_keyboard(enabled, lang), parse_mode="HTML",
        )
    except Exception:
        logger.exception("student_settings failed")
        await message.answer(t("generic_error", lang))


@router.callback_query(F.data.startswith("student:notifications:"))
async def student_toggle_notifications(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        enabled = bool(int(callback.data.split(":")[2]))
        status_code, response = await update_notification_settings_api(
            str(callback.from_user.id), profile["email"], enabled,
        )
        if status_code == 200 and response.get("ok"):
            label = t("on_v", lang) if enabled else t("off_v", lang)
            await callback.answer(t("s_notif_toggled", lang, status=label), show_alert=True)
        else:
            await callback.answer(response.get("error", t("generic_error", lang)), show_alert=True)
    except Exception:
        logger.exception("student_toggle_notifications failed")
        await callback.answer(t("generic_error", lang), show_alert=True)
