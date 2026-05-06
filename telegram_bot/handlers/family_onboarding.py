"""
Family bot uchun onboarding handler.

Oqim:
1. /start → 2 ta inline tugma: "Men ota-ona" / "Men o'quvchi"
2. Tugma bosilganda → "Telefon raqamingizni ulashing" (Telegram native share contact)
3. Telefon kelganida → backend find-by-phone API
4. Topilgan bo'lsa:
   - Ota-ona bir nechta bola bilan → InlineKeyboard ro'yxati, tanlash
   - Ota-ona bitta bola, yoki o'quvchi → bevosita login+parol berish
5. Login + yangi parol generatsiya qilinib ko'rsatiladi
"""
from __future__ import annotations

import logging

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

from services.api_client import family_find_by_phone_api, family_issue_credentials_api

logger = logging.getLogger(__name__)
router = Router()


class FamilyOnboardingState(StatesGroup):
    waiting_phone = State()
    waiting_child = State()


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


def _children_kb(children: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in children[:20]:
        cid = ch.get("id")
        name = ch.get("full_name") or "—"
        center = ch.get("center") or ""
        label = f"{name}" + (f" · {center}" if center else "")
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"family:child:{cid}")])
    rows.append([InlineKeyboardButton(text="🔄 Boshqa raqam", callback_data="family:restart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        f"📱 <b>Telefon raqamingizni ulashing</b>\n\n"
        f"Siz <b>{role_text}</b> sifatida ulanmoqdasiz.\n"
        "Quyidagi tugmani bosing — Telegram avtomatik telefon raqamingizni yuboradi.",
        reply_markup=_share_contact_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


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

    data = await state.get_data()
    role = data.get("role") or "parent"
    phone = contact.phone_number

    status_code, response = await family_find_by_phone_api(
        phone=phone,
        role=role,
        telegram_id=str(message.from_user.id),
        telegram_username=message.from_user.username,
    )

    # Ekran tugmalarini tozalash
    await message.answer("🔍 Tekshirilmoqda...", reply_markup=ReplyKeyboardRemove())

    if status_code == 429:
        await message.answer(
            "⏱ Juda ko'p urinish. Iltimos, biroz kuting va keyin qayta urinib ko'ring.",
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

    if role == "student":
        # O'quvchi uchun: bitta yoki bir nechta o'quvchi yozuvi (har xil markaz uchun) bo'lishi mumkin
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

    # Parent: matches — bola ro'yxati
    if len(matches) == 1:
        await _issue_and_send(message, state, matches[0]["id"], role="parent")
        return

    await state.set_state(FamilyOnboardingState.waiting_child)
    await message.answer(
        f"👨‍👩‍👧 <b>Topildi {len(matches)} ta farzand</b>\n\nQaysi farzand uchun login kerak?",
        reply_markup=_children_kb(matches),
        parse_mode="HTML",
    )


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
    status_code, response = await family_issue_credentials_api(
        user_id=user_id,
        role=role,
        telegram_id=str(target.from_user.id) if target.from_user else None,
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

    await target.answer(
        _format_credentials(response),
        parse_mode="HTML",
        reply_markup=_restart_kb(),
    )
    await state.clear()


@router.message(FamilyOnboardingState.waiting_phone)
async def family_phone_text_fallback(message: types.Message):
    """Foydalanuvchi telefon o'rniga matn yozsa — qayta yo'naltirish."""
    await message.answer(
        "📱 Iltimos, quyidagi tugma orqali telefon raqamingizni ulashing.",
        reply_markup=_share_contact_kb(),
    )


@router.message()
async def family_default_fallback(message: types.Message, state: FSMContext):
    """Boshqa har qanday holat — qayta /start."""
    current = await state.get_state()
    if current is None:
        await family_start(message, state)
