import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from keyboards.student_menu import get_store_products_keyboard, get_student_settings_keyboard
from services.api_client import (
    create_purchase_request_api,
    family_issue_credentials_api,
    get_bot_dashboard_api,
    update_notification_settings_api,
)
from services.profile_context import ensure_active_profile, get_active_profile, sync_profile_state

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
                f"  📅 {item['weekday_label']}\n"
                f"  🏫 {item['time_label']}"
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

        # Mahsulot ma'lumotlarini state'ga saqlaymiz — tasdiqlash dialogida nom/narx ko'rsatish uchun
        cached = {
            int(p["id"]): {
                "name": p.get("name") or p.get("nom") or "Mahsulot",
                "price_chaqmoq": p.get("price_chaqmoq") or p.get("narx_chaqmoq") or 0,
            }
            for p in products
            if p.get("id") is not None
        }
        await state.update_data(_cached_store_products=cached)

        recent_requests = "\n".join(
            f"• {item['product_name']} ×{item['qty']} — {item['status']}"
            for item in requests[:5]
        ) or "So'rovlar yo'q."
        text = (
            "🛍 <b>Do'kon</b>\n\n"
            "Mahsulotni tanlang — keyingi qadamda tasdiqlash so'raladi.\n\n"
            "<b>So'nggi so'rovlar:</b>\n"
            f"{recent_requests}"
        )
        await message.answer(text, reply_markup=get_store_products_keyboard(products), parse_mode="HTML")
    except Exception:
        logger.exception("student_store failed")
        await message.answer("❌ Do'konni ko'rsatishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("student:buy:"))
async def student_buy_ask(callback: types.CallbackQuery, state: FSMContext):
    """Mahsulot tugmasini bossa — avval tasdiqlash dialogi chiqadi."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        try:
            product_id = int(callback.data.split(":")[2])
        except (ValueError, IndexError):
            await callback.answer("Noto'g'ri tanlov", show_alert=True)
            return

        data = await state.get_data()
        cached = data.get("_cached_store_products") or {}
        # State da int yoki str key bo'lishi mumkin — ikkalasini tekshiramiz
        product = cached.get(product_id) or cached.get(str(product_id)) or {}
        name = product.get("name") or "Mahsulot"
        price = product.get("price_chaqmoq") or 0

        text = (
            "🛍 <b>Xarid so'rovini tasdiqlaysizmi?</b>\n\n"
            f"📦 Mahsulot: <b>{name}</b>\n"
            f"⚡ Narxi: <b>{price} Chaqmoq</b>\n\n"
            "Tasdiqlasangiz, manager yoki direktor tomonidan ko'rib chiqiladi. "
            "Tasdiqlangach <b>{price} Chaqmoq</b> balansingizdan ushlab qolinadi."
        ).replace("{price}", str(price))

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data=f"student:buy_confirm:{product_id}")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="student:buy_cancel")],
            ]
        )
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception:
        logger.exception("student_buy_ask failed")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)


@router.callback_query(F.data.startswith("student:buy_confirm:"))
async def student_buy_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Tasdiqlash bosilganda haqiqiy purchase request yuboriladi."""
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("student",))
        if not profile:
            return
        try:
            product_id = int(callback.data.split(":")[2])
        except (ValueError, IndexError):
            await callback.answer("Noto'g'ri tanlov", show_alert=True)
            return

        data = await state.get_data()
        cached = data.get("_cached_store_products") or {}
        product = cached.get(product_id) or cached.get(str(product_id)) or {}
        name = product.get("name") or "Mahsulot"

        status_code, response = await create_purchase_request_api(
            str(callback.from_user.id),
            profile["email"],
            product_id,
            qty=1,
        )
        if status_code == 201:
            backend_name = (response or {}).get("product_name") or name
            await callback.message.edit_text(
                "✅ <b>So'rov yuborildi!</b>\n\n"
                f"📦 Mahsulot: <b>{backend_name}</b>\n\n"
                "Manager yoki director tasdiqlagandan so'ng <b>balansingizdan ushlab qolinadi</b>. "
                "Holat haqida xabar olasiz.",
                parse_mode="HTML",
            )
            await callback.answer("✅ Yuborildi")
        else:
            err = (response or {}).get("error", "Xatolik yuz berdi.")
            await callback.answer(err, show_alert=True)
    except Exception:
        logger.exception("student_buy_confirm failed")
        await callback.answer("❌ So'rovni yuborib bo'lmadi.", show_alert=True)


@router.callback_query(F.data == "student:buy_cancel")
async def student_buy_cancel(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text("❌ Xarid so'rovi bekor qilindi.")
    except Exception:
        pass
    await callback.answer("Bekor qilindi")


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


@router.message(F.text == "🔑 Saytga login")
async def student_site_login(message: types.Message, state: FSMContext):
    """O'quvchiga yangi parol berib saytga kirish ma'lumotlarini yuboradi."""
    try:
        profile = await ensure_active_profile(message, state, allowed_roles=("student",))
        if not profile:
            return

        user_id = profile.get("user_id")
        if not user_id:
            # Main bot flow: current_user_id saqlanmagan — qayta olamiz
            refreshed = await sync_profile_state(state, str(message.from_user.id), profile["email"])
            user_id = (refreshed or {}).get("id")

        if not user_id:
            await message.answer("❌ Foydalanuvchi ma'lumotlari topilmadi. /start")
            return

        status_code, response = await family_issue_credentials_api(
            user_id=int(user_id),
            role="student",
            telegram_id=str(message.from_user.id),
        )
        if status_code != 200 or not response.get("ok"):
            err = (response or {}).get("error") or "Login berib bo'lmadi."
            await message.answer(f"❌ {err}")
            return

        creds = response.get("credentials") or {}
        user = response.get("user") or {}
        login_url = response.get("login_url") or ""
        lines = [
            "🔑 <b>Saytga kirish uchun yangi ma'lumotlar</b>",
            "",
            f"👤 <b>{user.get('full_name', '—')}</b>",
        ]
        if login_url:
            lines.append(f"🌐 Sayt: <code>{login_url}</code>")
        lines += [
            "",
            f"📧 <b>Login:</b> <code>{creds.get('email', '—')}</code>",
            f"🔑 <b>Parol:</b> <code>{creds.get('password', '—')}</code>",
            "",
            "⚠️ <i>Eski parol bekor qilindi. Ushbu parolni xavfsiz saqlang.</i>",
        ]
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("student_site_login failed")
        await message.answer("❌ Saytga kirish ma'lumotlarini berib bo'lmadi.")
