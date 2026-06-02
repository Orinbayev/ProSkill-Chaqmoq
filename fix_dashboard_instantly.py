import os
import django
from datetime import date

# Django muhitini sozlaymiz
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
import django.db.models as models
from django.utils import timezone
from accounts.models import Center, User
from education.models import TuitionMonth, Enrollment, PaymentAllocation, Payment
from django.db.models import Sum, Q

def run():
    center = Center.objects.filter(slug="proskill").first()
    if not center:
        print("❌ XATO: 'proskill' markazi topilmadi!")
        return
        
    print(f"🎯 Markaz topildi: {center.name} (ID: {center.id})")
    
    target_month = date(2026, 6, 1)
    fee_field = "fee_amount"
    
    # Faol enrollmentlarni olamiz
    enrollments = Enrollment.objects.filter(
        is_deleted=False,
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False
    ).filter(
        models.Q(center=center) | 
        models.Q(group__center=center) | 
        models.Q(student__center=center)
    ).distinct()
    
    print(f"🔄 Baza yangilanmoqda. Jami faol ulanishlar: {enrollments.count()} ta...")
    
    try:
        with transaction.atomic():
            now = timezone.now()
            
            # 1. Non-June TuitionMonths va non-June allocations ni tozalaymiz
            # (Pastda to'g'ri sanalar bilan qayta tiklaymiz)
            TuitionMonth.objects.filter(enrollment__in=enrollments).exclude(month=target_month).update(
                is_deleted=True, deleted_at=now, deleted_reason="financial_rebuild_june"
            )
            PaymentAllocation.objects.filter(tuition_month__enrollment__in=enrollments).exclude(tuition_month__month=target_month).update(
                is_deleted=True, deleted_at=now, deleted_reason="financial_rebuild_june"
            )
            
            # June oyi uchun arxivlangan/nofaol o'quvchilar qarzini o'chiramiz
            TuitionMonth.objects.filter(center=center, month=target_month).exclude(enrollment__in=enrollments).update(
                is_deleted=True, deleted_at=now, deleted_reason="financial_rebuild_june"
            )
            PaymentAllocation.objects.filter(tuition_month__center=center, tuition_month__month=target_month).exclude(tuition_month__enrollment__in=enrollments).update(
                is_deleted=True, deleted_at=now, deleted_reason="financial_rebuild_june"
            )
            
            # Balanslarni vaqtincha nollashtiramiz
            enrollments.update(credit_balance=0)
            
            # 2. Barcha faol o'quvchilar to'lovlarini xronologik tartibda o'z oylariga qulflaymiz
            from education.services.tuition import find_earliest_unpaid_month, _allocate_amount_forward, auto_net_student_credits
            
            for enr in enrollments:
                payments = Payment.objects.filter(
                    models.Q(enrollment=enr) | models.Q(student=enr.student, group=enr.group)
                ).filter(is_deleted=False).order_by("paid_date", "id")
                
                # Ushbu enrollment uchun mavjud Iyun allocations ni vaqtincha o'chiramiz
                PaymentAllocation.objects.filter(tuition_month__enrollment=enr).delete()
                
                # To'lovlarni oylar bo'yicha guruhlaymiz
                payments_by_month = {}
                for p in payments:
                    if not p.enrollment_id:
                        p.enrollment = enr
                        p.save(update_fields=["enrollment"])
                        
                    p_date = p.paid_date
                    p_month = p_date.replace(day=1)
                    if p_month not in payments_by_month:
                        payments_by_month[p_month] = []
                    payments_by_month[p_month].append(p)
                    
                # 2a. Iyun oldidagi to'lovlarni o'z oylariga (April, May) qulflash
                for p_month, p_list in payments_by_month.items():
                    if p_month < target_month:
                        total_p = sum(p.summa for p in p_list)
                        
                        tm, created = TuitionMonth.all_objects.update_or_create(
                            enrollment=enr,
                            month=p_month,
                            defaults={
                                "center": enr.center or center,
                                "is_deleted": False,
                                "deleted_at": None,
                                fee_field: total_p
                            }
                        )
                        
                        for p in p_list:
                            PaymentAllocation.objects.create(
                                center=p.center or enr.center,
                                payment=p,
                                tuition_month=tm,
                                amount=p.summa
                            )
                            
                # 2b. Iyun va undan keyingi to'lovlarni Iyun oyiga yo'naltirish
                june_and_later_payments = []
                for p_month, p_list in payments_by_month.items():
                    if p_month >= target_month:
                        june_and_later_payments.extend(p_list)
                june_and_later_payments.sort(key=lambda p: (p.paid_date, p.id))
                
                # June TuitionMonth (Full fee)
                from reset_june_debts import _resolve_fee_amount
                june_fee = _resolve_fee_amount(enr) or 300000
                
                TuitionMonth.all_objects.update_or_create(
                    enrollment=enr,
                    month=target_month,
                    defaults={
                        "center": enr.center or center,
                        "is_deleted": False,
                        "deleted_at": None,
                        fee_field: june_fee
                    }
                )
                
                for p in june_and_later_payments:
                    cash = int(getattr(p, "cash_amount", 0) or 0)
                    card = int(getattr(p, "card_amount_som", 0) or getattr(p, "card_amount", 0) or 0)
                    total = cash + card
                    if total <= 0:
                        continue
                    tm = find_earliest_unpaid_month(enr, start_month=target_month)
                    _allocate_amount_forward(enrollment=enr, payment=p, amount=total, start_month=tm.month)
            
            # Guruhlararo net-out
            seen_students = set()
            for enr in enrollments:
                if enr.student_id not in seen_students:
                    seen_students.add(enr.student_id)
                    try:
                        auto_net_student_credits(enr.student)
                    except Exception:
                        pass
                        
            # Kelajak oylarni tozalash (July, August etc.)
            future_tms = TuitionMonth.objects.filter(enrollment__in=enrollments, month__gt=target_month)
            for tm in future_tms:
                alloc_sum = PaymentAllocation.objects.filter(tuition_month=tm, is_deleted=False).aggregate(s=models.Sum("amount"))["s"] or 0
                if alloc_sum > 0:
                    Enrollment.objects.filter(pk=tm.enrollment_id).update(credit_balance=models.F("credit_balance") + alloc_sum)
                PaymentAllocation.objects.filter(tuition_month=tm, is_deleted=False).update(
                    is_deleted=True, deleted_at=now, deleted_reason="financial_rebuild_june"
                )
                TuitionMonth.objects.filter(pk=tm.id).update(
                    is_deleted=True, deleted_at=now, deleted_reason="financial_rebuild_june"
                )
                
            print("✅ Tranzaksiya muvaffaqiyatli bajarildi!")

        # 3. Keshni butunlay tozalaymiz
        from django.core.cache import cache
        cache.clear()
        print("⚡ Barcha keshlar tozalandi!")
        
        # 4. Endi diagramma nima ko'rsatishini hisoblab chiqib konsolga chiqaramiz
        from core.dashboard_views import _bulk_monthly_turnover, _six_month_range, _bulk_monthly_expenses
        six_months_meta = list(_six_month_range(timezone.localdate()))
        six_months_pairs = [(ms, me) for ms, me, _ in six_months_meta]
        
        bulk_turnover = _bulk_monthly_turnover(center, six_months_pairs)
        bulk_expenses = _bulk_monthly_expenses(center, six_months_pairs)
        
        print("\n" + "="*50)
        print("📊 DASTUR DIAGRAMMASI UCHUN YANGI QIYMÀTLAR:")
        for ms, me, lbl in six_months_meta:
            key = (ms.year, ms.month)
            inc = bulk_turnover.get(key, 0)
            exp = bulk_expenses.get(key, 0)
            print(f" 🗓️ {lbl} {ms.year}: Kirim (Aylanma) = {inc:,} so'm | Chiqim (Xarajat) = {exp:,} so'm")
        print("="*50)
        print("💡 Agar yuqoridagi 'Iyn 2026' aylanmasi kichik summa bo'lsa, saytda diagramma 100% to'g'rilandi!")
        
    except Exception as e:
        print(f"❌ XATO YUZ BERDI: {e}")

if __name__ == "__main__":
    run()
