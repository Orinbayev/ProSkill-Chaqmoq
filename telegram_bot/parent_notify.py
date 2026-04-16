from __future__ import annotations

from accounts.utils_bot import send_telegram_message
from core.dashboard_metrics import get_enrollment_month_debt, month_start


def notify_payment_due(enrollment):
    """
    Oyning 5-sanasida — to'lamagan o'quvchilarning ota-onasiga yuboriladi.
    """
    student = enrollment.student
    parent = student.parents.first()
    if not parent or not parent.telegram_id:
        return False

    debt = get_enrollment_month_debt(enrollment, month_start())
    if debt <= 0:
        return False

    center = enrollment.center or enrollment.group.center
    center_phone = getattr(center, "phone", "") or "Markaz telefoni ko'rsatilmagan"
    text = (
        f"👋 Hurmatli {parent.get_full_name()}!\n\n"
        f"📚 Farzandingiz *{student.get_full_name()}* uchun\n"
        f"{enrollment.group.nom} guruhida bu oylik to'lov amalga oshirilmagan.\n\n"
        f"💰 To'lov summasi: *{debt:,} so'm*\n\n"
        "Iltimos, imkon qadar tez to'lov qiling.\n"
        f"📞 {center_phone}"
    )
    return send_telegram_message(parent.telegram_id, text)


def notify_low_attendance(enrollment, attended, total):
    """
    Davomat 60% dan pastga tushsa yuboriladi.
    """
    pct = round(attended * 100 / total) if total else 0
    if pct >= 60:
        return False

    student = enrollment.student
    parent = student.parents.first()
    if not parent or not parent.telegram_id:
        return False

    center = enrollment.center or enrollment.group.center
    center_phone = getattr(center, "phone", "") or "Markaz telefoni ko'rsatilmagan"
    text = (
        f"👋 Hurmatli {parent.get_full_name()}!\n\n"
        f"📉 Farzandingiz *{student.get_full_name()}* ning {enrollment.group.nom} guruhidagi "
        f"so'nggi davomat ko'rsatkichi *{pct}%* ni tashkil qildi.\n"
        f"📊 Hisob: *{attended}/{total}*\n\n"
        "Iltimos, davomad bo'yicha farzandingiz bilan gaplashing.\n"
        f"📞 {center_phone}"
    )
    return send_telegram_message(parent.telegram_id, text)
