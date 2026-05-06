"""
Family bot uchun onboarding handler.

Oqim:
1. /start → 2 ta inline tugma: "Men ota-ona" / "Men o'quvchi"
2. Telefon ulashish (ikki yo'l):
   - "📱 Telefon raqamni ulashish" tugmasi (Telegram contact share)
   - YOKI matn sifatida +998901234567 / 901234567 yozish
3. Backend find-by-phone → match
4. Topilgan bo'lsa:
   - Ota-ona bir nechta bola bilan → InlineKeyboard ro'yxati, tanlash
   - Bitta bola yoki o'quvchi → bevosita login+parol berish
   - 0 bola, lekin parent profili mavjud → "➕ Farzand qo'shish" tugmasi
5. "➕ Farzand qo'shish" → ism yozish → ro'yxat → tug'ilgan sana → biriktirish
"""
from __future__ import annotations

import logging
import re

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from services.api_client import (
    family_add_child_api,
    family_find_by_phone_api,
    family_issue_credentials_api,
    family_search_child_api,
)

logger = logging.getLogger(__name__)
router = Router()


class FamilyOnboardingState(StatesGroup):
    waiting_phone = State()
    waiting_child = State()
    waiting_child_name = State()
    waiting_child_birthdate = State()


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


def _post_credentials_kb(can_add_children: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_add_children:
        rows.append([InlineKeyboardButton(text="➕ Yana farzand qo'shish", callback_data="family:add_child")])
    rows.append([InlineKeyboardButton(text="🔄 Boshqa raqam", callback_data="family:restart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _children_kb(children: list, *, with_add: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for ch in children[:20]:
        cid = ch.get("id")
        name = ch.get("full_name") or "—"
        center = ch.get("center") or ""
        label = name + (f" · {center}" if center else "")
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"family:child:{cid}")])
    if with_add:
        rows.append([InlineKeyboardButton(text="➕ Farzand qo'shish", callback_data="family:add_child")])
    rows.append([InlineKeyboardButton(text="🔄 Boshqa raqam", callback_data="family:restart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    """+998901234567, 998901234567, 901234567 — barcha formatlarni qabul qilish."""
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


def _format_credentials(payload: dict) -> str:
    user = payload.get("user") or {}
    creds = payload.get("credentials") or {}
    login_url = payload.get("login_url") or ""
    name = user.get("full_name") or "—"
    role = user.get("role_label") or user.get("role") or ""
    email = creds.get("email") or "—"
    password = creds.get("password") or "—"
    lines = [
        "✅ <b>Hisob topildi va yangi parol yaratildi</b>",
        "",
        f"👤 <b>{name}</b>" + (f" — {role}" if role else ""),
    ]
    if login_url:
        lines.append(f"🌐 Sayt: <code>{login_url}</code>")
    lines.extend(
        [
            "",
            f"📧 <b>Login:</b> <code>{email}</code>",
            f"🔑 <b>Parol:</b> <code>{password}</code>",
            "",
            "⚠️ <i>Eski parol bekor qilindi. Iltimos, ushbu parolni xavfsiz saqlang.</i>",
        ]
    )
    return "\n".join(lines)


# ─── Boshlanish ─────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def family_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "ChaqmoqApp Oila botiga xush kelibsiz. Bu bot orqali siz "
        "<b>saytdagi login va parolni</b> osonlik bilan olishingiz mumkin.\n\n"
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


@router.callback_query(F.data.startswith("family:role:"))
async def family_pick_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split(":", 2)[2]
    if role not in ("parent", "student"):
        await callback.answer("Noto'g'ri tanlov", show_alert=True)
        return

    await state.set_state(FamilyOnboardingState.waiting_phone)
    await state.update_data(role=role)

    role_text = "ota-ona" if role == "parent" else "o'quvchi"
    await callback.message.answer(
        f"📱 <b>Telefon raqamingizni yuboring</b>\n\n"
        f"Siz <b>{role_text}</b> sifatida ulanmoqdasiz.\n\n"
        "<b>Ikki usuldan birini tanlang:</b>\n"
        "• Pastdagi tugmani bosing — Telegram avtomatik raqamni yuboradi\n"
        "• Yoki to'g'ridan-to'g'ri yozing: <code>+998901234567</code> yoki <code>901234567</code>",
        reply_markup=_share_contact_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Telefon: contact yoki matn ─────────────────────────────────────────────
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
        # Parent uchun: agar parent yo'q bo'lsa, "ota-ona profili kerak" xabari
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

    # State'da phone va parent_user_id ni saqlab qolamiz (keyingi qadamlar uchun)
    await state.update_data(
        phone=phone,
        parent_user_id=parent_user_id,
        can_add_children=can_add_children,
    )

    if role == "student":
        if len(matches) == 1:
            await _issue_and_send(message, state, matches[0]["id"], role="student")
            return
        await state.set_state(FamilyOnboardingState.waiting_child)
        await message.answer(
            "Sizga bog'langan bir nechta yozuv topildi. Birini tanlang:",
            reply_markup=_children_kb(matches),
            parse_mode="HTML",
        )
        return

    # Parent
    if not matches:
        # 0 bola, lekin parent profili bor bo'lsa — "Farzand qo'shish" taklif
        if can_add_children:
            await state.set_state(FamilyOnboardingState.waiting_child)
            await message.answer(
                "👨‍👩‍👧 <b>Sizga hech qanday farzand biriktirilmagan</b>\n\n"
                "Quyidagi tugmani bosib, farzandingizni qidirib qo'shing:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Farzand qo'shish", callback_data="family:add_child")],
                        [InlineKeyboardButton(text="🔄 Boshqa raqam", callback_data="family:restart")],
                    ]
                ),
                parse_mode="HTML",
            )
            return
        # Hatto parent profili ham yo'q
        await message.answer(
            "❌ Sizning raqamingiz bilan ota-ona profili topilmadi.\n\n"
            "Iltimos, markazga murojaat qiling.",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        await state.clear()
        return

    if len(matches) == 1 and not can_add_children:
        await _issue_and_send(message, state, matches[0]["id"], role="parent")
        return

    await state.set_state(FamilyOnboardingState.waiting_child)
    await message.answer(
        f"👨‍👩‍👧 <b>Topildi {len(matches)} ta farzand</b>\n\nQaysi farzand uchun login kerak?",
        reply_markup=_children_kb(matches, with_add=can_add_children),
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
            "❌ Iltimos, <b>o'zingizning</b> telefon raqamingizni ulashing — boshqa kishining "
            "kontaktini emas.",
            parse_mode="HTML",
            reply_markup=_share_contact_kb(),
        )
        return

    await _process_phone(message, state, contact.phone_number)


@router.message(FamilyOnboardingState.waiting_phone, F.text)
async def family_phone_text(message: types.Message, state: FSMContext):
    """Foydalanuvchi telefonni matn sifatida yozsa."""
    phone = _try_parse_phone(message.text)
    if not phone:
        await message.answer(
            "📱 Telefon raqami noto'g'ri formatda.\n\n"
            "Quyidagi tugma orqali ulashing yoki to'g'ri formatda yozing:\n"
            "<code>+998901234567</code> yoki <code>901234567</code>",
            reply_markup=_share_contact_kb(),
            parse_mode="HTML",
        )
        return
    await _process_phone(message, state, phone)


# ─── Bola tanlash → login berish ─────────────────────────────────────────────
@router.callback_query(FamilyOnboardingState.waiting_child, F.data.startswith("family:child:"))
async def family_pick_child(callback: types.CallbackQuery, state: FSMContext):
    try:
        child_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri tanlov", show_alert=True)
        return

    data = await state.get_data()
    role = data.get("role") or "parent"
    await _issue_and_send(callback.message, state, child_id, role=role, callback=callback)


async def _issue_and_send(
    target,
    state: FSMContext,
    user_id: int,
    *,
    role: str,
    callback: types.CallbackQuery | None = None,
):
    tg_user = callback.from_user if callback else target.from_user
    status_code, response = await family_issue_credentials_api(
        user_id=user_id,
        role=role,
        telegram_id=str(tg_user.id) if tg_user else None,
    )

    if callback:
        await callback.answer()

    if status_code != 200 or not response.get("ok"):
        err = (response or {}).get("error") or "Login berib bo'lmadi."
        await target.answer(
            f"❌ <b>Xatolik</b>\n\n{err}",
            parse_mode="HTML",
            reply_markup=_restart_kb(),
        )
        await state.clear()
        return

    data = await state.get_data()
    can_add = bool(data.get("can_add_children"))
    await target.answer(
        _format_credentials(response),
        parse_mode="HTML",
        reply_markup=_post_credentials_kb(can_add),
    )
    # state ni tozalamaymiz — agar foydalanuvchi "Yana farzand qo'shish" bossa, parent_user_id kerak


# ─── Farzand qidirish va qo'shish ────────────────────────────────────────────
@router.callback_query(F.data == "family:add_child")
async def family_add_child_start(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parent_user_id = data.get("parent_user_id")
    if not parent_user_id:
        await callback.answer("Avval ota-ona sifatida ulaning.", show_alert=True)
        return

    await state.set_state(FamilyOnboardingState.waiting_child_name)
    await callback.message.answer(
        "🔍 <b>Farzandingiz to'liq ismini yozing</b>\n\n"
        "Masalan: <code>Aliyev Akmal</code>\n"
        "Kamida 3 harf yozing.",
        parse_mode="HTML",
    )
    await callback.answer()


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
        parent_user_id=parent_user_id,
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
        "Farzandingizni tanlang. Tasdiqlash uchun keyin tug'ilgan sanasini ham yozasiz.",
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

    if not parent_user_id or not child_id:
        await message.answer("Sessiya muddati tugadi. Qaytadan boshlang.", reply_markup=_restart_kb())
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
    await message.answer(
        f"✅ <b>{name}</b> sizning farzandlaringiz ro'yxatiga qo'shildi.\n\n"
        "Endi shu farzandingiz uchun login va parolni olishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"🔑 {name} uchun login", callback_data=f"family:child:{child.get('id')}")],
                [InlineKeyboardButton(text="➕ Yana farzand qo'shish", callback_data="family:add_child")],
                [InlineKeyboardButton(text="🔄 Boshqa raqam", callback_data="family:restart")],
            ]
        ),
    )
    await state.set_state(FamilyOnboardingState.waiting_child)


# ─── Fallback ────────────────────────────────────────────────────────────────
@router.message()
async def family_default_fallback(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await family_start(message, state)
