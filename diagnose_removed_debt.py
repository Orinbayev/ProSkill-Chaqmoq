"""FAQAT O'QISH (READ-ONLY) diagnostika — hech narsani o'zgartirmaydi.

Chiqarilgan o'quvchida fantom qarz sababini ko'rsatadi.
Ishga tushirish (Render Shell yoki lokal):
    python diagnose_removed_debt.py "BOBAJONOV" "MUHAMMADJON"
yoki telefon bo'yicha:
    python diagnose_removed_debt.py --phone 934666828
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db.models import Sum, Q
from accounts.models import User
from education.models import (
    Enrollment, TuitionMonth, PaymentAllocation, Attendance, StudentGroupHistory,
)
from education.services.tuition import (
    tuition_month_fee_field, enrollment_last_billable_date,
    billable_attendance_count, prorated_monthly_fee,
)

FF = tuition_month_fee_field()


def find_students(argv):
    qs = User.objects.filter(role="student")
    if "--phone" in argv:
        phone = argv[argv.index("--phone") + 1]
        return qs.filter(Q(telefon1__icontains=phone) | Q(telefon2__icontains=phone))
    if len(argv) >= 3:
        return qs.filter(familya__icontains=argv[1], ism__icontains=argv[2])
    if len(argv) == 2:
        return qs.filter(Q(familya__icontains=argv[1]) | Q(ism__icontains=argv[1]))
    print("Foydalanish: python diagnose_removed_debt.py FAMILYA ISM  |  --phone RAQAM")
    return qs.none()


def main():
    students = find_students(sys.argv)
    n = students.count()
    print(f"Topilgan o'quvchilar: {n}")
    if n == 0:
        return

    for stu in students[:10]:
        print("\n" + "=" * 70)
        print(f"O'QUVCHI: {stu.familya} {stu.ism}  (id={stu.id}, center={stu.center_id}, tel={stu.telefon1})")

        enrs = Enrollment.all_objects.filter(student=stu).select_related("group")
        for e in enrs:
            removed = (not e.is_active) or e.is_deleted
            last_bill = enrollment_last_billable_date(e)
            print(f"\n  GURUH: {getattr(e.group,'nom','?')}  (enr={e.id})")
            print(f"    is_active={e.is_active}  is_deleted={e.is_deleted}  "
                  f"=> CHIQARILGAN={removed}")
            print(f"    last_lesson_date={getattr(e,'last_lesson_date',None)}  "
                  f"last_billable_date(hisob chegara)={last_bill}")
            hist = StudentGroupHistory.objects.filter(student=stu, group=e.group).order_by("start_date")
            for h in hist:
                print(f"    tarix: start={h.start_date} end={h.end_date}")

            tms = TuitionMonth.all_objects.filter(enrollment=e).order_by("month")
            if not tms:
                print("    (TuitionMonth yo'q)")
            for tm in tms:
                paid = PaymentAllocation.objects.filter(
                    tuition_month=tm, payment__is_deleted=False,
                ).aggregate(s=Sum("amount"))["s"] or 0
                fee = int(getattr(tm, FF, 0) or 0)
                # Shu oy uchun HAQIQIY hisob-kitob qiymatlari:
                try:
                    billable = billable_attendance_count(e, tm.month)
                except Exception:
                    billable = "?"
                try:
                    should_fee = prorated_monthly_fee(e, tm.month)
                except Exception:
                    should_fee = "?"
                reason = getattr(tm, "deleted_reason", "") or ""
                flag = ""
                if removed and last_bill and tm.month.replace(day=1) > last_bill.replace(day=1) and fee > 0:
                    flag = "  <== FANTOM? (chiqarilgandan keyingi oy, fee>0)"
                elif fee > 0 and should_fee == 0 and billable == 0:
                    flag = "  <== fee>0 lekin davomat=0 (fantom bo'lishi mumkin)"
                print(f"      oy={tm.month}  fee={fee}  paid={paid}  "
                      f"is_deleted={tm.is_deleted}  reason='{reason}'  "
                      f"| billable_att={billable}  kerakli_fee={should_fee}{flag}")

    print("\n" + "=" * 70)
    print("IZOH: 'reason' bo'sh bo'lmasa (reset_/manual_cleared/cleanup_/user_edit) —")
    print("bu TuitionMonth 'himoyalangan', avtomatik reconcile uni 0 ga tushirmaydi.")


if __name__ == "__main__":
    main()
