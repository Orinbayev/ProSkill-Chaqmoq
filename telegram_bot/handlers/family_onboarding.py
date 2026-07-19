"""
Family bot uchun onboarding handler.

Asosiy oqim:
1. /start → 2 ta inline tugma: "Men ota-ona" / "Men o'quvchi"
2. Telefon ulashish (contact yoki matn)
3. Backend find-by-phone → match
4. "✅ Tasdiqlash" tugmasi (faqat bitta — barcha topilgan ma'lumotlar uchun)
5. Tasdiqlash → Telegram bilan bog'lash → asosiy panel ochiladi:
   - Parent: 👶 Bolalarim, 📊 Davomat, 💰 To'lov, ⚡ Chaqmoq, 📞 O'qituvchi,
            ➕ Farzand qo'shish, 🔑 Saytga login
   - Student: 📊 Mening holatim, ⚡ Chaqmoq, 📅 Jadval, 💰 To'lov,
              🏆 Reyting, 🛍 Do'kon, 🔔 Sozlamalar, 🔑 Saytga login
6. "➕ Farzand qo'shish" — ism yoz → ro'yxat → tug'ilgan sana → biriktirish
7. "🔑 Saytga login" — yangi parol generate qilinadi va ko'rsatiladi
"""
from __future__ import annotations

import logging
import re

from aiogram import Router, F, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from keyboards.menu import get_main_menu
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

logger = logging.getLogger(__name__)
router = Router()


class FamilyOnboardingState(StatesGroup):
    waiting_phone = State()
    waiting_confirm = State()
    waiting_child_name = State()
    waiting_child_birthdate = State()
    # Student uchun ism orqali qidirish
    waiting_student_name = State()
    waiting_student_birthdate = State()


# ─── Keyboardlar ────────────────────────────────────────────────────────────
def _role_picker_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍👩‍👧 Men ota-ona", callback_data="family:role:parent")],
            [InlineKeyboardButton(text="🎓 Men o'quvchi", callback_data="family:role:student")],
        ]
    )


def _share_contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _restart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="family:restart")]]
    )


def _already_linked_kb(users: list) -> InlineKeyboardMarkup:
    rows = []
    for u in users[:5]:
        uid = u.get("id")
        name = u.get("ism") or "—"
        role_text = "Ota-ona" if u.get("role") == "parent" else "O'quvchi"
        rows.append([InlineKeyboardButton(
            text=f"{role_text}: {name}",
            callback_data=f"family:resume:{uid}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Yangi profil ulash", callback_data="family:new_link")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_kb(target_user_id: int) -> InlineKeyboardMarkup:
    """Bir bola yoki bitta o'quvchi uchun tasdiqlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash va panelni ochish", callback_data=f"family:confirm:{target_user_id}")],
            [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="family:restart")],
        ]
    )


def _multi_confirm_kb(matches: list, *, can_add: bool) -> InlineKeyboardMarkup:
    """Bir necha bola — har biri uchun tasdiqlash tugmasi."""
    rows = []
    for m in matches[:15]:
        cid = m.get("id")
        name = m.get("full_name") or "—"
        rows.append([InlineKeyboardButton(text=f"✅ {name}", callback_data=f"family:confirm_pick:{cid}")])
    if can_add:
        rows.append([InlineKeyboardButton(text="➕ Farzand qo'shish", callback_data="family:add_child_pre")])
    rows.append([InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="family:restart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _empty_parent_kb() -> InlineKeyboardMarkup:
    """0 bola, lekin parent profili topildi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Profilni tasdiqlash va panelni ochish", callback_data="family:confirm_parent_only")],
            [InlineKeyboardButton(text="➕ Farzand qo'shish", callback_data="family:add_child_pre")],
            [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="family:restart")],
        ]
    )


def _search_results_kb(results: list) -> InlineKeyboardMarkup:
    rows = []
    for r in results[:15]:
        cid = r.get("id")
        name = r.get("full_name") or "—"
        center = r.get("center") or ""
        no_birth = "" if r.get("has_birth_date") else " ⚠"
        label = f"{name}" + (f" · {center}" if center else "") + no_birth
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"family:pickchild:{cid}")])
    rows.append([InlineKeyboardButton(text="🔄 Bekor qilish", callback_data="family:restart")])
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


# ─── Boshlanish ─────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def family_start(message: types.Message, state: FSMContext):
    await state.clear()

    # Foydalanuvchi allaqachon bot bilan bog'langanmi?
    status_code, response = await get_user_status_api(str(message.from_user.id))
    if status_code == 200 and response.get("status") == "linked":
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
                name = u.get("ism") or "Foydalanuvchi"
                await message.answer(
                    f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"
                    "Profilingiz faol. Quyidagi menyu orqali foydalaning:",
                    reply_markup=get_main_menu(role),
                    parse_mode="HTML",
                )
                return
            # Bir nechta profil — tanlash
            await state.update_data(linked_family_users=family_users)
            await message.answer(
                "👋 <b>Assalomu alaykum!</b>\n\n"
                f"Sizga tegishli <b>{len(family_users)} ta profil</b> topildi. "
                "Qaysi profilga kirishni xohlaysiz?",
                reply_markup=_already_linked_kb(family_users),
                parse_mode="HTML",
            )
            return

    # Bog'lanmagan — standart onboarding
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "ChaqmoqApp Oila botiga xush kelibsiz. Bu bot orqali siz "
        "<b>farzandingizning yoki o'zingizning</b> barcha ma'lumotlaringizni "
        "kuzatib borishingiz va saytga kirish parolini olishingiz mumkin.\n\n"
        "Iltimos, kim ekanligingizni tanlang:",
        reply_markup=_role_picker_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "family:restart")
async def family_restart(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Iltimos, kim ekanligingizni tanlang:",
        reply_markup=_role_picker_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("family:resume:"))
async def family_resume_profile(callback: types.CallbackQuery, state: FSMContext):
    """Allaqachon bog'langan profildan birini tanlash."""
    try:
        user_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Xato", show_alert=True)
        return
    data = await state.get_data()
    linked_users = data.get("linked_family_users") or []
    user = next((u for u in linked_users if u.get("id") == user_id), None)
    if not user:
        await callback.answer("Profil topilmadi", show_alert=True)
        return
    role = user.get("role")
    await state.set_data({
        "role": role,
        "current_user_id": user.get("id"),
        "current_user_email": user.get("email"),
        "current_user_role": role,
        "current_user_name": user.get("ism"),
    })
    name = user.get("ism") or "Foydalanuvchi"
    await callback.message.answer(
        f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"
        "Quyidagi menyu orqali foydalaning:",
        reply_markup=get_main_menu(role),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "family:new_link")
async def family_new_link(callback: types.CallbackQuery, state: FSMContext):
    """Yangi profil ulash — standart onboarding ga qaytish."""
    await state.clear()
    await callback.message.answer(
        "Iltimos, kim ekanligingizni tanlang:",
        reply_markup=_role_picker_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("family:role:"))
async def family_pick_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split(":", 2)[2]
    if role not in ("parent", "student"):
        await callback.answer("Noto'g'ri tanlov", show_alert=True)
        return

    await state.update_data(role=role)

    if role == "student":
        # O'quvchi uchun: 2 yo'lni taklif qilamiz
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Telefon raqami orqali", callback_data="family:student_method:phone")],
                [InlineKeyboardButton(text="📝 Ism va tug'ilgan sana orqali", callback_data="family:student_method:name")],
                [InlineKeyboardButton(text="🔄 Qaytish", callback_data="family:restart")],
            ]
        )
        await callback.message.answer(
            "🎓 <b>Siz o'quvchi sifatida ulanmoqdasiz.</b>\n\n"
            "Qanday usulda topilishingizni xohlaysiz?",
            reply_markup=kb,
            parse_mode="HTML",
        )
        await callback.answer()
        return

    # Ota-ona — to'g'ridan-to'g'ri telefon
    await state.set_state(FamilyOnboardingState.waiting_phone)
    await callback.message.answer(
        "📱 <b>Telefon raqamingizni yuboring</b>\n\n"
        "Siz <b>ota-ona</b> sifatida ulanmoqdasiz.\n\n"
        "<b>Ikki usuldan birini tanlang:</b>\n"
        "• Pastdagi tugmani bosing — Telegram avtomatik raqamni yuboradi\n"
        "• Yoki to'g'ridan-to'g'ri yozing: <code>+998901234567</code> yoki <code>901234567</code>",
        reply_markup=_share_contact_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("family:student_method:"))
async def family_student_method(callback: types.CallbackQuery, state: FSMContext):
    method = callback.data.split(":", 2)[2]
    if method == "phone":
        await state.set_state(FamilyOnboardingState.waiting_phone)
        await callback.message.answer(
            "📱 <b>Telefon raqamingizni yuboring</b>\n\n"
            "Pastdagi tugmani bosing yoki yozing: <code>+998901234567</code>",
            reply_markup=_share_contact_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    if method == "name":
        await state.set_state(FamilyOnboardingState.waiting_student_name)
        await callback.message.answer(
            "📝 <b>To'liq ismingizni yozing</b>\n\n"
            "Familiya va ismingizni yozing — masalan: <code>Aliyev Akmal</code>\n"
            "Kamida 3 harf yozing.",
            parse_mode="HTML",
        )
        await callback.answer()
        return
    await callback.answer("Noto'g'ri tanlov", show_alert=True)


# Wizard (ism/sana kutish) davomida foydalanuvchi menyu tugmasini bossa —
# uni "ism" deb qabul qilib xato spam qilmasin. Oqimni bekor qilib menyuni qaytaramiz.
_WIZARD_STATES = (
    FamilyOnboardingState.waiting_phone,
    FamilyOnboardingState.waiting_student_name,
    FamilyOnboardingState.waiting_student_birthdate,
    FamilyOnboardingState.waiting_child_name,
    FamilyOnboardingState.waiting_child_birthdate,
)
def _collect_menu_texts() -> frozenset[str]:
    """Reply-menyu tugma matnlarini bevosita klaviaturalardan yig'amiz (aniq mos kelishi uchun)."""
    from keyboards.parent_menu import get_parent_main_menu
    from keyboards.student_menu import get_student_main_menu

    texts: set[str] = set()
    for kb in (get_parent_main_menu(), get_student_main_menu()):
        for row in kb.keyboard:
            for btn in row:
                if getattr(btn, "text", None):
                    texts.add(btn.text)
    return frozenset(texts)


MENU_BUTTON_TEXTS = _collect_menu_texts()


@router.message(StateFilter(*_WIZARD_STATES), F.text.in_(MENU_BUTTON_TEXTS))
async def cancel_wizard_on_menu_tap(message: types.Message, state: FSMContext):
    """Oqim davomida menyu tugmasi bosildi → oqimni bekor qilib menyuga qaytaramiz."""
    data = await state.get_data()
    role = data.get("current_user_role") or data.get("role")
    await state.set_state(None)
    await message.answer(
        "↩️ Menyuga qaytdingiz. Kerakli bo'limni tanlang.",
        reply_markup=get_main_menu(role),
    )


@router.message(FamilyOnboardingState.waiting_student_name, F.text)
async def family_student_name(message: types.Message, state: FSMContext):
    name_query = " ".join(message.text.split()).strip()
    if len(name_query) < 3:
        await message.answer("Kamida 3 harf yozing. Masalan: <code>Aliyev</code>", parse_mode="HTML")
        return
    await state.update_data(student_name_query=name_query)
    await state.set_state(FamilyOnboardingState.waiting_student_birthdate)
    await message.answer(
        "📅 <b>Tug'ilgan sanangizni yozing</b>\n\n"
        "Format: <code>kun.oy.yil</code>\n"
        "Masalan: <code>15.03.2010</code>",
        parse_mode="HTML",
    )


@router.message(FamilyOnboardingState.waiting_student_birthdate, F.text)
async def family_student_birthdate(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    data = await state.get_data()
    name_query = data.get("student_name_query") or ""

    status_code, response = await family_student_by_name_api(
        name_query=name_query,
        birth_date=raw,
        telegram_id=str(message.from_user.id),
    )

    if status_code == 429:
        await message.answer(
            "⏱ Juda ko'p urinish. Iltimos, biroz kuting.",
            reply_markup=_restart_kb(),
        )
        await state.clear()
        return

    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Sizning ma'lumotlaringiz topilmadi."
        await message.answer(
            f"❌ {err}\n\nQaytadan tug'ilgan sana yozib ko'ring (masalan: <code>15.03.2010</code>) "
            "yoki <b>🔄 Qayta urinish</b>.",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        return

    matches = response.get("matches") or []
    await state.update_data(role="student", parent_user_id=None, can_add_children=False)
    await state.set_state(FamilyOnboardingState.waiting_confirm)

    if len(matches) == 1:
        s = matches[0]
        await message.answer(
            f"✅ <b>Topildi:</b>\n\n"
            f"👤 {s.get('full_name')}\n"
            f"🏫 {s.get('center', '—')}\n\n"
            "Davom etish uchun tasdiqlang:",
            reply_markup=_confirm_kb(s["id"]),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🔎 <b>Topildi {len(matches)} ta yozuv.</b>\n\nO'zingizni tanlang:",
        reply_markup=_multi_confirm_kb(matches, can_add=False),
        parse_mode="HTML",
    )


# ─── Telefon ─────────────────────────────────────────────────────────────────
async def _process_phone(message: types.Message, state: FSMContext, phone: str):
    data = await state.get_data()
    role = data.get("role") or "parent"

    await message.answer("🔍 Tekshirilmoqda...", reply_markup=ReplyKeyboardRemove())

    status_code, response = await family_find_by_phone_api(
        phone=phone,
        role=role,
        telegram_id=str(message.from_user.id),
        telegram_username=message.from_user.username,
    )

    if status_code == 429:
        await message.answer(
            "⏱ Juda ko'p urinish. Iltimos, biroz kuting va qayta urinib ko'ring.",
            reply_markup=_restart_kb(),
        )
        await state.clear()
        return

    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Sizning raqamingiz tizimda topilmadi."
        await message.answer(
            f"❌ <b>Topilmadi</b>\n\n{err}\n\n"
            "Iltimos, markazga murojaat qiling va telefon raqamingiz to'g'ri kiritilganini tekshiring.",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        await state.clear()
        return

    matches = response.get("matches") or []
    parent_user_id = response.get("parent_user_id")
    can_add_children = bool(response.get("can_add_children"))

    await state.update_data(
        phone=phone,
        parent_user_id=parent_user_id,
        can_add_children=can_add_children,
    )
    await state.set_state(FamilyOnboardingState.waiting_confirm)

    if role == "student":
        if len(matches) == 1:
            child = matches[0]
            await message.answer(
                f"✅ <b>Topildi:</b>\n\n"
                f"👤 {child.get('full_name')}\n"
                f"🏫 {child.get('center', '—')}\n\n"
                "Davom etish uchun tasdiqlang:",
                reply_markup=_confirm_kb(child["id"]),
                parse_mode="HTML",
            )
            return
        # Ko'p o'quvchi yozuvi
        await message.answer(
            f"🔎 <b>Topildi {len(matches)} ta yozuv.</b>\n\n"
            "Birini tanlang:",
            reply_markup=_multi_confirm_kb(matches, can_add=False),
            parse_mode="HTML",
        )
        return

    # PARENT
    if not matches:
        if can_add_children:
            await message.answer(
                "👨‍👩‍👧 <b>Sizning ota-ona profilingiz topildi</b>, lekin hech qanday "
                "farzand biriktirilmagan.\n\n"
                "Tasdiqlab panelni oching va keyin farzandingizni qo'shing:",
                reply_markup=_empty_parent_kb(),
                parse_mode="HTML",
            )
            return
        await message.answer(
            "❌ Sizning raqamingiz bilan ota-ona profili topilmadi.\n\n"
            "Iltimos, markazga murojaat qiling.",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        await state.clear()
        return

    # Bola(lar) topildi
    children_text = "\n".join(
        f"  • {m.get('full_name')} · {m.get('center', '—')}" for m in matches[:10]
    )
    await message.answer(
        f"👨‍👩‍👧 <b>Topildi {len(matches)} ta farzand</b>\n\n"
        f"{children_text}\n\n"
        "Profilingizni tasdiqlash uchun pastdan farzandingizni tanlang. "
        "Tasdiqlangach, ota-ona paneli ochiladi va siz barcha farzandlaringizni boshqara olasiz:",
        reply_markup=_multi_confirm_kb(matches, can_add=can_add_children),
        parse_mode="HTML",
    )


@router.message(FamilyOnboardingState.waiting_phone, F.contact)
async def family_receive_contact(message: types.Message, state: FSMContext):
    contact = message.contact
    if not contact or not contact.phone_number:
        await message.answer("Telefon raqamini ulash imkonsiz. Qayta urinib ko'ring.")
        return
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "❌ Iltimos, <b>o'zingizning</b> telefon raqamingizni ulashing.",
            parse_mode="HTML",
            reply_markup=_share_contact_kb(),
        )
        return
    await _process_phone(message, state, contact.phone_number)


@router.message(FamilyOnboardingState.waiting_phone, F.text)
async def family_phone_text(message: types.Message, state: FSMContext):
    phone = _try_parse_phone(message.text)
    if not phone:
        await message.answer(
            "📱 Telefon raqami noto'g'ri formatda.\n\n"
            "Tugma orqali ulashing yoki to'g'ri formatda yozing:\n"
            "<code>+998901234567</code> yoki <code>901234567</code>",
            reply_markup=_share_contact_kb(),
            parse_mode="HTML",
        )
        return
    await _process_phone(message, state, phone)


# ─── Tasdiqlash ─────────────────────────────────────────────────────────────
async def _confirm_and_open_panel(callback: types.CallbackQuery, state: FSMContext, target_user_id: int, role: str):
    status_code, response = await family_confirm_link_api(
        user_id=target_user_id,
        role=role,
        telegram_id=str(callback.from_user.id),
        telegram_username=callback.from_user.username,
    )
    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Tasdiqlab bo'lmadi."
        await callback.message.answer(f"❌ {err}", reply_markup=_restart_kb())
        await callback.answer()
        return

    profile = response.get("profile") or {}
    # Profile contextni saqlash — parent.py va student.py shu state'dan foydalanadi
    await state.set_data(
        {
            "role": role,
            "parent_user_id": (await state.get_data()).get("parent_user_id"),
            "phone": (await state.get_data()).get("phone"),
            "current_user_id": profile.get("id"),
            "current_user_email": profile.get("email"),
            "current_user_role": profile.get("role"),
            "current_user_name": profile.get("full_name"),
        }
    )
    # FSM state'ni tozalaymiz — parent.router/student.router text handlerlari ishlay boshlaydi
    await state.set_state(None)

    role_text = "Ota-ona" if role == "parent" else "O'quvchi"
    name = profile.get("full_name") or "—"
    await callback.message.answer(
        f"✅ <b>{role_text} paneli ochildi</b>\n\n"
        f"👤 {name}\n\n"
        "Quyidagi tugmalar orqali kerakli ma'lumotlarni oling:",
        reply_markup=get_main_menu(role),
        parse_mode="HTML",
    )
    await callback.answer("✅ Tasdiqlandi")


@router.callback_query(F.data.startswith("family:confirm:"))
async def family_confirm_single(callback: types.CallbackQuery, state: FSMContext):
    try:
        target_user_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri tanlov", show_alert=True)
        return
    data = await state.get_data()
    role = data.get("role") or "parent"
    await _confirm_and_open_panel(callback, state, target_user_id, role)


@router.callback_query(F.data.startswith("family:confirm_pick:"))
async def family_confirm_pick(callback: types.CallbackQuery, state: FSMContext):
    """Bir necha bola bo'lsa, parent profili confirm qilinadi (har bola tugmasi bosilganda)."""
    data = await state.get_data()
    role = data.get("role") or "parent"
    if role == "student":
        # Student: tanlangan studentni bog'laymiz
        try:
            target_user_id = int(callback.data.split(":", 2)[2])
        except (ValueError, IndexError):
            await callback.answer("Xato", show_alert=True)
            return
        await _confirm_and_open_panel(callback, state, target_user_id, role)
        return
    # Parent: parent_user_id ni bog'laymiz
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer("Ota-ona profili topilmadi.", show_alert=True)
        return
    await _confirm_and_open_panel(callback, state, int(parent_user_id), "parent")


@router.callback_query(F.data == "family:confirm_parent_only")
async def family_confirm_parent_only(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer("Ota-ona profili topilmadi.", show_alert=True)
        return
    await _confirm_and_open_panel(callback, state, int(parent_user_id), "parent")


# ─── Farzand qo'shish (parent panel + tasdiqlash oldidan) ───────────────────
@router.callback_query(F.data == "family:add_child_pre")
async def family_add_child_pre(callback: types.CallbackQuery, state: FSMContext):
    """Tasdiqlash bosqichida 'Farzand qo'shish' tugmasi — avval parent profilini tasdiqlaymiz."""
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer("Ota-ona profili topilmadi.", show_alert=True)
        return
    # Avval parent profilini tasdiqlaymiz
    await _confirm_and_open_panel(callback, state, int(parent_user_id), "parent")
    # Keyin add child flow ni boshlaymiz
    await state.set_state(FamilyOnboardingState.waiting_child_name)
    await callback.message.answer(
        "🔍 <b>Farzandingiz to'liq ismini yozing</b>\n\n"
        "Masalan: <code>Aliyev Akmal</code>\n"
        "Kamida 3 harf yozing.",
        parse_mode="HTML",
    )


# Parent panelidagi "➕ Farzand qo'shish" text tugmasi
@router.message(F.text == "➕ Farzand qo'shish")
async def family_add_child_from_menu(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("current_user_role")
    parent_user_id = data.get("parent_user_id") or data.get("current_user_id")
    if role != "parent" or not parent_user_id:
        await message.answer("❌ Bu tugma faqat ota-onalar uchun.")
        return
    await state.update_data(parent_user_id=parent_user_id)
    await state.set_state(FamilyOnboardingState.waiting_child_name)
    await message.answer(
        "🔍 <b>Farzandingiz to'liq ismini yozing</b>\n\n"
        "Masalan: <code>Aliyev Akmal</code>\n"
        "Kamida 3 harf yozing.",
        parse_mode="HTML",
    )


@router.message(FamilyOnboardingState.waiting_child_name, F.text)
async def family_search_child_by_name(message: types.Message, state: FSMContext):
    name_query = " ".join(message.text.split()).strip()
    if len(name_query) < 3:
        await message.answer("Kamida 3 harf yozing. Masalan: <code>Aliyev</code>", parse_mode="HTML")
        return

    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await message.answer("Sessiya muddati tugadi. Qaytadan boshlang.", reply_markup=_restart_kb())
        await state.clear()
        return

    status_code, response = await family_search_child_api(
        parent_user_id=int(parent_user_id),
        name_query=name_query,
        telegram_id=str(message.from_user.id),
    )

    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Hech narsa topilmadi."
        await message.answer(
            f"❌ {err}\n\nQayta urinish uchun ismni boshqacha yozing yoki <b>🔄 Bekor qilish</b>.",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        return

    results = response.get("results") or []
    await message.answer(
        f"🔎 <b>Topildi {len(results)} ta natija.</b>\n\n"
        "Farzandingizni tanlang. Tasdiqlash uchun keyin tug'ilgan sanasini yozasiz.",
        reply_markup=_search_results_kb(results),
        parse_mode="HTML",
    )


@router.callback_query(FamilyOnboardingState.waiting_child_name, F.data.startswith("family:pickchild:"))
async def family_pick_search_result(callback: types.CallbackQuery, state: FSMContext):
    try:
        child_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri tanlov", show_alert=True)
        return
    await state.update_data(picked_child_id=child_id)
    await state.set_state(FamilyOnboardingState.waiting_child_birthdate)
    await callback.message.answer(
        "📅 <b>Farzandingiz tug'ilgan sanasini yozing</b>\n\n"
        "Format: <code>kun.oy.yil</code>\n"
        "Masalan: <code>15.03.2010</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(FamilyOnboardingState.waiting_child_birthdate, F.text)
async def family_confirm_birthdate(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    child_id = data.get("picked_child_id")
    role = data.get("current_user_role") or data.get("role")

    if not parent_user_id or not child_id:
        await message.answer("Sessiya muddati tugadi.", reply_markup=_restart_kb())
        await state.clear()
        return

    status_code, response = await family_add_child_api(
        parent_user_id=int(parent_user_id),
        child_id=int(child_id),
        birth_date=raw,
        telegram_id=str(message.from_user.id),
    )

    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Biriktirish bekor qilindi."
        await message.answer(
            f"❌ {err}\n\nQaytadan tug'ilgan sanani yozib ko'ring (masalan: <code>15.03.2010</code>) "
            "yoki <b>🔄 Bekor qilish</b>.",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        return

    child = response.get("child") or {}
    name = child.get("full_name") or "Farzand"
    # State ni tozalaymiz va parent panelga qaytaramiz
    await state.set_state(None)
    await message.answer(
        f"✅ <b>{name}</b> sizning farzandlaringiz ro'yxatiga qo'shildi.\n\n"
        "Endi quyidagi tugmalar orqali ma'lumotlarini ko'rishingiz mumkin:",
        reply_markup=get_main_menu(role or "parent"),
        parse_mode="HTML",
    )


# ─── "🔑 Saytga login" — yangi parol generate ───────────────────────────────
@router.message(F.text == "🔑 Saytga login")
async def family_issue_credentials(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("current_user_role")
    user_id = data.get("current_user_id")
    if not role or not user_id:
        await message.answer("❌ Avval profilingizni tasdiqlang. /start")
        return

    status_code, response = await family_issue_credentials_api(
        user_id=int(user_id),
        role=role,
        telegram_id=str(message.from_user.id),
    )
    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Login berib bo'lmadi."
        await message.answer(f"❌ {err}")
        return

    creds = response.get("credentials") or {}
    user = response.get("user") or {}
    login_url = response.get("login_url") or ""
    magic_url = response.get("magic_url") or ""

    # Bir-bosishli kirish tugmasi (parolsiz) — asosiy usul
    reply_markup = None
    if magic_url:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔓 Saytga bir bosishda kirish", url=magic_url)]]
        )

    text_lines = [
        f"👤 <b>{user.get('full_name', '—')}</b>",
        "",
        "🔓 <b>Eng oson yo'l:</b> quyidagi tugmani bosing — parolsiz avtomat kirasiz,",
        "so'ng o'zingizga qulay parol o'rnatasiz.",
    ]
    # Qo'lda kirish uchun zaxira ma'lumotlar
    text_lines.append("")
    text_lines.append("<i>Yoki qo'lda kiring:</i>")
    if login_url:
        text_lines.append(f"🌐 Sayt: <code>{login_url}</code>")
    text_lines.append(f"📧 <b>Login:</b> <code>{creds.get('email', '—')}</code>")
    text_lines.append(f"🔑 <b>Parol:</b> <code>{creds.get('password', '—')}</code>")

    await message.answer("\n".join(text_lines), parse_mode="HTML", reply_markup=reply_markup)


# ─── "🚪 Chiqish" — bitta profildan yoki hammasidan chiqish ─────────────────
@router.message(F.text == "🚪 Chiqish")
async def family_logout_menu(message: types.Message, state: FSMContext):
    """Qaysi profildan chiqishni tanlash."""
    status_code, response = await get_user_status_api(str(message.from_user.id))
    if status_code != 200 or response.get("status") != "linked":
        await state.clear()
        await message.answer(
            "Hisobingiz allaqachon uzilgan. /start bosing.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    users = response.get("users") or []
    data = await state.get_data()
    current_email = data.get("current_user_email")

    # Faqat parent/student profillarini ko'rsat (family bot uchun)
    family_users = [u for u in users if u.get("role") in ("parent", "student")]
    if not family_users:
        family_users = users

    if len(family_users) == 1:
        u = family_users[0]
        role_text = "Ota-ona" if u.get("role") == "parent" else "O'quvchi"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🗑 {u.get('ism')} ({role_text}) — uzib tashlash",
                callback_data=f"family:unlink_confirm:{u.get('email')}",
            )],
            [InlineKeyboardButton(text="✖ Bekor qilish", callback_data="family:unlink_cancel")],
        ])
        await message.answer(
            "🚪 <b>Profildan chiqish</b>\n\nQuyidagi profilni botdan uzib tashlamoqchimisiz?",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        rows = []
        for u in family_users:
            role_text = "Ota-ona" if u.get("role") == "parent" else "O'quvchi"
            marker = " ✅" if u.get("email") == current_email else ""
            rows.append([InlineKeyboardButton(
                text=f"🗑 {u.get('ism')} ({role_text}){marker}",
                callback_data=f"family:unlink_confirm:{u.get('email')}",
            )])
        rows.append([InlineKeyboardButton(text="❌ Hammasini uzish", callback_data="family:unlink_all")])
        rows.append([InlineKeyboardButton(text="✖ Bekor qilish", callback_data="family:unlink_cancel")])
        await message.answer(
            "🚪 <b>Qaysi profildan chiqmoqchisiz?</b>\n\n"
            "Faqat bitta profilni uzasiz — qolgan profillar ishlayveradi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("family:unlink_confirm:"))
async def family_unlink_confirm(callback: types.CallbackQuery):
    email = callback.data.split(":", 2)[2]
    await callback.message.edit_text(
        f"❓ <b>Ishonchingiz komilmi?</b>\n\n<code>{email}</code> profili botdan uziladi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, uzib tashlash", callback_data=f"family:unlink_do:{email}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="family:unlink_cancel"),
            ]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("family:unlink_do:"))
async def family_unlink_do(callback: types.CallbackQuery, state: FSMContext):
    email = callback.data.split(":", 2)[2]
    status_code, response = await unlink_account_api(str(callback.from_user.id), email=email)

    if status_code != 200:
        err = (response or {}).get("error") or "Xatolik yuz berdi."
        await callback.answer(f"❌ {err}", show_alert=True)
        return

    await callback.message.edit_text(f"✅ Profil (<code>{email}</code>) muvaffaqiyatli uzildi.", parse_mode="HTML")

    # Qolgan profillarni tekshir
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
                f"🔄 Faol profil: <b>{u.get('ism')}</b>\n\nQuyidagi menyu orqali foydalaning:",
                reply_markup=get_main_menu(role),
                parse_mode="HTML",
            )
            return

    # Hech qanday profil qolmadi
    await state.clear()
    await callback.message.answer(
        "Barcha profillar uzildi. Botga qayta ulash uchun /start bosing.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await callback.answer()


@router.callback_query(F.data == "family:unlink_all")
async def family_unlink_all_confirm(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ <b>Barcha profillarni uzib tashlamoqchimisiz?</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, hammasini", callback_data="family:unlink_all_do"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="family:unlink_cancel"),
            ]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "family:unlink_all_do")
async def family_unlink_all_do(callback: types.CallbackQuery, state: FSMContext):
    status_code, response = await unlink_account_api(str(callback.from_user.id))
    if status_code == 200:
        await state.clear()
        await callback.message.edit_text("✅ Barcha profillar uzildi.")
        await callback.message.answer(
            "Botga qayta ulash uchun /start bosing.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        err = (response or {}).get("error") or "Xatolik."
        await callback.answer(f"❌ {err}", show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "family:unlink_cancel")
async def family_unlink_cancel(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role = data.get("current_user_role") or "parent"
    await callback.message.delete()
    await callback.answer("Bekor qilindi.")
