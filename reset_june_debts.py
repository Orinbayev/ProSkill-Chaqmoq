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
from education.services.tuition import tuition_month_fee_field, find_earliest_unpaid_month, _allocate_amount_forward

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

def has_june_payment(enr) -> bool:
    """O'quvchida Iyun 2026 oyida to'lov bor-yo'qligini tekshiradi."""
    payments = Payment.objects.filter(
        models.Q(enrollment=enr) | models.Q(student=enr.student, group=enr.group)
    ).filter(is_deleted=False)
    for p in payments:
        p_date = getattr(p, "paid_at", None) or getattr(p, "sana", None) or getattr(p, "paid_date", None)
        if p_date:
            if hasattr(p_date, "date"):
                p_date = p_date.date()
            if p_date.year == 2026 and p_date.month == 6:
                return True
    return False

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
    
    # KENGAYTIRILGAN FILTER: Markazga tegishli BARCHA enrollmentlarni qamrab olamiz
    # (ba'zida enrollmentda center=null bo'lsa ham student__center orqali topadi)
    enrollments = Enrollment.objects.filter(is_deleted=False).filter(
        models.Q(center=center) | 
        models.Q(group__center=center) | 
        models.Q(student__center=center)
    )
    
    print("=" * 80)
    print(f"🔄 BOSHLANDI: {center.name} markazidagi qarzlarni qayta qurish...")
    print(f"Jami aniqlangan enrollmentlar soni: {enrollments.count()}")
    print("=" * 80)

    try:
        with transaction.atomic():
            now = timezone.now()
            
            # 1. Iyun 2026 dan boshqa barcha oylar qarzdorliklarini to'liq o'chiramiz
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
            print(f"🗑️ 1. O'chirilgan non-June TuitionMonth yozuvlari: {deleted_tms_count}")
            
            # 2. Iyun 2026 dan boshqa oylar to'lov taqsimotlarini o'chiramiz
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
            
            # 3. Barcha enrollmentlar credit_balance qiymatini vaqtincha 0 qilamiz
            enrollments.update(credit_balance=0)
            print("🔄 3. Barcha enrollmentlar uchun credit_balance nollashtirildi.")
            
            # 4. Faol yoki Iyun oyida to'lov qilgan o'quvchilar uchun IYUN oyi qarzini (full fee) yozamiz
            created_tms = 0
            for enr in enrollments:
                is_active_student = enr.is_active and not enr.student.is_archived and not enr.group.is_archived and not enr.group.is_deleted
                if is_active_student or has_june_payment(enr):
                    fee = _resolve_fee_amount(enr)
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
            print(f"📝 4. Iyun 2026 oyi uchun to'liq qarzlar yozildi: {created_tms} ta enrollment uchun.")
            
            # 5. Mustahkamlangan to'lov taqsimoti (Reallocation):
            # Unlinked to'lovlarni ham bog'laymiz va boshidan qayta taqsimlaymiz
            reallocated_count = 0
            for enr in enrollments:
                # Ushbu enrollmentga tegishli barcha to'lovlarni o'chiramiz (faqat allocationlarni)
                PaymentAllocation.objects.filter(tuition_month__enrollment=enr).delete()
                
                # To'lovlarni qidiramiz (enrollment FK orqali yoki student+group orqali)
                payments = Payment.objects.filter(
                    models.Q(enrollment=enr) | models.Q(student=enr.student, group=enr.group)
                ).filter(is_deleted=False).order_by("id")
                
                for p in payments:
                    # Agar to'lov enrollmentga bog'lanmagan bo'lsa, bog'lab qo'yamiz (DB butunligi uchun)
                    if not p.enrollment_id:
                        p.enrollment = enr
                        p.save(update_fields=["enrollment"])
                        
                    cash = int(getattr(p, "cash_amount", 0) or 0)
                    card = int(getattr(p, "card_amount_som", 0) or getattr(p, "card_amount", 0) or 0)
                    total = cash + card
                    if total <= 0:
                        continue
                    
                    # Iyun oyidan boshlab to'lovlarni taqsimlaymiz
                    tm = find_earliest_unpaid_month(enr, start_month=target_month)
                    _allocate_amount_forward(enrollment=enr, payment=p, amount=total, start_month=tm.month)
                
                reallocated_count += 1
            print(f"⚡ 5. Barcha {reallocated_count} ta o'quvchi to'lovlari mustahkamlanib, qayta taqsimlandi.")
            
            # 6. Kelajak oylarni o'chirib, ortiqcha pulni credit_balance ga o'tkazamiz
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
            
            print("=" * 80)
            print("🎉 BARCHASI MUVAFFAQIYATLI TUGADI! Tranzaksiya saqlandi (committed).")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ XATO YUZ BERDI: {str(e)}")
        print("Baza holati o'zgartirilmadi (Rollback qilindi).")

if __name__ == "__main__":
    run_reset()
