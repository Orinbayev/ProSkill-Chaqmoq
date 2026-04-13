import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from keyboards.teacher_menu import (
    get_teacher_attendance_keyboard,
    get_teacher_groups_keyboard,
)
from services.api_client import (
    get_bot_dashboard_api,
    get_group_attendance_sheet_api,
    mark_group_attendance_api,
)
from services.profile_context import ensure_active_profile

router = Router()
logger = logging.getLogger(__name__)


async def _load_teacher_dashboard(message: types.Message, state: FSMContext, group_id: int | None = None):
    profile = await ensure_active_profile(message, state, allowed_roles=("teacher",))
    if not profile:
        return None
    status_code, response = await get_bot_dashboard_api(
        str(message.from_user.id),
        profile["email"],
        group_id=group_id,
    )
    if status_code != 200 or not response.get("ok"):
        await message.answer("❌ O'qituvchi ma'lumotlarini yuklab bo'lmadi.")
        return None
    return response.get("teacher", {})


def _format_groups(groups: list[dict]):
    if not groups:
        return "Faol guruhlar topilmadi."
    return "\n\n".join(
        f"• <b>{group['name']}</b>\n"
        f"  O'quvchilar: {group['student_count']}\n"
        f"  Bugungi davomat: {group['today_attendance_count']}\n"
        f"  O'rtacha davomat: {group['average_attendance_rate']}%"
        for group in groups
    )


def _format_attendance_sheet(sheet: dict):
    students = sheet.get("students", [])
    if not students:
        return "Guruhda faol o'quvchilar topilmadi."
    lines = [
        f"✅ <b>{sheet['group']['name']} — davomat</b>",
        f"Sana: <b>{sheet.get('date')}</b>",
        "",
    ]
    for student in students[:25]:
        lines.append(
            f"• {student['full_name']} — {student['today_status_label']} "
            f"({student['attendance_rate']}%)"
        )
    return "\n".join(lines)


@router.message(F.text == "📚 Guruhlarim")
async def teacher_groups(message: types.Message, state: FSMContext):
    try:
        payload = await _load_teacher_dashboard(message, state)
        if not payload:
            return
        await message.answer(
            f"📚 <b>Guruhlarim</b>\n\n{_format_groups(payload.get('groups', []))}",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("teacher_groups failed")
        await message.answer("❌ Guruhlarni ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "✅ Davomat Belgilash")
async def teacher_attendance_entry(message: types.Message, state: FSMContext):
    try:
        payload = await _load_teacher_dashboard(message, state)
        if not payload:
            return
        groups = payload.get("groups", [])
        if not groups:
            await message.answer("ℹ️ Sizga biriktirilgan faol guruh yo'q.")
            return
        await message.answer(
            "✅ Davomat olish uchun guruhni tanlang:",
            reply_markup=get_teacher_groups_keyboard(groups, "attendance"),
        )
    except Exception:
        logger.exception("teacher_attendance_entry failed")
        await message.answer("❌ Davomat bo'limini ochishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("teacher:attendance:"))
async def teacher_attendance_sheet(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("teacher",))
        if not profile:
            return
        group_id = int(callback.data.split(":")[2])
        status_code, response = await get_group_attendance_sheet_api(
            str(callback.from_user.id),
            profile["email"],
            group_id,
        )
        if status_code != 200 or not response.get("ok"):
            await callback.answer("❌ Davomat jadvali yuklanmadi.", show_alert=True)
            return
        sheet = response.get("sheet", {})
        await callback.message.edit_text(
            _format_attendance_sheet(sheet),
            reply_markup=get_teacher_attendance_keyboard(group_id, sheet.get("students", [])),
            parse_mode="HTML",
        )
        await callback.answer()
    except Exception:
        logger.exception("teacher_attendance_sheet failed")
        await callback.answer("❌ Davomat jadvali ochilmadi.", show_alert=True)


@router.callback_query(F.data.startswith("teacher:mark:"))
async def teacher_mark_attendance(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("teacher",))
        if not profile:
            return
        _, _, group_id, student_id, status = callback.data.split(":")
        status_code, response = await mark_group_attendance_api(
            str(callback.from_user.id),
            profile["email"],
            int(group_id),
            int(student_id),
            status,
        )
        if status_code != 200 or not response.get("ok"):
            await callback.answer(response.get("error", "Xatolik yuz berdi."), show_alert=True)
            return
        await callback.answer(f"✅ {response.get('student_name')} — {response.get('status_label')}")

        sheet_status, sheet_response = await get_group_attendance_sheet_api(
            str(callback.from_user.id),
            profile["email"],
            int(group_id),
        )
        if sheet_status == 200 and sheet_response.get("ok"):
            sheet = sheet_response.get("sheet", {})
            await callback.message.edit_text(
                _format_attendance_sheet(sheet),
                reply_markup=get_teacher_attendance_keyboard(int(group_id), sheet.get("students", [])),
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("teacher_mark_attendance failed")
        await callback.answer("❌ Davomatni saqlab bo'lmadi.", show_alert=True)


@router.message(F.text == "👥 O'quvchilarim")
async def teacher_students(message: types.Message, state: FSMContext):
    try:
        payload = await _load_teacher_dashboard(message, state)
        if not payload:
            return
        groups = payload.get("groups", [])
        if not groups:
            await message.answer("ℹ️ Sizga biriktirilgan faol guruh yo'q.")
            return
        await message.answer(
            "👥 O'quvchilar ro'yxatini ko'rish uchun guruhni tanlang:",
            reply_markup=get_teacher_groups_keyboard(groups, "students"),
        )
    except Exception:
        logger.exception("teacher_students failed")
        await message.answer("❌ O'quvchilar bo'limini ochishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("teacher:students:"))
async def teacher_students_group(callback: types.CallbackQuery, state: FSMContext):
    try:
        profile = await ensure_active_profile(callback, state, allowed_roles=("teacher",))
        if not profile:
            return
        group_id = int(callback.data.split(":")[2])
        status_code, response = await get_bot_dashboard_api(
            str(callback.from_user.id),
            profile["email"],
            group_id=group_id,
        )
        if status_code != 200 or not response.get("ok"):
            await callback.answer("❌ O'quvchilar ro'yxati yuklanmadi.", show_alert=True)
            return
        teacher = response.get("teacher", {})
        students = teacher.get("students", [])
        if not students:
            await callback.message.edit_text("ℹ️ Bu guruhda faol o'quvchilar topilmadi.")
            await callback.answer()
            return
        lines = ["👥 <b>O'quvchilar</b>\n"]
        for item in students[:30]:
            lines.append(
                f"• {item['full_name']}\n"
                f"  Davomat: {item['attendance_rate']}%\n"
                f"  Chaqmoq: {item['balance']}\n"
                f"  Qarz: {item['debt']:,} so'm"
            )
        await callback.message.edit_text("\n\n".join(lines), parse_mode="HTML")
        await callback.answer()
    except Exception:
        logger.exception("teacher_students_group failed")
        await callback.answer("❌ O'quvchilar ro'yxati ochilmadi.", show_alert=True)


@router.message(F.text == "💵 Oylik Daromadim")
async def teacher_income(message: types.Message, state: FSMContext):
    try:
        payload = await _load_teacher_dashboard(message, state)
        if not payload:
            return
        income = payload.get("monthly_income", {})
        breakdown = "\n".join(
            f"• {item['group_name']} — {item['students']} o'quvchi / {int(item['group_total']):,} so'm"
            for item in income.get("breakdown", [])[:10]
        ) or "Bo'linma ma'lumoti yo'q."
        text = (
            "💵 <b>Joriy oy daromadi</b>\n\n"
            f"Hisoblangan maosh: <b>{income.get('expected_income', 0):,} so'm</b>\n"
            f"Faol o'quvchilar: <b>{income.get('active_students', 0)}</b>\n"
            f"To'langan summa: <b>{income.get('paid_out', 0):,} so'm</b>\n\n"
            "<b>Guruhlar kesimida:</b>\n"
            f"{breakdown}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("teacher_income failed")
        await message.answer("❌ Daromad ma'lumotini ko'rsatishda xatolik yuz berdi.")


@router.message(F.text == "📊 Statistika")
async def teacher_statistics(message: types.Message, state: FSMContext):
    try:
        payload = await _load_teacher_dashboard(message, state)
        if not payload:
            return
        stats = payload.get("statistics", {})
        text = (
            "📊 <b>Statistika</b>\n\n"
            f"Guruhlar soni: <b>{stats.get('groups_count', 0)}</b>\n"
            f"O'quvchilar soni: <b>{stats.get('students_count', 0)}</b>\n"
            f"O'rtacha davomat: <b>{stats.get('average_attendance_rate', 0)}%</b>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("teacher_statistics failed")
        await message.answer("❌ Statistikani ko'rsatishda xatolik yuz berdi.")
