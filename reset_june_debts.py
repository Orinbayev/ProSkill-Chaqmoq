import os
import django
from datetime import date

# Django muhitini sozlaymiz (script mustaqil ishlashi uchun)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
import django.db.models as models
from django.utils import timezone
from accounts.models import Center
from education.models import TuitionMonth, Enrollment, PaymentAllocation
from education.services.tuition import reallocate_enrollment, ensure_tuition_month

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
    
    # Markazga tegishli barcha o'quvchilar enrollmentlarini olamiz
    enrollments = Enrollment.objects.filter(is_deleted=False).filter(
        models.Q(center=center) | models.Q(center__isnull=True, group__center=center)
    )
    
    print("=" * 80)
    print(f"🔄 BOSHLANDI: {center.name} markazidagi qarzlarni qayta qurish...")
    print(f"O'quvchilar guruh birikmalari (Enrollments) soni: {enrollments.count()}")
    print("=" * 80)

    try:
        with transaction.atomic():
            now = timezone.now()
            
            # 1. Iyun 2026 dan boshqa barcha oylar (Aprel, May, Iyul, Avgust va h.k.) qarzdorliklarini to'liq o'chiramiz
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
            print(f"🗑️ 1. O'chirilgan tarixiy va kelajakdagi TuitionMonth yozuvlari (Iyundan tashqari barchasi): {deleted_tms_count}")
            
            # 2. Iyun 2026 dan boshqa oylar to'lov taqsimotlarini ham o'chiramiz
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
            print(f"🗑️ 2. O'chirilgan PaymentAllocation yozuvlari (Iyundan tashqari barchasi): {deleted_allocs_count}")
            
            # 3. Barcha enrollmentlar credit_balance qiymatini vaqtincha 0 qilamiz (boshidan qayta hisoblash uchun)
            enrollments.update(credit_balance=0)
            print("🔄 3. Barcha enrollmentlar uchun credit_balance nollashtirildi.")
            
            # 4. FAQAT faol o'quvchilar uchun IYUN 2026 oyi qarzdorligini (TuitionMonth) boshidan yaratamiz
            active_enrollments = enrollments.filter(
                is_active=True,
                student__is_archived=False,
                group__is_archived=False,
                group__is_deleted=False
            )
            
            created_tms = 0
            for enr in active_enrollments:
                ensure_tuition_month(enr, target_month)
                created_tms += 1
            print(f"📝 4. Iyun 2026 oyi uchun yangi qarzlar yozildi: {created_tms} ta faol o'quvchi uchun.")
            
            # 5. Barcha mavjud to'lovlarni boshidan boshlab qayta taqsimlaymiz (reallocate)
            # Bu amal to'lovlarni faqat Iyun oyiga taqsimlaydi (chunki boshqa oylar o'chirilgan).
            reallocated_count = 0
            for enr in enrollments:
                reallocate_enrollment(enr)
                reallocated_count += 1
            print(f"⚡ 5. Barcha {reallocated_count} ta o'quvchi to'lovlari qayta taqsimlandi.")
            
            # 6. Agar to'lov qayta taqsimlanganda ortiqcha pul hisobiga kelgusi oylar (Iyul, Avgust) avtomat ochilib ketgan bo'lsa,
            # ularni o'chirib, o'sha ortiqcha pullarni o'quvchining "credit_balance" (oldindan to'lov balansi)ga o'tkazamiz.
            future_tms = TuitionMonth.objects.filter(
                enrollment__in=enrollments,
                month__gt=target_month
            )
            
            cleaned_future_tms = 0
            moved_credits_sum = 0
            
            for tm in future_tms:
                # Kelajak oyga taqsimlangan pul summasini yig'amiz
                alloc_sum = PaymentAllocation.objects.filter(
                    tuition_month=tm,
                    is_deleted=False
                ).aggregate(s=models.Sum("amount"))["s"] or 0
                
                if alloc_sum > 0:
                    # Ortiqcha pulni credit_balance ga qo'shamiz
                    Enrollment.objects.filter(pk=tm.enrollment_id).update(
                        credit_balance=models.F("credit_balance") + alloc_sum
                    )
                    moved_credits_sum += alloc_sum
                    
                # Kelajak oydagi taqsimotlarni soft-delete qilamiz
                PaymentAllocation.objects.filter(
                    tuition_month=tm,
                    is_deleted=False
                ).update(
                    is_deleted=True,
                    deleted_at=now,
                    deleted_reason="move_future_allocations_to_credit_balance"
                )
                
                # Kelajak oy TuitionMonth'ini soft-delete qilamiz
                TuitionMonth.objects.filter(pk=tm.id).update(
                    is_deleted=True,
                    deleted_at=now,
                    deleted_reason="move_future_allocations_to_credit_balance"
                )
                cleaned_future_tms += 1
                
            print(f"🛡️ 6. Kelajakdagi ortiqcha TuitionMonth yozuvlari o'chirildi: {cleaned_future_tms} ta.")
            if moved_credits_sum > 0:
                print(f"💰 Kelajak oylar uchun to'langan jami {moved_credits_sum:,} so'm pul o'quvchilar balansiga (credit_balance) xavfsiz o'tkazildi.")
            
            print("=" * 80)
            print("🎉 BARCHASI MUVAFFAQIYATLI TUGADI! Tranzaksiya saqlandi (committed).")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ XATO YUZ BERDI: {str(e)}")
        print("Baza holati o'zgartirilmadi (Rollback qilindi).")

if __name__ == "__main__":
    run_reset()
