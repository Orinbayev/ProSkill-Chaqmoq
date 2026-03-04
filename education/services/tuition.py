# education/services/tuition.py
from __future__ import annotations

from datetime import date
from typing import Optional, Union

from django.db import transaction
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.utils import timezone

from education.models import TuitionMonth, PaymentAllocation, Payment, Enrollment


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


def get_fee_amount(enrollment: Enrollment) -> int:
    """
    fee manbasi:
    - enrollment.kurs_narhi (eng ustun)
    - group.kurs_narxi yoki group.kurs_narhi (fallback)
    """
    enr_fee = getattr(enrollment, "kurs_narhi", None)
    if enr_fee not in (None, ""):
        return int(enr_fee or 0)

    g = getattr(enrollment, "group", None)
    if not g:
        return 0

    return int(getattr(g, "kurs_narxi", 0) or getattr(g, "kurs_narhi", 0) or 0)


# =========================
#  TUITION MONTH HELPERS
# =========================

def ensure_tuition_month(enrollment: Enrollment, month: date) -> TuitionMonth:
    """
    Agar shu oy uchun TuitionMonth bo‘lmasa yaratadi.
    Fee 0 bo‘lib qolsa -> enrollment/groupdan qayta yozadi.
    """
    month = month_first_day(month)
    fee = int(get_fee_amount(enrollment) or 0)
    fee_field = tuition_month_fee_field()

    tm, _ = TuitionMonth.objects.get_or_create(
        enrollment=enrollment,
        month=month,
        defaults={fee_field: fee},
    )

    cur_fee = int(getattr(tm, fee_field, 0) or 0)
    if cur_fee <= 0 and fee > 0:
        setattr(tm, fee_field, fee)
        tm.save(update_fields=[fee_field])

    return tm


def ensure_all_tuition_months_since_start(enrollment: Enrollment, up_to_month: date) -> None:
    """
    Enrollment yaratilgan kundan boshlab berilgan oygacha (up_to_month)
    barcha TuitionMonth rekordlarini yaratilishini ta'minlaydi.
    """
    start_dt = getattr(enrollment, "created_at", None) or timezone.now()
    cur = month_first_day(start_dt.date())
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
        start_dt = getattr(enrollment, "created_at", None) or timezone.now()
        start_month = month_first_day(start_dt.date())
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
    new_fee = int(new_fee or 0)

    TuitionMonth.objects.filter(enrollment=enrollment, month__gte=start_month).update(**{fee_field: new_fee})
    TuitionMonth.objects.update_or_create(
        enrollment=enrollment,
        month=start_month,
        defaults={fee_field: new_fee},
    )


# =========================
#  CORE ALLOCATION ENGINE
# =========================

def _get_payment_card_amount(p: Payment) -> int:
    if _model_has_field(Payment, "card_amount_som"):
        return int(getattr(p, "card_amount_som", 0) or 0)
    return int(getattr(p, "card_amount", 0) or 0)


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

    fee_field = tuition_month_fee_field()
    cur = month_first_day(start_month)

    # Faqat joriy oy uchun TuitionMonth olamiz (yaratmaymiz agar yo'q bo'lsa)
    tm = TuitionMonth.objects.filter(enrollment=enrollment, month=cur).first()
    if tm is None:
        # Agar joriy oy uchun TuitionMonth yo'q bo'lsa, yangi yaratamiz
        tm = ensure_tuition_month(enrollment, cur)

    # Hammasini shu oyga yozamiz (ortiqcha bo'lsa ham)
    if amount > 0:
        PaymentAllocation.objects.create(payment=payment, tuition_month=tm, amount=amount)



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
    note: str = ""
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

    if _model_has_field(Payment, "paid_at"):
        kwargs["paid_at"] = paid_at
    else:
        if _model_has_field(Payment, "sana"):
            kwargs["sana"] = timezone.localdate()
        if _model_has_field(Payment, "vaqt"):
            kwargs["vaqt"] = timezone.localtime().time()

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
