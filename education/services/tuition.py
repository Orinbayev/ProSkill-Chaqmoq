# education/services/tuition.py
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional, Union

from django.db import transaction
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce
from django.utils import timezone

from education.models import TuitionMonth, PaymentAllocation, Payment, Enrollment, StudentGroupHistory


# =========================
#  SMALL HELPERS
# =========================

def _model_has_field(Model, field_name: str) -> bool:
    try:
        Model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def tuition_month_fee_field() -> str:
    """
    TuitionMonth modelida fee field nomi turlicha bo'lishi mumkin:
    - fee_amount
    - fee
    """
    return "fee_amount" if _model_has_field(TuitionMonth, "fee_amount") else "fee"


def tuition_month_fee(tm: TuitionMonth) -> int:
    field = tuition_month_fee_field()
    return int(getattr(tm, field, 0) or 0)


def set_tuition_month_fee(tm: TuitionMonth, amount: int) -> None:
    field = tuition_month_fee_field()
    setattr(tm, field, int(amount or 0))
    tm.save(update_fields=[field])


def month_first_day(d: date) -> date:
    return date(d.year, d.month, 1)


def add_month(d: date, n: int = 1) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def parse_month_str(s: str) -> Optional[date]:
    """
    'YYYY-MM' -> date(YYYY,MM,1)
    invalid -> None
    """
    if not s:
        return None
    s = s.strip()
    if len(s) != 7 or s[4] != "-":
        return None
    try:
        y = int(s[:4])
        m = int(s[5:7])
        if 1 <= m <= 12:
            return date(y, m, 1)
        return None
    except Exception:
        return None


def full_course_amount(enrollment: Enrollment) -> int:
    if not enrollment:
        return 0
    return int(getattr(enrollment, "full_course_amount", 0) or 0)


def enrollment_start_date(enrollment: Enrollment) -> date:
    if not enrollment:
        return timezone.localdate()

    history = StudentGroupHistory.objects.filter(
        student=enrollment.student,
        group=enrollment.group,
    ).order_by("-start_date").first()
    if history and history.start_date:
        return history.start_date

    start_dt = getattr(enrollment, "created_at", None) or timezone.now()
    return start_dt.date()


def effective_student_payable_amount(enrollment: Enrollment) -> int:
    if not enrollment:
        return 0
    return int(getattr(enrollment, "effective_student_payable_amount", 0) or 0)


def get_fee_amount(enrollment: Enrollment) -> int:
    """
    fee manbasi:
    - enrollment.student_payable_amount (agar berilgan bo'lsa)
    - aks holda to'liq kurs narxi
    """
    return effective_student_payable_amount(enrollment)


def _billable_attendance_q() -> Q:
    return (
        Q(status="present")
        | Q(status="absent_unexcused")
        | Q(present=True)
        | Q(forced=True)
    )


# =========================
#  PRORATED FEE CALCULATIONS
# =========================
#
# Muammo:
#   O'quvchi oy o'rtasida (masalan 18-sanada) qo'shilsa ham, TuitionMonth.fee_amount
#   to'liq oylik narxga qo'yilardi. Natijada "qarzdorlar" bo'limida yolg'on qarz paydo
#   bo'lardi (masalan 550k − 4 dars × 45.8k = 367k sun'iy qarz).
#
# Yechim:
#   1) prorated_monthly_fee()  — enrollment yaratilganda birinchi oy uchun
#      expected_lessons (GroupSchedule dan) × per_lesson narxni hisoblaydi.
#   2) reconcile_tuition_month() — oy oxirida haqiqiy davomatga qarab
#      (present + absent_unexcused) fee_amount ni qayta yozadi.
#   3) Har ikkalasi ham effective_student_payable_amount (chegirmali narx) dan
#      hisoblaydi, shuning uchun chegirma va tekin holatlar ham qamrab olinadi.
#   4) O'qituvchi maoshi bu yerda HECH qanday o'zgartirilmaydi — u alohida
#      HistoricalFinanceService orqali ASL kurs_narhi dan hisoblanadi.


def month_last_day(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def scheduled_lessons_between(group, start: date, end: date) -> int:
    """
    GroupSchedule ga qarab [start, end] oralig'ida nechta rejalashtirilgan dars
    borligini sanaydi. Jadval bo'sh bo'lsa 0 qaytaradi (fallback yuqorida).
    """
    from education.models import GroupSchedule

    if start > end:
        return 0

    weekday_counts = Counter(
        GroupSchedule.objects.filter(group=group).values_list("weekday", flat=True)
    )
    if not weekday_counts:
        return 0

    count = 0
    cur = start
    # GroupSchedule.weekday: 1=Mon .. 7=Sun (Python isoweekday bilan mos)
    while cur <= end:
        count += int(weekday_counts.get(cur.isoweekday(), 0) or 0)
        cur += timedelta(days=1)
    return count


def expected_lessons_in_period(enrollment: Enrollment, start: date, end: date) -> int:
    """
    Oralig'idagi "kutilayotgan" darslar sonini qaytaradi.
    Avval GroupSchedule dan sanaydi, bo'sh bo'lsa — oy_dars_soni ni kunlar
    nisbatiga asosan prorate qiladi (fallback).
    """
    if start > end:
        return 0

    group = enrollment.group
    scheduled = scheduled_lessons_between(group, start, end)
    if scheduled > 0:
        return scheduled

    oy_dars_soni = int(getattr(group, "oy_dars_soni", 12) or 12) or 12
    month_total_days = calendar.monthrange(start.year, start.month)[1]
    period_days = (end - start).days + 1
    ratio = min(period_days / month_total_days, 1.0)
    return max(0, round(oy_dars_soni * ratio))


def billable_attendance_count(enrollment: Enrollment, month: date) -> int:
    """
    Shu oyda hisob-kitobga kiradigan davomatlar soni:
      - status='present' yoki status='absent_unexcused' (sababsiz)
      - eski maydonlar uchun: present=True yoki forced=True
    Sababli (absent_excused) — hisoblanmaydi.
    """
    from education.models import Attendance

    month_start = month_first_day(month)
    month_end = month_last_day(month_start)

    return (
        Attendance.objects.filter(
            group=enrollment.group,
            student=enrollment.student,
            date__gte=month_start,
            date__lte=month_end,
        )
        .filter(_billable_attendance_q())
        .count()
    )


def _monthly_lessons_count(enrollment: Enrollment) -> int:
    group = enrollment.group
    monthly_lessons = int(getattr(group, "oy_dars_soni", 0) or 0) or 12
    return monthly_lessons if monthly_lessons > 0 else 12


def _prorated_monthly_fee_from_amount(
    enrollment: Enrollment,
    month: date,
    effective_price: int,
) -> int:
    month_start = month_first_day(month)
    month_end = month_last_day(month_start)

    effective_price = int(effective_price or 0)
    if effective_price <= 0:
        return 0

    monthly_lessons = _monthly_lessons_count(enrollment)
    per_lesson = effective_price / monthly_lessons
    start_date = enrollment_start_date(enrollment)

    if start_date > month_end:
        return 0
    if start_date <= month_start:
        return effective_price

    expected = expected_lessons_in_period(enrollment, start_date, month_end)
    fee = round(expected * per_lesson)
    return min(int(fee), effective_price)


def prorated_monthly_fee(enrollment: Enrollment, month: date) -> int:
    """
    Oylik to'lov summasini kutilayotgan darslarga qarab hisoblaydi.

    - To'liq oy (start_date <= oy boshi): effective_student_payable_amount
    - Qisman oy (start_date oy ichida): expected_lessons × per_lesson
    - Cap: hech qachon effective_student_payable_amount dan oshmaydi
    - Oy enrollment boshlanishidan oldin: 0 (qarz yaratilmaydi)
    """
    return _prorated_monthly_fee_from_amount(
        enrollment,
        month,
        effective_student_payable_amount(enrollment),
    )


def attendance_based_fee(enrollment: Enrollment, month: date) -> int:
    """
    Haqiqiy davomatga qarab to'lov summasini hisoblaydi (reconcile uchun).
    fee = min(billable_lessons × per_lesson, effective_student_payable_amount)
    """
    effective_price = effective_student_payable_amount(enrollment)
    if effective_price <= 0:
        return 0

    per_lesson = effective_price / _monthly_lessons_count(enrollment)

    billable = billable_attendance_count(enrollment, month)
    fee = round(billable * per_lesson)
    return min(int(fee), effective_price)


def teacher_monthly_financials(
    enrollment: Enrollment,
    billable_lessons: int,
    *,
    teacher_percent: Optional[int] = None,
) -> dict:
    """
    O'qituvchi payoutini har doim asl kurs narxidan hisoblaydi va oylik
    maksimumdan oshirmaydi.
    """
    group = getattr(enrollment, "group", None)
    monthly_lessons = int(getattr(group, "oy_dars_soni", 0) or 0) or 12
    if monthly_lessons <= 0:
        monthly_lessons = 12

    billable_lessons = max(0, int(billable_lessons or 0))
    full_amount = full_course_amount(enrollment)
    effective_percent = int(teacher_percent or 0)
    if effective_percent <= 0:
        effective_percent = int(getattr(enrollment, "oqituvchi_foiz", 0) or 0)

    if full_amount <= 0:
        return {
            "billable_lessons": billable_lessons,
            "teacher_salary": 0,
            "center_profit": 0,
            "turnover": 0,
            "teacher_salary_cap": 0,
            "turnover_cap": 0,
        }

    per_lesson_turnover = full_amount / monthly_lessons
    teacher_salary_cap = round(full_amount * effective_percent / 100)
    turnover_cap = int(full_amount)

    turnover = min(round(per_lesson_turnover * billable_lessons), turnover_cap)
    teacher_salary = min(
        round(per_lesson_turnover * (effective_percent / 100) * billable_lessons),
        teacher_salary_cap,
    )
    center_profit = turnover - teacher_salary

    return {
        "billable_lessons": billable_lessons,
        "teacher_salary": int(teacher_salary),
        "center_profit": int(center_profit),
        "turnover": int(turnover),
        "teacher_salary_cap": int(teacher_salary_cap),
        "turnover_cap": int(turnover_cap),
    }


# =========================
#  TUITION MONTH HELPERS
# =========================


def is_month_closed_for_center(center, month: date) -> bool:
    from education.models import FinancialMonth

    if not center:
        return False

    month = month_first_day(month)
    return FinancialMonth.objects.filter(
        center=center,
        year=month.year,
        month=month.month,
        is_closed=True,
    ).exists()


def get_effective_month_fee(enrollment: Enrollment, month: date) -> int:
    month = month_first_day(month)
    tm = TuitionMonth.objects.filter(enrollment=enrollment, month=month).first()
    if tm:
        return tuition_month_fee(tm)
    return int(prorated_monthly_fee(enrollment, month) or 0)

def ensure_tuition_month(enrollment: Enrollment, month: date) -> TuitionMonth:
    """
    Agar shu oy uchun TuitionMonth bo‘lmasa yaratadi.
    Fee = prorated_monthly_fee (qisman oyni hisobga oladi, cheat-proof).
    Fee 0 bo‘lib qolsa va prorated > 0 bo‘lsa -> qayta yozadi.
    """
    month = month_first_day(month)
    fee = int(prorated_monthly_fee(enrollment, month) or 0)
    fee_field = tuition_month_fee_field()

    tm, created = TuitionMonth.all_objects.get_or_create(
        enrollment=enrollment,
        month=month,
        defaults={
            "center": getattr(enrollment, "center", None),
            fee_field: fee,
        },
    )
    if not created and tm.is_deleted:
        tm.restore()

    update_fields = []
    if not getattr(tm, "center_id", None) and getattr(enrollment, "center_id", None):
        tm.center = enrollment.center
        update_fields.append("center")

    cur_fee = int(getattr(tm, fee_field, 0) or 0)
    if (
        not is_month_closed_for_center(getattr(enrollment, "center", None), month)
        and cur_fee != fee
    ):
        setattr(tm, fee_field, fee)
        update_fields.append(fee_field)

    if update_fields:
        tm.save(update_fields=update_fields)

    return tm


@transaction.atomic
def reconcile_tuition_month(enrollment: Enrollment, month: date) -> TuitionMonth:
    """
    Oy oxirida (yoki qo'lda) chaqiriladi.
    TuitionMonth.fee_amount ni haqiqiy davomatga qarab qayta hisoblaydi:
      fee = min(billable_lessons × per_lesson, effective_student_payable_amount)

    - Davomat yo'q bo'lsa (fee=0) va TuitionMonth allaqachon to'langan bo'lsa,
      fee ni pastga tushirmaymiz (ma'lumotlarni yo'qotmaslik uchun).
    - Aks holda yangi fee ni yozadi.
    """
    month_start = month_first_day(month)
    new_fee = int(attendance_based_fee(enrollment, month_start) or 0)
    fee_field = tuition_month_fee_field()

    tm, created = TuitionMonth.all_objects.get_or_create(
        enrollment=enrollment,
        month=month_start,
        defaults={
            "center": getattr(enrollment, "center", None),
            fee_field: new_fee,
        },
    )
    if not created and tm.is_deleted:
        tm.restore()

    paid = get_month_paid(tm)
    current_fee = int(getattr(tm, fee_field, 0) or 0)
    update_fields = []

    if not getattr(tm, "center_id", None) and getattr(enrollment, "center_id", None):
        tm.center = enrollment.center
        update_fields.append("center")

    # Xavfsizlik: agar hech qanday davomat yo'q va oyga to'lov qilingan bo'lsa,
    # fee ni 0 ga tushirmaymiz. Admin qo'lda tekshirishi kerak.
    if new_fee == 0 and paid > 0 and current_fee > 0:
        if update_fields:
            tm.save(update_fields=update_fields)
        return tm

    if current_fee != new_fee:
        setattr(tm, fee_field, new_fee)
        update_fields.append(fee_field)

    if update_fields:
        tm.save(update_fields=update_fields)

    return tm


def ensure_all_tuition_months_since_start(enrollment: Enrollment, up_to_month: date) -> None:
    """
    Enrollment yaratilgan kundan boshlab berilgan oygacha (up_to_month)
    barcha TuitionMonth rekordlarini yaratilishini ta'minlaydi.
    """
    cur = month_first_day(enrollment_start_date(enrollment))
    final = month_first_day(up_to_month)

    # Xavfsizlik uchun max 3 yil (36 oy)
    limit = 36
    while cur <= final and limit > 0:
        ensure_tuition_month(enrollment, cur)
        cur = add_month(cur, 1)
        limit -= 1


def get_month_paid(enrollment_or_tm: Union[Enrollment, TuitionMonth], month: Optional[date] = None) -> int:
    """
    Moslik uchun 2 xil ishlaydi:
    - get_month_paid(enrollment, month)
    - get_month_paid(tm)
    """
    if isinstance(enrollment_or_tm, TuitionMonth):
        tm = enrollment_or_tm
    else:
        if month is None:
            month = timezone.localdate()
        month = month_first_day(month)
        tm = TuitionMonth.objects.filter(enrollment=enrollment_or_tm, month=month).first()
        if not tm:
            return 0

    s = PaymentAllocation.objects.filter(tuition_month=tm).aggregate(s=Sum("amount"))["s"] or 0
    return int(s)


def find_earliest_unpaid_month(enrollment: Enrollment, start_month: Optional[date] = None) -> TuitionMonth:
    """
    Eng oldingi to‘lanmagan (paid < fee) oyni topadi.
    start_month berilsa -> o‘sha oydan boshlab qidiradi.
    """
    fee_field = tuition_month_fee_field()

    if start_month is None:
        start_month = month_first_day(enrollment_start_date(enrollment))
    else:
        start_month = month_first_day(start_month)

    ensure_tuition_month(enrollment, start_month)

    months = TuitionMonth.objects.filter(enrollment=enrollment, month__gte=start_month).order_by("month")

    for tm in months:
        fee = int(getattr(tm, fee_field, 0) or 0)
        if fee <= 0:
            continue
        paid = get_month_paid(tm)
        if paid < fee:
            return tm

    last = months.last()
    next_m = add_month(last.month, 1) if last else start_month
    return ensure_tuition_month(enrollment, next_m)


def sync_tuition_fee(enrollment: Enrollment, start_month: date, new_fee: int) -> None:
    """
    enrollment kurs narhi o'zgarsa, shu oydan boshlab TuitionMonth fee larni yangilaydi.
    fee field nomi fee_amount yoki fee bo'lishi mumkin.
    """
    start_month = month_first_day(start_month)
    fee_field = tuition_month_fee_field()
    effective_amount = int(
        new_fee if new_fee is not None else effective_student_payable_amount(enrollment) or 0
    )

    existing_months = list(
        TuitionMonth.all_objects.filter(enrollment=enrollment, month__gte=start_month).order_by("month")
    )

    for tm in existing_months:
        if tm.is_deleted:
            tm.restore()
        target_fee = int(
            _prorated_monthly_fee_from_amount(enrollment, tm.month, effective_amount) or 0
        )
        update_fields = []
        if int(getattr(tm, fee_field, 0) or 0) != target_fee:
            setattr(tm, fee_field, target_fee)
            update_fields.append(fee_field)
        if not getattr(tm, "center_id", None) and getattr(enrollment, "center_id", None):
            tm.center = enrollment.center
            update_fields.append("center")
        if update_fields:
            tm.save(update_fields=update_fields)

    TuitionMonth.all_objects.update_or_create(
        enrollment=enrollment,
        month=start_month,
        defaults={
            "center": getattr(enrollment, "center", None),
            fee_field: int(
                _prorated_monthly_fee_from_amount(enrollment, start_month, effective_amount) or 0
            ),
        },
    )


# =========================
#  CORE ALLOCATION ENGINE
# =========================

def _get_payment_card_amount(p: Payment) -> int:
    if _model_has_field(Payment, "card_amount_som"):
        return int(getattr(p, "card_amount_som", 0) or 0)
    return int(getattr(p, "card_amount", 0) or 0)


def infer_payment_type(cash_amount: int, card_amount_som: int) -> str:
    cash_amount = int(cash_amount or 0)
    card_amount_som = int(card_amount_som or 0)
    if cash_amount > 0 and card_amount_som > 0:
        return "mixed"
    if card_amount_som > 0:
        return "card"
    return "cash"


def _set_payment_amounts(p: Payment, cash_amount: int, card_amount_som: int, total: int) -> None:
    update_fields = []

    if _model_has_field(Payment, "cash_amount"):
        p.cash_amount = int(cash_amount or 0)
        update_fields.append("cash_amount")

    if _model_has_field(Payment, "card_amount_som"):
        p.card_amount_som = int(card_amount_som or 0)
        update_fields.append("card_amount_som")
    elif _model_has_field(Payment, "card_amount"):
        p.card_amount = int(card_amount_som or 0)
        update_fields.append("card_amount")

    if _model_has_field(Payment, "summa"):
        p.summa = int(total or 0)
        update_fields.append("summa")

    if _model_has_field(Payment, "payment_type"):
        p.payment_type = infer_payment_type(cash_amount, card_amount_som)
        update_fields.append("payment_type")

    if update_fields:
        p.save(update_fields=update_fields)


def _allocate_amount_forward(*, enrollment: Enrollment, payment: Payment, amount: int, start_month: date) -> None:
    """
    ✅ [FIX] Faqat START_MONTH (joriy oy) uchun to'lovni yozamiz.
    Ortiqcha pul bo'lsa ham kelajak oylarga tarqatilmaydi - hammasi shu oyga yoziladi.
    Bu 'APREL 2026, MAY 2026' kabi ko'p oylar muammosini hal qiladi.
    """
    amount = int(amount or 0)
    if amount <= 0:
        return

    cur = month_first_day(start_month)

    # Faqat joriy oy uchun TuitionMonth olamiz (yaratmaymiz agar yo'q bo'lsa)
    tm = TuitionMonth.objects.filter(enrollment=enrollment, month=cur).first()
    if tm is None:
        # Agar joriy oy uchun TuitionMonth yo'q bo'lsa, yangi yaratamiz
        tm = ensure_tuition_month(enrollment, cur)

    # Hammasini shu oyga yozamiz (ortiqcha bo'lsa ham)
    if amount > 0:
        PaymentAllocation.objects.create(
            center=getattr(payment, "center", None) or getattr(enrollment, "center", None),
            payment=payment,
            tuition_month=tm,
            amount=amount,
        )



# =========================
#  CREATE PAYMENT + ALLOCATE
# =========================

@transaction.atomic
def create_payment_and_allocate(
    *,
    enrollment: Enrollment,
    created_by=None,
    cash_amount: int,
    card_amount_som: int,
    start_month: Optional[date] = None,
    paid_at=None,
    note: str = "",
    payment_type: Optional[str] = None,
) -> Payment:
    """
    Payment yaratadi va pullarni oylar bo‘yicha taqsimlaydi:
    - start_month berilsa: o‘sha oydan boshlab ketma-ket taqsimlaydi
    - start_month bo‘lmasa: joriy oy (oy boshidan) boshlab
    """
    cash_amount = int(cash_amount or 0)
    card_amount_som = int(card_amount_som or 0)
    total = cash_amount + card_amount_som
    if total <= 0:
        raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas")

    if paid_at is None:
        paid_at = timezone.now()
    elif isinstance(paid_at, date) and not isinstance(paid_at, datetime):
        paid_at = datetime.combine(paid_at, datetime.min.time())

    if timezone.is_naive(paid_at):
        paid_at = timezone.make_aware(paid_at, timezone.get_current_timezone())

    local_paid_at = timezone.localtime(paid_at)

    if start_month is None:
        tm_earliest = find_earliest_unpaid_month(enrollment)
        start_month = tm_earliest.month
    else:
        start_month = month_first_day(start_month)

    # Payment CREATE (robust)
    kwargs = {}

    if _model_has_field(Payment, "enrollment"):
        kwargs["enrollment"] = enrollment
    if _model_has_field(Payment, "student"):
        kwargs["student"] = enrollment.student
    if _model_has_field(Payment, "group"):
        kwargs["group"] = enrollment.group

    if _model_has_field(Payment, "cash_amount"):
        kwargs["cash_amount"] = cash_amount

    if _model_has_field(Payment, "card_amount_som"):
        kwargs["card_amount_som"] = card_amount_som
    elif _model_has_field(Payment, "card_amount"):
        kwargs["card_amount"] = card_amount_som

    if _model_has_field(Payment, "summa"):
        kwargs["summa"] = total

    if _model_has_field(Payment, "payment_type"):
        kwargs["payment_type"] = payment_type or infer_payment_type(cash_amount, card_amount_som)

    if _model_has_field(Payment, "paid_at"):
        kwargs["paid_at"] = local_paid_at
    else:
        if _model_has_field(Payment, "paid_date"):
            kwargs["paid_date"] = local_paid_at.date()
        if _model_has_field(Payment, "paid_time"):
            kwargs["paid_time"] = local_paid_at.time().replace(microsecond=0)
        if _model_has_field(Payment, "sana"):
            kwargs["sana"] = local_paid_at.date()
        if _model_has_field(Payment, "vaqt"):
            kwargs["vaqt"] = local_paid_at.time().replace(microsecond=0)

    if created_by and _model_has_field(Payment, "created_by"):
        kwargs["created_by"] = created_by

    if _model_has_field(Payment, "note"):
        kwargs["note"] = note

    payment = Payment.objects.create(**kwargs)

    _allocate_amount_forward(enrollment=enrollment, payment=payment, amount=total, start_month=start_month)

    return payment


# =========================
#  UPDATE PAYMENT + REALLOCATE
# =========================

@transaction.atomic
def update_payment_and_reallocate(
    *,
    payment: Payment,
    cash_amount: int,
    card_amount_som: int,
    start_month: Optional[date] = None
) -> Payment:
    """
    Payment summalarini yangilaydi va allocation'larini qayta taqsimlaydi.
    start_month:
      - berilsa: shu oydan boshlab forward allocate
      - berilmasa: eng oldingi unpaid oydan boshlab
    """
    enrollment = getattr(payment, "enrollment", None)
    if not enrollment:
        raise ValueError("Payment.enrollment topilmadi (modelda enrollment FK bo‘lishi kerak).")

    cash_amount = int(cash_amount or 0)
    card_amount_som = int(card_amount_som or 0)
    new_total = cash_amount + card_amount_som
    if new_total <= 0:
        raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas")

    old_total = int(getattr(payment, "summa", 0) or (_get_payment_card_amount(payment) + int(getattr(payment, "cash_amount", 0) or 0)))

    # 1) Paymentni update
    _set_payment_amounts(payment, cash_amount, card_amount_som, new_total)

    # 2) Shu payment allocationlarini o'chiramiz
    PaymentAllocation.objects.filter(payment=payment).delete()

    # 3) start_month tanlash
    if start_month is not None:
        start_month = month_first_day(start_month)
    else:
        # eng oldingi unpaid oydan boshlaymiz (yaxshiroq)
        first_tm = TuitionMonth.objects.filter(enrollment=enrollment).order_by("month").first()
        base = first_tm.month if first_tm else month_first_day(timezone.localdate())
        start_month = find_earliest_unpaid_month(enrollment, start_month=base).month

    # 4) allocate
    _allocate_amount_forward(enrollment=enrollment, payment=payment, amount=new_total, start_month=start_month)

    return payment


# =========================
#  FULL REALLOCATE (optional)
# =========================

@transaction.atomic
def reallocate_enrollment(enrollment: Enrollment) -> None:
    """
    Enrollment bo‘yicha hamma PaymentAllocation’larni 0 dan qayta hisoblaydi.
    Paymentlar ketma-ket (eskidan yangiga) yurib chiqiladi va allocation qayta taqsimlanadi.
    """
    # Payment modelida enrollment bo'lishi kutiladi. Bo'lmasa fallback qilish mumkin.
    if not _model_has_field(Payment, "enrollment"):
        raise ValueError("Payment modelida enrollment field yo'q, reallocate_enrollment ishlamaydi.")

    PaymentAllocation.objects.filter(payment__enrollment=enrollment).delete()

    payment_fields = {f.name for f in Payment._meta.get_fields()}
    order_by = ["id"]
    if "paid_at" in payment_fields:
        order_by = ["paid_at", "id"]
    elif "sana" in payment_fields and "vaqt" in payment_fields:
        order_by = ["sana", "vaqt", "id"]
    elif "created_at" in payment_fields:
        order_by = ["created_at", "id"]

    payments = Payment.objects.filter(enrollment=enrollment).order_by(*order_by)

    # hech bo‘lmasa current oy mavjud bo‘lsin
    ensure_tuition_month(enrollment, timezone.localdate())

    for p in payments:
        cash = int(getattr(p, "cash_amount", 0) or 0)
        card = _get_payment_card_amount(p)
        total = cash + card
        if total <= 0:
            continue

        # unpaid oylar bo'yicha taqsimlash
    # eng birinchi oydan boshlab to'g'ri hisoblash
        first_tm = TuitionMonth.objects.filter(enrollment=enrollment).order_by("month").first()
        base = first_tm.month if first_tm else month_first_day(timezone.localdate())

        tm = find_earliest_unpaid_month(enrollment, start_month=base)
        _allocate_amount_forward(enrollment=enrollment, payment=p, amount=total, start_month=tm.month)
