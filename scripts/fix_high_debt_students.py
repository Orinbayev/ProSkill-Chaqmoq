"""
Katta qarz to'plagan o'quvchilarni tuzatadi:
1. Noto'g'ri katta Payment ni soft-delete qiladi
2. Faqat iyun oyining to'g'ri summasini Payment qilib yozadi
3. Oldingi oylarning TuitionMonth larini soft-delete qiladi (ular iyungacha bo'lgan qarzlar)
"""
from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from django.db import transaction
from datetime import date

c = Center.objects.get(slug='proskill')
today = date(2026, 6, 22)
june  = date(2026, 6, 1)

# Tuzatilishi kerak bo'lgan o'quvchilar (ism, guruh nomi)
TARGETS = [
    ("Abdullayev Isobek",    "English - 02"),
    ("Madaminov Yaxyobek",   "English 03"),
    ("Otaxon Otaxonov",      "Kompyuter Savodxonlik - 28"),
    ("Shavkatov Jafarbek",   "BackEnd-08"),
    ("Tursunov Tursunboy",   "English 12"),
]

print("\n" + "="*70)
print("  KATTA QARZLI O'QUVCHILAR — TAHLIL VA TUZATISH")
print("="*70)

for full_name, group_nom in TARGETS:
    parts = full_name.split(" ", 1)
    familya, ism = parts[0], parts[1] if len(parts) > 1 else ""

    enr = Enrollment.objects.filter(
        group__center=c,
        student__familya__iexact=familya,
        student__ism__icontains=ism.split()[0] if ism else "",
        group__nom__iexact=group_nom,
        is_deleted=False,
    ).select_related('student', 'group', 'group__center').first()

    if not enr:
        print(f"\n⚠️  TOPILMADI: {full_name} — {group_nom}")
        continue

    name = f"{enr.student.familya} {enr.student.ism}"
    print(f"\n{'─'*70}")
    print(f"  {name}  |  {enr.group.nom}  (enrollment id={enr.id})")
    print(f"{'─'*70}")

    # Barcha TuitionMonth larni ko'rsat
    tms = TuitionMonth.objects.filter(
        enrollment=enr, is_deleted=False
    ).order_by('month')

    print(f"  TuitionMonth lar:")
    june_tm = None
    old_tms = []
    for tm in tms:
        paid_allocs = PaymentAllocation.objects.filter(
            tuition_month=tm,
            payment__is_deleted=False,
        )
        paid = sum(a.amount for a in paid_allocs)
        debt = max(0, tm.fee_amount - paid)
        marker = " ← IYUN" if tm.month == june else ""
        print(f"    {tm.month.strftime('%Y-%m')}  fee={tm.fee_amount:>10,}  to'langan={paid:>10,}  qarz={debt:>10,}{marker}")
        if tm.month == june:
            june_tm = tm
        elif tm.month < june:
            old_tms.append(tm)

    # Bugun yaratilgan noto'g'ri katta Payment ni top
    wrong_payments = Payment.objects.filter(
        enrollment=enr,
        paid_date=today,
        note="Eski qarz — to'lov bo'limiga o'tkazildi",
        is_deleted=False,
    )
    print(f"\n  Bugun yaratilgan to'lovlar:")
    for p in wrong_payments:
        print(f"    Payment id={p.id}  summa={p.summa:,}  ← o'CHIRILADI")

    if not june_tm:
        print(f"  ⚠️  Iyun TM topilmadi — o'tkazildi")
        continue

    june_fee = june_tm.fee_amount
    print(f"\n  Iyun to'g'ri narxi: {june_fee:,} so'm")
    print(f"  O'chiriladigan eski oylar: {len(old_tms)} ta TM")

    with transaction.atomic():
        # 1. Noto'g'ri katta payment ni soft-delete
        for p in wrong_payments:
            p.is_deleted = True
            p.deleted_reason = "bulk_pay_corrected"
            p.save(update_fields=['is_deleted', 'deleted_reason'])

        # 2. Eski oylarning TM larini soft-delete
        for tm in old_tms:
            tm.is_deleted = True
            tm.deleted_reason = "cleanup_pre_june_debt"
            tm.save(update_fields=['is_deleted', 'deleted_reason'])

        # 3. Iyun uchun to'g'ri Payment yarat
        already = Payment.objects.filter(
            enrollment=enr,
            paid_date__year=june.year,
            paid_date__month=june.month,
            summa=june_fee,
            is_deleted=False,
        ).exists()

        if not already and june_fee > 0:
            center = enr.center or (enr.group.center if enr.group else None)
            Payment.objects.create(
                enrollment=enr,
                student=enr.student,
                group=enr.group,
                center=center,
                summa=june_fee,
                cash_amount=june_fee,
                paid_date=june,
                note="Iyun to'lovi (tuzatildi)",
                payment_type='cash',
            )
            print(f"  ✅ Yangi Payment yaratildi: {june_fee:,} so'm (iyun)")
        else:
            print(f"  ℹ️  Payment allaqachon mavjud yoki fee=0")

print(f"\n{'='*70}")
print("  TUGADI — Ularning iyun to'lovlari to'g'irlandi.")
print(f"{'='*70}\n")
