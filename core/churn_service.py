"""
Churn Prediction Service — O'quvchi ketish xavfini baholash.

Risk ball hisoblash omillari (jami 100 ball):
  1. Davomat    (0–40 ball) — so'nggi 30 kunlik davomat foizi
  2. To'lov     (0–30 ball) — joriy oyda to'lov holati
  3. Ketma-ket  (0–20 ball) — ketma-ket yo'qlamalar soni
  4. Chaqmoq    (0–10 ball) — so'nggi 2 haftadagi ball trendi

Xavf darajalari:
  HIGH   (70–100) — shoshilinch e'tibor talab qiladi
  MEDIUM (40–69)  — kuzatuvda saqlash
  LOW    (0–39)   — normal holat
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db.models import Count, Q, Sum
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import Center, User


# ─────────────────────────────────────────────
# Ball chegaralari
# ─────────────────────────────────────────────
RISK_HIGH   = 70
RISK_MEDIUM = 40

MONTHLY_LESSONS = 12   # bir oyda o'rtacha dars soni


def _att_score(att_pct: int) -> tuple[int, str | None]:
    """Davomat foizidan xavf balli va sabab qaytaradi."""
    if att_pct < 30:
        return 40, f"Davomat juda past ({att_pct}%)"
    if att_pct < 50:
        return 30, f"Davomat past ({att_pct}%)"
    if att_pct < 70:
        return 15, f"Davomat o'rtacha ({att_pct}%)"
    return 0, None


def _payment_score(student, center, today) -> tuple[int, str | None, int]:
    """To'lov holatidan xavf balli, sabab va qarz summasi."""
    from education.models import Enrollment

    debt = 0
    enr = (
        Enrollment.objects
        .filter(student=student, center=center, is_active=True)
        .select_related('group')
        .first()
    )
    if not enr:
        return 0, None, 0

    kurs_narhi = enr.kurs_narhi or 0
    tolangan   = enr.jami_tolangan or 0
    debt       = max(0, kurs_narhi - tolangan)

    if debt == 0:
        return 0, None, 0
    if debt >= kurs_narhi:
        return 30, f"To'lov to'liq amalga oshirilmagan ({debt:,} so'm qarz)", debt
    return 15, f"Qisman to'lov ({debt:,} so'm qarz)", debt


def _consecutive_score(student, center, today) -> tuple[int, str | None]:
    """Ketma-ket yo'qlamalardan xavf balli."""
    from education.models import Attendance

    last_14 = today - timedelta(days=14)
    records = (
        Attendance.objects
        .filter(student=student, center=center, date__gte=last_14)
        .order_by('-date')
        .values_list('present', 'forced', flat=False)
    )

    streak = 0
    for present, forced in records:
        if present or forced:
            break
        streak += 1

    if streak >= 10:
        return 20, f"{streak} kun ketma-ket kelmagan"
    if streak >= 6:
        return 12, f"{streak} kun ketma-ket kelmagan"
    if streak >= 3:
        return 6, f"{streak} kun ketma-ket kelmagan"
    return 0, None


def _chaqmoq_score(student, center, today) -> tuple[int, str | None]:
    """Chaqmoq ball trendidan xavf balli."""
    try:
        from chaqmoq.models import Ledger
    except ImportError:
        return 0, None

    last_14  = today - timedelta(days=14)
    prev_14  = last_14 - timedelta(days=14)

    recent = (
        Ledger.objects
        .filter(student=student, sana__date__gte=last_14)
        .aggregate(s=Sum('ball'))['s'] or 0
    )
    previous = (
        Ledger.objects
        .filter(student=student, sana__date__gte=prev_14, sana__date__lt=last_14)
        .aggregate(s=Sum('ball'))['s'] or 0
    )

    if previous > 0 and recent < (previous * 0.3):
        return 10, "Chaqmoq ballari keskin kamaygan"
    if previous > 0 and recent == 0:
        return 6, "So'nggi 2 haftada chaqmoq bali yo'q"
    return 0, None


# ─────────────────────────────────────────────
# Asosiy baholash funksiyasi
# ─────────────────────────────────────────────

def assess_student(student, center, today=None) -> dict:
    """
    Bitta o'quvchi uchun to'liq risk baholash.
    Returns: {risk_level, risk_score, reasons, att_pct, debt_amount}
    """
    if today is None:
        today = timezone.localtime(timezone.now()).date()

    thirty_ago = today - timedelta(days=30)

    # --- Davomat ---
    from education.models import Attendance
    att_count = Attendance.objects.filter(
        student=student, center=center,
        date__gte=thirty_ago,
    ).filter(Q(present=True) | Q(forced=True)).count()

    att_pct = min(100, round((att_count / MONTHLY_LESSONS) * 100))

    score   = 0
    reasons = []

    s, r = _att_score(att_pct)
    score += s
    if r:
        reasons.append(r)

    s, r, debt = _payment_score(student, center, today)
    score += s
    if r:
        reasons.append(r)

    s, r = _consecutive_score(student, center, today)
    score += s
    if r:
        reasons.append(r)

    s, r = _chaqmoq_score(student, center, today)
    score += s
    if r:
        reasons.append(r)

    score = min(100, score)

    if score >= RISK_HIGH:
        level = 'high'
    elif score >= RISK_MEDIUM:
        level = 'medium'
    else:
        level = 'low'

    return {
        'risk_level':  level,
        'risk_score':  score,
        'reasons':     reasons,
        'att_pct':     att_pct,
        'debt_amount': debt,
    }


# ─────────────────────────────────────────────
# Markaz bo'yicha to'liq yangilash
# ─────────────────────────────────────────────

def run_churn_assessment(center, notify_managers: bool = True) -> int:
    """
    Markazdagi barcha faol o'quvchilarni baholab, ChurnRisk jadvalini yangilaydi.
    Yangi HIGH/MEDIUM topilsa menejerga notification yuboradi.
    Qaytaradi: baholangan o'quvchilar soni.
    """
    from accounts.models import User
    from core.models import ChurnRisk, Notification

    today     = timezone.localtime(timezone.now()).date()
    students  = User.objects.filter(center=center, role='student', is_archived=False)
    managers  = list(User.objects.filter(center=center, role__in=('manager', 'director')))

    count = 0
    for student in students:
        data = assess_student(student, center, today)

        obj, created = ChurnRisk.objects.update_or_create(
            center=center,
            student=student,
            defaults={
                'risk_level':  data['risk_level'],
                'risk_score':  data['risk_score'],
                'reasons':     data['reasons'],
                'att_pct':     data['att_pct'],
                'debt_amount': data['debt_amount'],
            },
        )

        # Notification: yangi HIGH/MEDIUM va hali xabar yuborilmagan bo'lsa
        should_notify = (
            notify_managers
            and data['risk_level'] in ('high', 'medium')
            and (created or not obj.notified)
        )
        if should_notify and managers:
            level_label = "YUQORI XAVF" if data['risk_level'] == 'high' else "O'RTA XAVF"
            reasons_str  = " | ".join(data['reasons']) if data['reasons'] else "Kam faollik"
            title   = f"Ketish xavfi: {student.get_full_name()} [{level_label}]"
            message = f"Ball: {data['risk_score']}/100 · {reasons_str}"

            for mgr in managers:
                Notification.objects.create(
                    center    = center,
                    recipient = mgr,
                    title     = title,
                    message   = message,
                    type      = 'system',
                )

            ChurnRisk.objects.filter(pk=obj.pk).update(
                notified    = True,
                notified_at = timezone.now(),
            )

        count += 1

    return count
