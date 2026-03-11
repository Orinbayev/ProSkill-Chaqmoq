"""
chaqmoq/services.py

Rule Engine  — Davomat jarimasi va To'lov bonusi uchun.
Notification — O'quvchiga xabar yuborish.

Har doim mavjud kodni buzmaydi, faqat qo'shimcha logika qo'shiladi.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from chaqmoq.models import Rule, Ledger

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. NOTIFICATION SERVICE
# ─────────────────────────────────────────────────────────────────────────────

def send_notification(*, recipient, title: str, message: str,
                      notification_type: str = 'coin',
                      center=None, sender=None) -> None:
    """
    O'quvchiga (yoki istalgan foydalanuvchiga) notification yuboradi.
    core.models.Notification jadvalidan foydalanadi.
    """
    try:
        from core.models import Notification
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            center=center,
            title=title,
            message=message,
            type=notification_type,
        )
    except Exception as exc:
        logger.warning("Notification yuborishda xato: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# 2. RULE ENGINE — DAVOMAT JARIMASI (attendance_penalty)
# ─────────────────────────────────────────────────────────────────────────────

def check_attendance_penalty(*, student, center, created_by=None, target_date=None) -> bool:
    """
    Belgilangan target_date (default: bugun) bo'yicha oy ichidagi jarimani tekshiradi.
    """
    from education.models import Attendance

    rules = Rule.objects.filter(
        tur=Rule.ATTENDANCE_PENALTY,
    ).filter(
        Q(center=center) | Q(center__isnull=True)
    )

    penalized = False
    now = target_date or timezone.localdate()

    for rule in rules:
        if not rule.absence_limit or not rule.lightning_penalty:
            continue

        # Periodni hisoblash (faqat monthly qo'llab-quvvatlanadi hozircha)
        if rule.period == 'monthly':
            period_start = now.replace(day=1)
            period_end = (period_start.replace(month=period_start.month % 12 + 1)
                          if period_start.month < 12
                          else period_start.replace(year=period_start.year + 1, month=1))
        else:
            continue

        # Joriy oy sababsiz yo'qliklar soni
        unexcused_count = Attendance.objects.filter(
            student=student,
            status='absent_unexcused',
            date__gte=period_start,
            date__lt=period_end,
        ).count()

        if center:
            unexcused_count = Attendance.objects.filter(
                student=student,
                center=center,
                status='absent_unexcused',
                date__gte=period_start,
                date__lt=period_end,
            ).count()

        if unexcused_count < rule.absence_limit:
            continue

        # Bu oy uchun allaqachon jarima qo'yilganmi? (takrorlanmasin)
        already_penalized = Ledger.objects.filter(
            student=student,
            rule=rule,
            sana__date__gte=period_start,
            sana__date__lt=period_end,
        ).exists()

        if already_penalized:
            continue

        # Ledger yozuvi yaratish
        penalty = rule.lightning_penalty  # manfiy son
        with transaction.atomic():
            Ledger.objects.create(
                student=student,
                beruvchi=created_by,
                rule=rule,
                ball=penalty,
                sana=timezone.now(),
                group=None,
            )

            # Notification
            send_notification(
                recipient=student,
                center=center,
                title="⚡ Chaqmoq ayirildi",
                message=(
                    f"Siz {now.strftime('%Y-%yil %B oy')} ichida "
                    f"{rule.absence_limit} ta sababsiz dars qoldirganingiz uchun "
                    f"{abs(penalty)} ta chaqmoq ayirildi."
                ),
                notification_type='coin',
                sender=created_by,
            )

        logger.info(
            "Attendance penalty applied: student=%s, rule=%s, ball=%s",
            student, rule, penalty,
        )
        penalized = True

    return penalized


# ─────────────────────────────────────────────────────────────────────────────
# 3. RULE ENGINE — DAVOMAT BONUSI (attendance_bonus)
# ─────────────────────────────────────────────────────────────────────────────

def check_attendance_bonus(*, student, center, created_by=None, target_date=None) -> bool:
    """
    Belgilangan target_date bo'yicha davomat bonusini tekshiradi.
    """
    from education.models import Attendance

    rules = Rule.objects.filter(
        tur=Rule.ATTENDANCE_BONUS,
    ).filter(
        Q(center=center) | Q(center__isnull=True)
    )

    bonused = False
    now = target_date or timezone.localdate()

    for rule in rules:
        if not rule.presence_limit or not rule.lightning_bonus:
            continue

        if rule.period == 'monthly':
            period_start = now.replace(day=1)
            period_end = (period_start.replace(month=period_start.month % 12 + 1)
                          if period_start.month < 12
                          else period_start.replace(year=period_start.year + 1, month=1))
        else:
            continue

        # Joriy oy davomida kelgan darslar soni (present=True)
        q_filter = Q(student=student, present=True, date__gte=period_start, date__lt=period_end)
        if center:
            q_filter &= Q(center=center)
        
        presence_count = Attendance.objects.filter(q_filter).count()

        if presence_count < rule.presence_limit:
            continue

        # Allaqachon bonus berilganmi?
        already = Ledger.objects.filter(
            student=student,
            rule=rule,
            sana__date__gte=period_start,
            sana__date__lt=period_end,
        ).exists()

        if already:
            continue

        bonus = rule.lightning_bonus
        with transaction.atomic():
            Ledger.objects.create(
                student=student,
                beruvchi=created_by,
                rule=rule,
                ball=bonus,
                sana=timezone.now(),
                group=None,
            )

            send_notification(
                recipient=student,
                center=center,
                title="🔥 Faollik bonusi!",
                message=(
                    f"Siz {now.strftime('%B')} oyida {presence_count} ta darsda "
                    f"qatnashganingiz uchun +{bonus} ta chaqmoq bilan taqdirlandingiz! 🔥"
                ),
                notification_type='coin',
                sender=created_by,
            )

        logger.info("Attendance bonus applied: student=%s, rule=%s, ball=%s", student, rule, bonus)
        bonused = True

    return bonused


# ─────────────────────────────────────────────────────────────────────────────
# 3. PAYMENT TRIGGER — TO'LOV BONUSI (payment_bonus)
# ─────────────────────────────────────────────────────────────────────────────

def check_payment_bonus(*, enrollment, center, created_by=None) -> bool:
    """
    Enrollment to'lovi 100% bo'lganda chaqiriladi.

    Mantig'i:
      - center da Rule.tur == 'payment_bonus' bo'lgan qoidalar olinadi
      - Enrollment da jami_tolangan >= kurs_narhi bo'lsa = 100%
      - Agar bu oy için bonus allaqachon berilmagan bo'lsa — Ledger yaratiladi
      - Notification yuboriladi

    Qaytaradi: True agar bonus qo'yildi, False aks holda.
    """
    rules = Rule.objects.filter(
        tur=Rule.PAYMENT_BONUS,
    ).filter(
        Q(center=center) | Q(center__isnull=True)
    )

    if not rules.exists():
        return False

    # 100% to'lovni tekshirish
    fee = enrollment.kurs_narhi or 0
    paid = enrollment.jami_tolangan or 0

    if fee <= 0 or paid < fee:
        return False

    student = enrollment.student
    now = timezone.localdate()
    period_start = now.replace(day=1)

    bonused = False

    for rule in rules:
        bonus = rule.payment_bonus_lightning
        if not bonus or bonus <= 0:
            continue

        # Bu oy uchun allaqachon bonus berilib bo'lganmi?
        already = Ledger.objects.filter(
            student=student,
            rule=rule,
            sana__date__gte=period_start,
        ).exists()

        if already:
            continue

        with transaction.atomic():
            Ledger.objects.create(
                student=student,
                beruvchi=created_by,
                rule=rule,
                ball=bonus,
                sana=timezone.now(),
                group=enrollment.group,
            )

            send_notification(
                recipient=student,
                center=center,
                title="⚡ Bonus chaqmoq qo'shildi",
                message=(
                    f"Oylik to'lovni to'liq amalga oshirganingiz uchun "
                    f"+{bonus} ta chaqmoq qo'shildi! 🎉"
                ),
                notification_type='coin',
                sender=created_by,
            )

        logger.info(
            "Payment bonus applied: student=%s, rule=%s, ball=%s",
            student, rule, bonus,
        )
        bonused = True

    return bonused
