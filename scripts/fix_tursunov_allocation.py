from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from datetime import date

c    = Center.objects.get(slug='proskill')
june = date(2026, 6, 1)

enr = Enrollment.objects.filter(
    group__center=c,
    student__familya='Tursunov',
    student__ism__icontains='Tursunboy',
    group__nom='English 12',
    is_deleted=False,
).first()

if not enr:
    print("Topilmadi!")
else:
    tm = TuitionMonth.objects.filter(enrollment=enr, month=june, is_deleted=False).first()
    pay = Payment.objects.filter(enrollment=enr, note="Iyun to'lovi (tuzatildi)", is_deleted=False).first()

    if not tm or not pay:
        print(f"TM: {tm}, Payment: {pay}")
    else:
        alloc_exists = PaymentAllocation.objects.filter(payment=pay, tuition_month=tm).exists()
        if alloc_exists:
            print("PaymentAllocation allaqachon bor.")
        else:
            PaymentAllocation.objects.create(payment=pay, tuition_month=tm, amount=pay.summa)
            print(f"✅ PaymentAllocation yaratildi: {pay.summa:,} so'm → {tm.month} TM")
            print(f"   Endi Qarzdorlardan chiqib ketadi.")
