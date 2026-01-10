from datetime import date
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from education.models import TuitionMonth, PaymentAllocation, Payment

def month_first_day(d: date) -> date:
    return date(d.year, d.month, 1)

def next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)

def ensure_tuition_month(enrollment, month: date) -> TuitionMonth:
    """
    Agar shu oy uchun TuitionMonth bo‘lmasa yaratadi.
    fee_amount manbasi: enrollment.kurs_narhi (sizda bor) -> group.kurs_narxi fallback
    """
    month = month_first_day(month)

    fee = getattr(enrollment, "kurs_narhi", None) or getattr(getattr(enrollment, "group", None), "kurs_narxi", 0) or 0

    tm, created = TuitionMonth.objects.get_or_create(
        enrollment=enrollment,
        month=month,
        defaults={"fee_amount": int(fee)}
    )
    # Agar fee 0 bo‘lib qolgan bo‘lsa, keyin ham update qilish mumkin (xohlasangiz)
    return tm

def get_month_paid(tm: TuitionMonth) -> int:
    return tm.allocations.aggregate(s=Sum("amount"))["s"] or 0

def find_earliest_unpaid_month(enrollment) -> TuitionMonth:
    """
    Eng oldingi to‘lanmagan (paid < fee) oyni topadi.
    Agar hammasi yopilgan bo‘lsa — keyingi yangi oy yaratadi.
    """
    months = TuitionMonth.objects.filter(enrollment=enrollment).order_by("month")
    for tm in months:
        paid = get_month_paid(tm)
        if paid < tm.fee_amount:
            return tm

    # Hech bo‘lmasa current month bo‘lsin
    today_m = month_first_day(timezone.localdate())
    if months.exists():
        last = months.last().month
        m = next_month(last)
    else:
        m = today_m

    return ensure_tuition_month(enrollment, m)

@transaction.atomic
def create_payment_and_allocate(*, enrollment, created_by, cash_amount: int, card_amount: int, paid_at=None) -> Payment:
    cash_amount = int(cash_amount or 0)
    card_amount = int(card_amount or 0)
    total = cash_amount + card_amount
    if total <= 0:
        raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas")

    if paid_at is None:
        paid_at = timezone.now()

    # Payment modelingizda fieldlar boshqacha bo‘lishi mumkin.
    # Shuning uchun safe tarzda set qilamiz.
    payment = Payment.objects.create(
        enrollment=enrollment,
        group=enrollment.group,          # ✅ SHUNI QO‘SHING
        cash_amount=cash_amount,
        card_amount=card_amount,
        summa=total,
        student=enrollment.student,

    )


    # Agar sizda sana/vaqt field bo‘lsa:
    if hasattr(payment, "sana"):
        payment.sana = timezone.localdate()
    if hasattr(payment, "vaqt"):
        payment.vaqt = timezone.localtime().time()
    if hasattr(payment, "paid_at"):
        payment.paid_at = paid_at

    if hasattr(payment, "created_by"):
        payment.created_by = created_by

    payment.save()

    # Allocation: paymentni eng eski qarzdan boshlab yopib boradi
    remaining = total

    # Hech bo‘lmasa current oy mavjud bo‘lsin
    ensure_tuition_month(enrollment, timezone.localdate())

    while remaining > 0:
        tm = find_earliest_unpaid_month(enrollment)
        paid = get_month_paid(tm)
        need = max(0, tm.fee_amount - paid)

        if need == 0:
            # Bu holat kam, lekin bo‘lsa next oyga o‘tamiz
            tm_next = ensure_tuition_month(enrollment, next_month(tm.month))
            tm = tm_next
            paid = get_month_paid(tm)
            need = max(0, tm.fee_amount - paid)

        take = min(remaining, need)
        PaymentAllocation.objects.create(payment=payment, tuition_month=tm, amount=take)
        remaining -= take

        # Agar remaining qolsa, keyingi oy yaratilib boradi
        if remaining > 0 and take == need:
            ensure_tuition_month(enrollment, next_month(tm.month))

    return payment
