"""
Family bot onboarding — 3 tilli (O'zbekcha / Русский / Ўзбекча).

/start bosilganda: salom + til tanlash → tanlangandan keyin oldingi oqim
(bog'langan profil tekshiruvi yoki telefon/ism orqali kirish). Barcha xabarlar
markaziy i18n moduldan olinadi va QISQA.
"""
import re

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from keyboards.menu import get_family_menu
from services.api_client import (
    family_add_child_api,
    family_confirm_link_api,
    family_find_by_phone_api,
    family_issue_credentials_api,
    family_search_child_api,
    family_student_by_name_api,
    get_user_status_api,
    unlink_account_api,
)
from i18n import t, ik, btn_variants, get_lang, set_lang, lang_picker_kb, M

router = Router()


class FamilyOnboardingState(StatesGroup):
    waiting_phone = State()
    waiting_confirm = State()
    waiting_child_name = State()
    waiting_child_birthdate = State()
    waiting_student_name = State()
    waiting_student_birthdate = State()


# ─── Keyboardlar (til bo'yicha) ─────────────────────────────────────────────
def _role_picker_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ik("role_parent", lang), callback_data="family:role:parent")],
        [InlineKeyboardButton(text=ik("role_student", lang), callback_data="family:role:student")],
    ])


def _share_contact_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=ik("share_contact", lang), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _restart_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=ik("retry", lang), callback_data="family:restart")]]
    )


def _already_linked_kb(users: list, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for u in users[:5]:
        uid = u.get("id")
        name = u.get("ism") or "—"
        role_text = t("role_parent", lang) if u.get("role") == "parent" else t("role_student", lang)
        rows.append([InlineKeyboardButton(text=f"{role_text}: {name}", callback_data=f"family:resume:{uid}")])
    rows.append([InlineKeyboardButton(text=ik("new_profile", lang), callback_data="family:new_link")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_kb(target_user_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ik("confirm_open", lang), callback_data=f"family:confirm:{target_user_id}")],
        [InlineKeyboardButton(text=ik("retry", lang), callback_data="family:restart")],
    ])


def _multi_confirm_kb(matches: list, *, can_add: bool, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for m in matches[:15]:
        cid = m.get("id")
        name = m.get("full_name") or "—"
        rows.append([InlineKeyboardButton(text=f"✅ {name}", callback_data=f"family:confirm_pick:{cid}")])
    if can_add:
        rows.append([InlineKeyboardButton(text=ik("add_child", lang), callback_data="family:add_child_pre")])
    rows.append([InlineKeyboardButton(text=ik("retry", lang), callback_data="family:restart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _empty_parent_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ik("confirm_parent", lang), callback_data="family:confirm_parent_only")],
        [InlineKeyboardButton(text=ik("add_child", lang), callback_data="family:add_child_pre")],
        [InlineKeyboardButton(text=ik("retry", lang), callback_data="family:restart")],
    ])


def _search_results_kb(results: list, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for r in results[:15]:
        cid = r.get("id")
        name = r.get("full_name") or "—"
        center = r.get("center") or ""
        no_birth = "" if r.get("has_birth_date") else " ⚠"
        label = f"{name}" + (f" · {center}" if center else "") + no_birth
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"family:pickchild:{cid}")])
    rows.append([InlineKeyboardButton(text=ik("cancel", lang), callback_data="family:restart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Yordamchilar ───────────────────────────────────────────────────────────
_PHONE_RE = re.compile(r"[^\d+]")


def _try_parse_phone(text: str) -> str | None:
    if not text:
        return None
    cleaned = _PHONE_RE.sub("", text.strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not cleaned.isdigit():
        return None
    if len(cleaned) == 9:
        cleaned = "998" + cleaned
    if len(cleaned) == 12 and cleaned.startswith("998"):
        return "+" + cleaned
    if len(cleaned) >= 10:
        return "+" + cleaned
    return None


# ─── /start → til tanlash ────────────────────────────────────────────────────
@router.message(CommandStart())
async def family_start(message: types.Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    # Allaqachon ro'yxatdan o'tgan (bog'langan) bo'lsa — TIL SO'RAMAYMIZ, to'g'ridan-to'g'ri menyu.
    status_code, response = await get_user_status_api(str(tg_id))
    linked = (
        status_code == 200
        and (response or {}).get("status") == "linked"
        and any(u.get("role") in ("parent", "student") for u in ((response or {}).get("users") or []))
    )
    if linked:
        await _run_start_flow(message, tg_id, state, response=response)
        return
    # Yangi foydalanuvchi — til tanlash
    await message.answer(M["pick_lang"]["uz"], reply_markup=lang_picker_kb(), parse_mode="HTML")


@router.message(Command("language", "til"))
async def family_language(message: types.Message, state: FSMContext):
    """Istalgan vaqtда tilni o'zgartirish."""
    await message.answer(M["pick_lang"]["uz"], reply_markup=lang_picker_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("family:lang:"))
async def family_set_lang(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split(":", 2)[2]
    set_lang(callback.from_user.id, lang)
    await callback.answer()
    await _run_start_flow(callback.message, callback.from_user.id, state)


async def _run_start_flow(msg: types.Message, tg_id: int, state: FSMContext, response=None):
    """Bog'langan profil bo'lsa menyu, aks holda kirish oqimi. `response` berilsa qayta so'ramaymiz."""
    lang = get_lang(tg_id)
    if response is None:
        _sc, response = await get_user_status_api(str(tg_id))
    response = response or {}
    if response.get("status") == "linked":
        users = response.get("users") or []
        family_users = [u for u in users if u.get("role") in ("parent", "student")]
        if family_users:
            if len(family_users) == 1:
                u = family_users[0]
                role = u.get("role")
                await state.set_data({
                    "role": role,
                    "current_user_id": u.get("id"),
                    "current_user_email": u.get("email"),
                    "current_user_role": role,
                    "current_user_name": u.get("ism"),
                })
                await msg.answer(
                    t("linked_one", lang, name=u.get("ism") or "—"),
                    reply_markup=get_family_menu(role, lang),
                    parse_mode="HTML",
                )
                return
            await state.update_data(linked_family_users=family_users)
            await msg.answer(
                t("linked_many", lang),
                reply_markup=_already_linked_kb(family_users, lang),
                parse_mode="HTML",
            )
            return

    await msg.answer(t("onboard_who", lang), reply_markup=_role_picker_kb(lang), parse_mode="HTML")


@router.callback_query(F.data == "family:restart")
async def family_restart(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    lang = get_lang(callback.from_user.id)
    await callback.message.answer(t("pick_who", lang), reply_markup=_role_picker_kb(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("family:resume:"))
async def family_resume_profile(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        user_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("✗", show_alert=True)
        return
    data = await state.get_data()
    linked_users = data.get("linked_family_users") or []
    user = next((u for u in linked_users if u.get("id") == user_id), None)
    if not user:
        await callback.answer(t("generic_error", lang), show_alert=True)
        return
    role = user.get("role")
    await state.set_data({
        "role": role,
        "current_user_id": user.get("id"),
        "current_user_email": user.get("email"),
        "current_user_role": role,
        "current_user_name": user.get("ism"),
    })
    await callback.message.answer(
        t("linked_one", lang, name=user.get("ism") or "—"),
        reply_markup=get_family_menu(role, lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "family:new_link")
async def family_new_link(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    lang = get_lang(callback.from_user.id)
    await callback.message.answer(t("pick_who", lang), reply_markup=_role_picker_kb(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("family:role:"))
async def family_pick_role(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    role = callback.data.split(":", 2)[2]
    if role not in ("parent", "student"):
        await callback.answer("✗", show_alert=True)
        return

    await state.update_data(role=role)

    if role == "student":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=ik("method_phone", lang), callback_data="family:student_method:phone")],
            [InlineKeyboardButton(text=ik("method_name", lang), callback_data="family:student_method:name")],
            [InlineKeyboardButton(text=ik("back", lang), callback_data="family:restart")],
        ])
        await callback.message.answer(t("student_method", lang), reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return

    await state.set_state(FamilyOnboardingState.waiting_phone)
    await callback.message.answer(t("ask_phone", lang), reply_markup=_share_contact_kb(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("family:student_method:"))
async def family_student_method(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    method = callback.data.split(":", 2)[2]
    if method == "phone":
        await state.set_state(FamilyOnboardingState.waiting_phone)
        await callback.message.answer(t("ask_phone", lang), reply_markup=_share_contact_kb(lang), parse_mode="HTML")
        await callback.answer()
        return
    if method == "name":
        await state.set_state(FamilyOnboardingState.waiting_student_name)
        await callback.message.answer(t("ask_name", lang), parse_mode="HTML")
        await callback.answer()
        return
    await callback.answer("✗", show_alert=True)


# ─── Wizard davomida menyu tugmasi bosilsa — oqimni bekor qilamiz ───────────
_WIZARD_STATES = (
    FamilyOnboardingState.waiting_phone,
    FamilyOnboardingState.waiting_student_name,
    FamilyOnboardingState.waiting_student_birthdate,
    FamilyOnboardingState.waiting_child_name,
    FamilyOnboardingState.waiting_child_birthdate,
)
# Barcha til va (keshlangan eski menyular uchun) eski umumiy tugmalar
MENU_BUTTON_TEXTS = btn_variants(
    "p_children", "p_attendance", "p_payment", "p_balance", "p_teacher", "p_addchild",
    "s_status", "s_balance", "s_schedule", "s_payment", "s_ranking", "s_store", "s_settings",
    "c_sitelogin", "c_logout",
) | {
    "👤 Profil", "📜 Faoliyat tarixi", "🔐 Xavfsizlik", "🔄 Profilni almashtirish", "ℹ️ Yordam",
    "🚪 Chiqish", "🔑 Saytga login", "➕ Farzand qo'shish",  # eski o'zbekcha yozuvlar
}


@router.message(StateFilter(*_WIZARD_STATES), F.text.in_(MENU_BUTTON_TEXTS))
async def cancel_wizard_on_menu_tap(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    role = data.get("current_user_role") or data.get("role")
    await state.set_state(None)
    await message.answer(t("back_to_menu", lang), reply_markup=get_family_menu(role, lang))


# ─── O'quvchi: ism + tug'ilgan sana ──────────────────────────────────────────
@router.message(FamilyOnboardingState.waiting_student_name, F.text)
async def family_student_name(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    name_query = " ".join(message.text.split()).strip()
    if len(name_query) < 3:
        await message.answer(t("min3", lang), parse_mode="HTML")
        return
    await state.update_data(student_name_query=name_query)
    await state.set_state(FamilyOnboardingState.waiting_student_birthdate)
    await message.answer(t("ask_birthdate", lang), parse_mode="HTML")


@router.message(FamilyOnboardingState.waiting_student_birthdate, F.text)
async def family_student_birthdate(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    raw = message.text.strip()
    data = await state.get_data()
    name_query = data.get("student_name_query") or ""

    status_code, response = await family_student_by_name_api(
        name_query=name_query, birth_date=raw, telegram_id=str(message.from_user.id),
    )

    if status_code == 429:
        await message.answer(t("too_many", lang), reply_markup=_restart_kb(lang))
        await state.clear()
        return

    if status_code != 200 or not response.get("ok"):
        await message.answer(t("not_found_name", lang), parse_mode="HTML", reply_markup=_restart_kb(lang))
        return

    matches = response.get("matches") or []
    await state.update_data(role="student", parent_user_id=None, can_add_children=False)
    await state.set_state(FamilyOnboardingState.waiting_confirm)

    if len(matches) == 1:
        s = matches[0]
        await message.answer(
            t("found_one", lang, name=s.get("full_name"), center=s.get("center", "—")),
            reply_markup=_confirm_kb(s["id"], lang), parse_mode="HTML",
        )
        return

    await message.answer(
        t("found_many", lang, n=len(matches)),
        reply_markup=_multi_confirm_kb(matches, can_add=False, lang=lang), parse_mode="HTML",
    )


# ─── Telefon ─────────────────────────────────────────────────────────────────
async def _process_phone(message: types.Message, state: FSMContext, phone: str):
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    role = data.get("role") or "parent"

    await message.answer(t("checking", lang), reply_markup=ReplyKeyboardRemove())

    status_code, response = await family_find_by_phone_api(
        phone=phone, role=role, telegram_id=str(message.from_user.id),
        telegram_username=message.from_user.username,
    )

    if status_code == 429:
        await message.answer(t("too_many", lang), reply_markup=_restart_kb(lang))
        await state.clear()
        return

    if status_code != 200 or not response.get("ok"):
        await message.answer(t("not_found_phone", lang), parse_mode="HTML", reply_markup=_restart_kb(lang))
        await state.clear()
        return

    matches = response.get("matches") or []
    parent_user_id = response.get("parent_user_id")
    can_add_children = bool(response.get("can_add_children"))

    await state.update_data(phone=phone, parent_user_id=parent_user_id, can_add_children=can_add_children)
    await state.set_state(FamilyOnboardingState.waiting_confirm)

    if role == "student":
        if len(matches) == 1:
            child = matches[0]
            await message.answer(
                t("found_one", lang, name=child.get("full_name"), center=child.get("center", "—")),
                reply_markup=_confirm_kb(child["id"], lang), parse_mode="HTML",
            )
            return
        await message.answer(
            t("found_many", lang, n=len(matches)),
            reply_markup=_multi_confirm_kb(matches, can_add=False, lang=lang), parse_mode="HTML",
        )
        return

    # PARENT
    if not matches:
        if can_add_children:
            await message.answer(t("parent_no_child", lang), reply_markup=_empty_parent_kb(lang), parse_mode="HTML")
            return
        await message.answer(t("not_found_phone", lang), parse_mode="HTML", reply_markup=_restart_kb(lang))
        await state.clear()
        return

    await message.answer(
        t("parent_children_found", lang, n=len(matches)),
        reply_markup=_multi_confirm_kb(matches, can_add=can_add_children, lang=lang), parse_mode="HTML",
    )


@router.message(FamilyOnboardingState.waiting_phone, F.contact)
async def family_receive_contact(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    contact = message.contact
    if not contact or not contact.phone_number:
        await message.answer(t("phone_bad", lang), parse_mode="HTML")
        return
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(t("share_own", lang), parse_mode="HTML", reply_markup=_share_contact_kb(lang))
        return
    await _process_phone(message, state, contact.phone_number)


@router.message(FamilyOnboardingState.waiting_phone, F.text)
async def family_phone_text(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    phone = _try_parse_phone(message.text)
    if not phone:
        await message.answer(t("phone_bad", lang), reply_markup=_share_contact_kb(lang), parse_mode="HTML")
        return
    await _process_phone(message, state, phone)


# ─── Tasdiqlash ─────────────────────────────────────────────────────────────
async def _confirm_and_open_panel(callback: types.CallbackQuery, state: FSMContext, target_user_id: int, role: str):
    lang = get_lang(callback.from_user.id)
    status_code, response = await family_confirm_link_api(
        user_id=target_user_id, role=role, telegram_id=str(callback.from_user.id),
        telegram_username=callback.from_user.username,
    )
    if status_code != 200 or not response.get("ok"):
        await callback.message.answer(t("confirm_fail", lang), reply_markup=_restart_kb(lang))
        await callback.answer()
        return

    profile = response.get("profile") or {}
    await state.set_data({
        "role": role,
        "parent_user_id": (await state.get_data()).get("parent_user_id"),
        "phone": (await state.get_data()).get("phone"),
        "current_user_id": profile.get("id"),
        "current_user_email": profile.get("email"),
        "current_user_role": profile.get("role"),
        "current_user_name": profile.get("full_name"),
    })
    await state.set_state(None)

    role_text = t("role_parent", lang) if role == "parent" else t("role_student", lang)
    await callback.message.answer(
        t("panel_open", lang, role=role_text, name=profile.get("full_name") or "—"),
        reply_markup=get_family_menu(role, lang), parse_mode="HTML",
    )
    await callback.answer("✅")


@router.callback_query(F.data.startswith("family:confirm:"))
async def family_confirm_single(callback: types.CallbackQuery, state: FSMContext):
    try:
        target_user_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("✗", show_alert=True)
        return
    data = await state.get_data()
    role = data.get("role") or "parent"
    await _confirm_and_open_panel(callback, state, target_user_id, role)


@router.callback_query(F.data.startswith("family:confirm_pick:"))
async def family_confirm_pick(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    data = await state.get_data()
    role = data.get("role") or "parent"
    if role == "student":
        try:
            target_user_id = int(callback.data.split(":", 2)[2])
        except (ValueError, IndexError):
            await callback.answer("✗", show_alert=True)
            return
        await _confirm_and_open_panel(callback, state, target_user_id, role)
        return
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer(t("generic_error", lang), show_alert=True)
        return
    await _confirm_and_open_panel(callback, state, int(parent_user_id), "parent")


@router.callback_query(F.data == "family:confirm_parent_only")
async def family_confirm_parent_only(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer(t("generic_error", lang), show_alert=True)
        return
    await _confirm_and_open_panel(callback, state, int(parent_user_id), "parent")


# ─── Farzand qo'shish ────────────────────────────────────────────────────────
@router.callback_query(F.data == "family:add_child_pre")
async def family_add_child_pre(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer(t("generic_error", lang), show_alert=True)
        return
    await _confirm_and_open_panel(callback, state, int(parent_user_id), "parent")
    await state.set_state(FamilyOnboardingState.waiting_child_name)
    await callback.message.answer(t("add_child_ask", lang), parse_mode="HTML")


@router.message(F.text.in_(btn_variants("p_addchild")) | (F.text == "➕ Farzand qo'shish"))
async def family_add_child_from_menu(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    role = data.get("current_user_role")
    parent_user_id = data.get("parent_user_id") or data.get("current_user_id")
    if role != "parent" or not parent_user_id:
        await message.answer(t("only_parents", lang))
        return
    await state.update_data(parent_user_id=parent_user_id)
    await state.set_state(FamilyOnboardingState.waiting_child_name)
    await message.answer(t("add_child_ask", lang), parse_mode="HTML")


@router.message(FamilyOnboardingState.waiting_child_name, F.text)
async def family_search_child_by_name(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    name_query = " ".join(message.text.split()).strip()
    if len(name_query) < 3:
        await message.answer(t("min3", lang), parse_mode="HTML")
        return

    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await message.answer(t("session_expired", lang), reply_markup=_restart_kb(lang))
        await state.clear()
        return

    status_code, response = await family_search_child_api(
        parent_user_id=int(parent_user_id), name_query=name_query, telegram_id=str(message.from_user.id),
    )

    if status_code != 200 or not response.get("ok"):
        await message.answer(t("child_not_found", lang), parse_mode="HTML", reply_markup=_restart_kb(lang))
        return

    results = response.get("results") or []
    await message.answer(
        t("child_found_many", lang, n=len(results)),
        reply_markup=_search_results_kb(results, lang), parse_mode="HTML",
    )


@router.callback_query(FamilyOnboardingState.waiting_child_name, F.data.startswith("family:pickchild:"))
async def family_pick_search_result(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    try:
        child_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("✗", show_alert=True)
        return
    await state.update_data(picked_child_id=child_id)
    await state.set_state(FamilyOnboardingState.waiting_child_birthdate)
    await callback.message.answer(t("ask_child_birthdate", lang), parse_mode="HTML")
    await callback.answer()


@router.message(FamilyOnboardingState.waiting_child_birthdate, F.text)
async def family_confirm_birthdate(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    raw = message.text.strip()
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    child_id = data.get("picked_child_id")
    role = data.get("current_user_role") or data.get("role")

    if not parent_user_id or not child_id:
        await message.answer(t("session_expired", lang), reply_markup=_restart_kb(lang))
        await state.clear()
        return

    status_code, response = await family_add_child_api(
        parent_user_id=int(parent_user_id), child_id=int(child_id),
        birth_date=raw, telegram_id=str(message.from_user.id),
    )

    if status_code != 200 or not response.get("ok"):
        await message.answer(t("child_not_found", lang), parse_mode="HTML", reply_markup=_restart_kb(lang))
        return

    child = response.get("child") or {}
    name = child.get("full_name") or "—"
    await state.set_state(None)
    await message.answer(
        t("child_added", lang, name=name),
        reply_markup=get_family_menu(role or "parent", lang), parse_mode="HTML",
    )


# ─── "🔑 Saytga kirish" — magic link (parolsiz) ─────────────────────────────
@router.message(F.text.in_(btn_variants("c_sitelogin")) | (F.text == "🔑 Saytga login"))
async def family_issue_credentials(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    role = data.get("current_user_role")
    user_id = data.get("current_user_id")
    if not role or not user_id:
        await message.answer(t("session_expired", lang))
        return

    status_code, response = await family_issue_credentials_api(
        user_id=int(user_id), role=role, telegram_id=str(message.from_user.id),
    )
    if status_code != 200 or not response.get("ok"):
        await message.answer(t("creds_fail", lang))
        return

    creds = response.get("credentials") or {}
    user = response.get("user") or {}
    magic_url = response.get("magic_url") or ""

    reply_markup = None
    if magic_url:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=ik("magic_login", lang), url=magic_url)]]
        )

    text = (
        t("creds_title", lang, name=user.get("full_name", "—")) + "\n\n"
        + t("creds_manual", lang, email=creds.get("email", "—"), password=creds.get("password", "—"))
    )
    await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


# ─── "🚪 Chiqish" ────────────────────────────────────────────────────────────
@router.message(F.text.in_(btn_variants("c_logout")) | (F.text == "🚪 Chiqish"))
async def family_logout_menu(message: types.Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    status_code, response = await get_user_status_api(str(message.from_user.id))
    if status_code != 200 or response.get("status") != "linked":
        await state.clear()
        await message.answer(t("logout_done", lang), reply_markup=ReplyKeyboardRemove())
        return

    users = response.get("users") or []
    data = await state.get_data()
    current_email = data.get("current_user_email")

    family_users = [u for u in users if u.get("role") in ("parent", "student")]
    if not family_users:
        family_users = users

    if len(family_users) == 1:
        u = family_users[0]
        role_text = t("role_parent", lang) if u.get("role") == "parent" else t("role_student", lang)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 {u.get('ism')} ({role_text})", callback_data=f"family:unlink_confirm:{u.get('email')}")],
            [InlineKeyboardButton(text=ik("buy_no", lang), callback_data="family:unlink_cancel")],
        ])
        await message.answer(t("logout_pick", lang), reply_markup=kb, parse_mode="HTML")
    else:
        rows = []
        for u in family_users:
            role_text = t("role_parent", lang) if u.get("role") == "parent" else t("role_student", lang)
            marker = " ✅" if u.get("email") == current_email else ""
            rows.append([InlineKeyboardButton(text=f"🗑 {u.get('ism')} ({role_text}){marker}", callback_data=f"family:unlink_confirm:{u.get('email')}")])
        rows.append([InlineKeyboardButton(text=t("unlink_all_btn", lang), callback_data="family:unlink_all")])
        rows.append([InlineKeyboardButton(text=ik("buy_no", lang), callback_data="family:unlink_cancel")])
        await message.answer(t("logout_pick", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")


@router.callback_query(F.data.startswith("family:unlink_confirm:"))
async def family_unlink_confirm(callback: types.CallbackQuery):
    lang = get_lang(callback.from_user.id)
    email = callback.data.split(":", 2)[2]
    await callback.message.edit_text(
        f"{t('unlink_q', lang)}\n<code>{email}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=ik("buy_yes", lang), callback_data=f"family:unlink_do:{email}"),
            InlineKeyboardButton(text=ik("buy_no", lang), callback_data="family:unlink_cancel"),
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("family:unlink_do:"))
async def family_unlink_do(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    email = callback.data.split(":", 2)[2]
    status_code, response = await unlink_account_api(str(callback.from_user.id), email=email)

    if status_code != 200:
        await callback.answer(t("generic_error", lang), show_alert=True)
        return

    await callback.message.edit_text("✅")

    sc2, resp2 = await get_user_status_api(str(callback.from_user.id))
    if sc2 == 200 and resp2.get("status") == "linked":
        remaining = resp2.get("users") or []
        family_remaining = [u for u in remaining if u.get("role") in ("parent", "student")]
        if not family_remaining:
            family_remaining = remaining
        if family_remaining:
            u = family_remaining[0]
            role = u.get("role")
            await state.set_data({
                "role": role,
                "current_user_id": u.get("id"),
                "current_user_email": u.get("email"),
                "current_user_role": role,
                "current_user_name": u.get("ism"),
            })
            await callback.message.answer(
                t("linked_one", lang, name=u.get("ism") or "—"),
                reply_markup=get_family_menu(role, lang), parse_mode="HTML",
            )
            return

    await state.clear()
    await callback.message.answer(t("logout_done", lang), reply_markup=ReplyKeyboardRemove())
    await callback.answer()


@router.callback_query(F.data == "family:unlink_all")
async def family_unlink_all_confirm(callback: types.CallbackQuery):
    lang = get_lang(callback.from_user.id)
    await callback.message.edit_text(
        t("unlink_q", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=ik("buy_yes", lang), callback_data="family:unlink_all_do"),
            InlineKeyboardButton(text=ik("buy_no", lang), callback_data="family:unlink_cancel"),
        ]]),
    )
    await callback.answer()


@router.callback_query(F.data == "family:unlink_all_do")
async def family_unlink_all_do(callback: types.CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    status_code, response = await unlink_account_api(str(callback.from_user.id))
    if status_code == 200:
        await state.clear()
        await callback.message.edit_text("✅")
        await callback.message.answer(t("logout_done", lang), reply_markup=ReplyKeyboardRemove())
    else:
        await callback.answer(t("generic_error", lang), show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "family:unlink_cancel")
async def family_unlink_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.answer(t("s_buy_cancel", get_lang(callback.from_user.id)))
