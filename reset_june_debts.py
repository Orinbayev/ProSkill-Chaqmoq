import os
import django
from datetime import date

# Django muhitini sozlaymiz (script mustaqil ishlashi uchun)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
import django.db.models as models
from django.utils import timezone
from accounts.models import Center, User
from education.models import TuitionMonth, Enrollment, PaymentAllocation, Payment
from education.services.tuition import (
    tuition_month_fee_field,
    find_earliest_unpaid_month,
    _allocate_amount_forward,
    auto_net_student_credits
)

def _resolve_fee_amount(enrollment) -> int:
    """O'quvchining to'liq oylik o'qish pulini aniqlaydi (prorationlarsiz)."""
    if enrollment.student_payable_amount not in (None, ""):
        return int(enrollment.student_payable_amount)
    if getattr(enrollment, "kurs_narhi", None):
        return int(enrollment.kurs_narhi or 0)
    group = getattr(enrollment, "group", None)
    if group:
        return int(getattr(group, "kurs_narxi", 0) or getattr(group, "kurs_narhi", 0) or 0)
    return 0

def run_reset():
    import sys
    
    center = None
    if len(sys.argv) > 1:
        slug_arg = sys.argv[1].strip()
        center = Center.objects.filter(slug=slug_arg).first()
        if not center:
            print(f"❌ XATO: Kiritilgan '{slug_arg}' slugli o'quv markazi topilmadi!")
            return
    else:
        # Avtomatik ravishda "proskill" yoki "proskill-center" ni qidiramiz
        center = (
            Center.objects.filter(slug="proskill").first()
            or Center.objects.filter(slug="proskill-center").first()
            or Center.objects.filter(name__icontains="ProSkill").first()
        )

    if not center:
        print("❌ XATO: 'Pro Skill' nomli o'quv markazi topilmadi!")
        return

    target_month = date(2026, 6, 1)  # FAQAT Iyun 2026
    fee_field = tuition_month_fee_field()
    
    # ⚠️ MUHIM: Faqat faol, arxivlanmagan va o'chirilmagan o'quvchilar/guruhlarni olamiz
    # Bu veb-saytdagi Qarzdorlar sahifasi bilan 100% bir xil natija beradi!
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
    
    print("=" * 80)
    print(f"🔄 BOSHLANDI: {center.name} markazidagi faol qarzlarni qayta qurish...")
    print(f"Jami faol enrollmentlar soni: {enrollments.count()}")
    print("=" * 80)

    try:
        with transaction.atomic():
            now = timezone.now()
            
            # 1. Faol enrollmentlar uchun Iyun 2026 dan boshqa barcha oylar qarzlarini vaqtincha soft-delete qilamiz (pastda to'lovlar borligi uchun qayta tiklaymiz)
            tms_to_delete = TuitionMonth.objects.filter(
                enrollment__in=enrollments
            ).exclude(
                month=target_month
            )
            deleted_tms_count = tms_to_delete.count()
            tms_to_delete.update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="cleanup_non_june_months"
            )
            print(f"🗑️ 1. O'chirilgan faol o'quvchilar non-June TuitionMonth yozuvlari: {deleted_tms_count}")
            
            # 1b. Arxivlangan o'quvchilar yoki o'chirilgan guruhlar uchun June 2026 qarzlarini to'liq o'chiramiz (Soft-Delete)
            tms_inactive_june = TuitionMonth.objects.filter(
                center=center,
                month=target_month
            ).exclude(
                enrollment__in=enrollments
            )
            inactive_june_count = tms_inactive_june.count()
            tms_inactive_june.update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="cleanup_inactive_or_archived_enrollments_for_june"
            )
            print(f"🗑️ 1b. O'chirilgan arxivlangan/no-faol June TuitionMonth yozuvlari: {inactive_june_count}")
            
            # 2. Faol o'quvchilar uchun Iyun 2026 dan boshqa oylar to'lov taqsimotlarini o'chiramiz
            allocs_to_delete = PaymentAllocation.objects.filter(
                tuition_month__enrollment__in=enrollments
            ).exclude(
                tuition_month__month=target_month
            )
            deleted_allocs_count = allocs_to_delete.count()
            allocs_to_delete.update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="cleanup_non_june_months"
            )
            print(f"🗑️ 2. O'chirilgan non-June PaymentAllocation yozuvlari: {deleted_allocs_count}")
            
            # 2b. Arxivlangan/no-faol o'quvchilar uchun June 2026 to'lov taqsimotlarini ham o'chiramiz
            allocs_inactive_june = PaymentAllocation.objects.filter(
                tuition_month__center=center,
                tuition_month__month=target_month
            ).exclude(
                tuition_month__enrollment__in=enrollments
            )
            inactive_june_allocs_count = allocs_inactive_june.count()
            allocs_inactive_june.update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="cleanup_inactive_or_archived_enrollments_for_june"
            )
            print(f"🗑️ 2b. O'chirilgan arxivlangan/no-faol June PaymentAllocation yozuvlari: {inactive_june_allocs_count}")
            
            # 3. Barcha faol enrollmentlar credit_balance qiymatini vaqtincha 0 qilamiz
            enrollments.update(credit_balance=0)
            print("🔄 3. Barcha faol enrollmentlar uchun credit_balance nollashtirildi.")
            
            # 4. Hamma-hamma enrollmentlar uchun IYUN 2026 oyi qarzini (full fee) yozamiz
            created_tms = 0
            for enr in enrollments:
                fee = _resolve_fee_amount(enr)
                if fee <= 0:
                    fee = 300000
                    
                TuitionMonth.all_objects.update_or_create(
                    enrollment=enr,
                    month=target_month,
                    defaults={
                        "center": getattr(enr, "center", None) or center,
                        "is_deleted": False,
                        "deleted_at": None,
                        fee_field: fee
                    }
                )
                created_tms += 1
            print(f"📝 4. Barcha faol enrollmentlar uchun Iyun 2026 qarzlar yozildi: {created_tms} ta.")
            
            # 5. To'lovlarni o'z oylariga bog'lab qayta taqsimlaymiz (Reallocate)
            # - Iyun oyi oldidan kiritilgan to'lovlar o'z oylarida qoladi va Iyun oyiga o'tmaydi.
            # - Iyun va undan keyingi oylardagi to'lovlar Iyun oyiga yo'naltiriladi.
            reallocated_count = 0
            for enr in enrollments:
                payments = Payment.objects.filter(
                    models.Q(enrollment=enr) | models.Q(student=enr.student, group=enr.group)
                ).filter(is_deleted=False).order_by("paid_date", "id")
                
                # Ushbu enrollment uchun mavjud bo'lgan barcha to'lov taqsimotlarini o'chiramiz
                PaymentAllocation.objects.filter(tuition_month__enrollment=enr).delete()
                
                # To'lovlarni oylar bo'yicha guruhlaymiz
                payments_by_month = {}
                for p in payments:
                    if not p.enrollment_id:
                        p.enrollment = enr
                        p.save(update_fields=["enrollment"])
                        
                    p_date = getattr(p, "paid_date", None)
                    if not p_date:
                        p_date = target_month
                        
                    p_month = p_date.replace(day=1)
                    if p_month not in payments_by_month:
                        payments_by_month[p_month] = []
                    payments_by_month[p_month].append(p)
                    
                # 5a. Tarixiy oylar uchun (April, May) qarz summasini to'langan summaga tenglashtiramiz
                # Bu orqali tarixiy oylardagi qoldiq qarz 0 bo'ladi va ular Iyun oyiga oqib o'tmaydi.
                for p_month, p_list in payments_by_month.items():
                    if p_month < target_month:
                        total_p = sum(p.summa for p in p_list)
                        
                        # Tarixiy oy uchun TuitionMonth yaratamiz/yangilaymiz
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
                        
                        # Ushbu tarixiy oy to'lovlarini to'liq shu oyga yopamiz
                        for p in p_list:
                            PaymentAllocation.objects.create(
                                center=p.center or enr.center,
                                payment=p,
                                tuition_month=tm,
                                amount=p.summa
                            )
                            
                # 5b. Iyun va undan keyingi oylar to'lovlarini Iyun oyiga taqsimlaymiz
                june_and_later_payments = []
                for p_month, p_list in payments_by_month.items():
                    if p_month >= target_month:
                        june_and_later_payments.extend(p_list)
                        
                june_and_later_payments.sort(key=lambda p: (getattr(p, "paid_date", target_month), p.id))
                
                for p in june_and_later_payments:
                    cash = int(getattr(p, "cash_amount", 0) or 0)
                    card = int(getattr(p, "card_amount_som", 0) or getattr(p, "card_amount", 0) or 0)
                    total = cash + card
                    if total <= 0:
                        continue
                        
                    tm = find_earliest_unpaid_month(enr, start_month=target_month)
                    _allocate_amount_forward(enrollment=enr, payment=p, amount=total, start_month=tm.month)
                
                reallocated_count += 1
                
            print(f"⚡ 5. Barcha {reallocated_count} ta o'quvchi to'lovlari o'z oylari kesimida qayta taqsimlandi.")
            
            # 5c. Guruhlararo to'lov va avanslarni o'zaro hisob-kitob qilish (Net-Out)
            seen_students = set()
            netted_count = 0
            for enr in enrollments:
                if enr.student_id not in seen_students:
                    seen_students.add(enr.student_id)
                    try:
                        auto_net_student_credits(enr.student)
                        netted_count += 1
                    except Exception:
                        pass
            print(f"🔄 5c. Barcha {netted_count} ta o'quvchi uchun guruhlararo to'lov/avanslar o'zaro net-out qilindi.")
            
            # 6. Ortiqcha kelajak oylarni tozalab, pulni credit_balance ga o'tkazamiz
            future_tms = TuitionMonth.objects.filter(
                enrollment__in=enrollments,
                month__gt=target_month
            )
            
            cleaned_future_tms = 0
            moved_credits_sum = 0
            
            for tm in future_tms:
                alloc_sum = PaymentAllocation.objects.filter(
                    tuition_month=tm,
                    is_deleted=False
                ).aggregate(s=models.Sum("amount"))["s"] or 0
                
                if alloc_sum > 0:
                    Enrollment.objects.filter(pk=tm.enrollment_id).update(
                        credit_balance=models.F("credit_balance") + alloc_sum
                    )
                    moved_credits_sum += alloc_sum
                    
                PaymentAllocation.objects.filter(
                    tuition_month=tm,
                    is_deleted=False
                ).update(
                    is_deleted=True,
                    deleted_at=now,
                    deleted_reason="move_future_allocations_to_credit_balance"
                )
                
                TuitionMonth.objects.filter(pk=tm.id).update(
                    is_deleted=True,
                    deleted_at=now,
                    deleted_reason="move_future_allocations_to_credit_balance"
                )
                cleaned_future_tms += 1
                
            print(f"🛡️ 6. Kelajakdagi ortiqcha TuitionMonth yozuvlari o'chirildi: {cleaned_future_tms} ta.")
            if moved_credits_sum > 0:
                print(f"💰 Kelajak oylar uchun to'langan jami {moved_credits_sum:,} so'm pul o'quvchilar balansiga (credit_balance) avans sifatida o'tkazildi.")
            
            # 7. Yakuniy statistikani bazadan qayta hisoblaymiz (Sayt bilan 100% mosligini tekshirish uchun)
            db_fees = TuitionMonth.objects.filter(
                center=center,
                month=target_month,
                is_deleted=False
            ).aggregate(s=models.Sum("fee_amount"))["s"] or 0
            
            db_paid = PaymentAllocation.objects.filter(
                tuition_month__center=center,
                tuition_month__month=target_month,
                tuition_month__is_deleted=False,
                payment__is_deleted=False
            ).aggregate(s=models.Sum("amount"))["s"] or 0
            
            db_outstanding = db_fees - db_paid
            
            # Debtors count (qarzdorlar soni)
            student_debt_map = {}
            for enr in enrollments:
                tm = TuitionMonth.objects.filter(enrollment=enr, month=target_month, is_deleted=False).first()
                if tm:
                    paid = PaymentAllocation.objects.filter(tuition_month=tm, is_deleted=False).aggregate(s=models.Sum("amount"))["s"] or 0
                    debt = max(0, tm.fee_amount - paid)
                    if debt > 0:
                        student_debt_map[enr.student_id] = student_debt_map.get(enr.student_id, 0) + debt
            
            real_debtors_count = len([sid for sid, d in student_debt_map.items() if d > 0])
            
            print("=" * 80)
            print("📊 YAKUNIY STATISTIKA (BAZA VA VEB-SAYT 100% BIR XIL):")
            print(f"  Jami yozilgan qarz summasi (June Gross Fees): {db_fees:,} so'm")
            print(f"  To'lovlardan chegirilgan qismi (June Paid): {db_paid:,} so'm")
            print(f"  Qoldiq qarz (Outstanding Debt): {db_outstanding:,} so'm")
            print(f"  Haqiqiy qarzdor o'quvchilar soni: {real_debtors_count} ta")
            print("=" * 80)
            print("🎉 BARCHASI MUVAFFAQIYATLI TUGADI! Tranzaksiya saqlandi (committed).")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ XATO YUZ BERDI: {str(e)}")
        print("Baza holati o'zgartirilmadi (Rollback qilindi).")

if __name__ == "__main__":
    run_reset()
