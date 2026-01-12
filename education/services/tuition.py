# C:\Users\user\Desktop\chaqmoq_academy\education\services\tuition.py
from __future__ import annotations

from datetime import date
from typing import Optional, Union

from django.db import transaction
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db import transaction
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


def _tm_fee_field() -> str:
    # Sizda TuitionMonth.da fee_amount bo‘lishi mumkin, ba’zida fee bo‘ladi
    return "fee_amount" if _model_has_field(TuitionMonth, "fee_amount") else "fee"


def month_first_day(d: date) -> date:
    return date(d.year, d.month, 1)


def add_month(d: date, n: int = 1) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


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
    fee 0 bo‘lib qolsa -> enrollment/groupdan qayta yozadi.
    """
    month = month_first_day(month)
    fee_field = _tm_fee_field()
    fee = get_fee_amount(enrollment)

    defaults = {fee_field: int(fee)}
    tm, _ = TuitionMonth.objects.get_or_create(
        enrollment=enrollment,
        month=month,
        defaults=defaults
    )

    # fee 0 bo‘lib qolsa fallback bilan update
    cur_fee = int(getattr(tm, fee_field, 0) or 0)
    if cur_fee <= 0 and fee > 0:
        setattr(tm, fee_field, int(fee))
        tm.save(update_fields=[fee_field])

    return tm


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

    s = (
        PaymentAllocation.objects
        .filter(tuition_month=tm)
        .aggregate(s=Sum("amount"))["s"] or 0
    )
    return int(s)


def find_earliest_unpaid_month(enrollment: Enrollment, start_month: Optional[date] = None) -> TuitionMonth:
    """
    Eng oldingi to‘lanmagan (paid < fee) oyni topadi.
    start_month berilsa -> o‘sha oydan boshlab qidiradi.
    """
    fee_field = _tm_fee_field()

    if start_month is None:
        start_month = month_first_day(timezone.localdate())
    else:
        start_month = month_first_day(start_month)

    # start_month kamida mavjud bo‘lsin
    ensure_tuition_month(enrollment, start_month)

    months = TuitionMonth.objects.filter(enrollment=enrollment, month__gte=start_month).order_by("month")

    for tm in months:
        fee = int(getattr(tm, fee_field, 0) or 0)
        if fee <= 0:
            continue
        paid = get_month_paid(tm)
        if paid < fee:
            return tm

    # hammasi yopilgan bo‘lsa -> keyingi oy
    last = months.last()
    next_m = add_month(last.month, 1) if last else start_month
    return ensure_tuition_month(enrollment, next_m)


# =========================
#  CREATE PAYMENT + ALLOCATE
# =========================

@transaction.atomic
def create_payment_and_allocate(
    *,
    enrollment: Enrollment,
    created_by,
    cash_amount: int,
    card_amount: int,
    start_month: Optional[date] = None,
    paid_at=None
) -> Payment:
    """
    Payment yaratadi va pullarni oylar bo‘yicha taqsimlaydi:
    - start_month berilsa: o‘sha oydan boshlab ketma-ket taqsimlaydi
    - start_month bo‘lmasa: joriy oy (oy boshidan) boshlab
    """

    cash_amount = int(cash_amount or 0)
    card_amount = int(card_amount or 0)
    total = cash_amount + card_amount
    if total <= 0:
        raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas")

    if paid_at is None:
        paid_at = timezone.now()

    if start_month is None:
        start_month = month_first_day(timezone.localdate())
    else:
        start_month = month_first_day(start_month)

    # -------------------------
    # Payment CREATE (robust)
    # -------------------------
    kwargs = {}

    if _model_has_field(Payment, "enrollment"):
        kwargs["enrollment"] = enrollment
    if _model_has_field(Payment, "student"):
        kwargs["student"] = enrollment.student
    if _model_has_field(Payment, "group"):
        kwargs["group"] = enrollment.group

    if _model_has_field(Payment, "cash_amount"):
        kwargs["cash_amount"] = cash_amount

    # card maydon nomlari turlicha bo‘lishi mumkin
    if _model_has_field(Payment, "card_amount_som"):
        kwargs["card_amount_som"] = card_amount
    elif _model_has_field(Payment, "card_amount"):
        kwargs["card_amount"] = card_amount

    if _model_has_field(Payment, "summa"):
        kwargs["summa"] = total

    # vaqt fieldlari
    if _model_has_field(Payment, "paid_at"):
        kwargs["paid_at"] = paid_at
    else:
        # eski loyihalarda sana/vaqt bo‘ladi
        if _model_has_field(Payment, "sana"):
            kwargs["sana"] = timezone.localdate()
        if _model_has_field(Payment, "vaqt"):
            kwargs["vaqt"] = timezone.localtime().time()

    if created_by and _model_has_field(Payment, "created_by"):
        kwargs["created_by"] = created_by

    payment = Payment.objects.create(**kwargs)

    # -------------------------
    # Allocation: start_month -> forward
    # -------------------------
    left = total
    cur = start_month
    fee_field = _tm_fee_field()

    # 60 oy max (cheksiz loop bo‘lmasin)
    for _ in range(60):
        tm = ensure_tuition_month(enrollment, cur)
        fee = int(getattr(tm, fee_field, 0) or 0)

        if fee <= 0:
            cur = add_month(cur, 1)
            continue

        paid = get_month_paid(tm)
        need = max(0, fee - paid)

        if need <= 0:
            cur = add_month(cur, 1)
            continue

        take = min(left, need)
        if take > 0:
            PaymentAllocation.objects.create(payment=payment, tuition_month=tm, amount=take)
            left -= take

        if left <= 0:
            break

        cur = add_month(cur, 1)

    # Agar baribir left qolib ketsa (juda katta to‘lov), davom ettiramiz
    # (realda kam bo‘ladi, lekin xavfsiz)
    while left > 0:
        tm = ensure_tuition_month(enrollment, cur)
        fee = int(getattr(tm, fee_field, 0) or 0)
        if fee <= 0:
            cur = add_month(cur, 1)
            continue

        paid = get_month_paid(tm)
        need = max(0, fee - paid)
        if need <= 0:
            cur = add_month(cur, 1)
            continue

        take = min(left, need)
        PaymentAllocation.objects.create(payment=payment, tuition_month=tm, amount=take)
        left -= take
        cur = add_month(cur, 1)

    # Enrollment.jami_tolangan update (agar field bo‘lsa)
    if _model_has_field(Enrollment, "jami_tolangan"):
        Enrollment.objects.filter(pk=enrollment.pk).update(
            jami_tolangan=Coalesce(F("jami_tolangan"), 0) + total
        )

    return payment


@transaction.atomic
def reallocate_enrollment(enrollment: Enrollment):
    """
    Enrollment bo‘yicha hamma PaymentAllocation’larni 0 dan qayta hisoblaydi.
    Paymentlar ketma-ket (eskidan yangiga) yurib chiqiladi va allocation qayta taqsimlanadi.
    """

    # 1) hammasini tozalaymiz
    PaymentAllocation.objects.filter(payment__enrollment=enrollment).delete()

    # 2) Paymentlarni tartib bilan olamiz
    payment_fields = {f.name for f in Payment._meta.get_fields()}

    order_by = ["id"]
    if "paid_at" in payment_fields:
        order_by = ["paid_at", "id"]
    elif "sana" in payment_fields and "vaqt" in payment_fields:
        order_by = ["sana", "vaqt", "id"]
    elif "created_at" in payment_fields:
        order_by = ["created_at", "id"]

    payments = Payment.objects.filter(enrollment=enrollment).order_by(*order_by)

    # 3) Hech bo‘lmasa current oy mavjud bo‘lsin
    ensure_tuition_month(enrollment, timezone.localdate())

    fee_field = _tm_fee_field()

    def get_card_amount(p: Payment) -> int:
        if _model_has_field(Payment, "card_amount_som"):
            return int(getattr(p, "card_amount_som", 0) or 0)
        return int(getattr(p, "card_amount", 0) or 0)

    # 4) Har bir paymentni qayta allocate qilamiz
    for p in payments:
        cash = int(getattr(p, "cash_amount", 0) or 0)
        card = get_card_amount(p)
        total = cash + card
        if total <= 0:
            continue

        remaining = total

        while remaining > 0:
            tm = find_earliest_unpaid_month(enrollment)
            fee = int(getattr(tm, fee_field, 0) or 0)
            paid = get_month_paid(tm)

            need = max(0, fee - paid)

            # agar shu oy yopilgan bo‘lsa keyingi oyga o‘tamiz
            if need == 0:
                next_m = add_month(tm.month, 1)
                tm = ensure_tuition_month(enrollment, next_m)
                fee = int(getattr(tm, fee_field, 0) or 0)
                paid = get_month_paid(tm)
                need = max(0, fee - paid)

            take = min(remaining, need)
            if take > 0:
                PaymentAllocation.objects.create(payment=p, tuition_month=tm, amount=take)
                remaining -= take
            else:
                # xavfsizlik: cheksiz loop bo‘lmasin
                break
