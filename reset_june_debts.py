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
    else:
        # Avtomatik ravishda "proskill" yoki "proskill-center" ni qidiramiz (bo'shliqsiz)
        center = (
            Center.objects.filter(slug="proskill").first()
            or Center.objects.filter(slug="proskill-center").first()
            or Center.objects.filter(name__icontains="ProSkill").first()
        )

    if not center:
        print("❌ XATO: 'Pro Skill' nomli o'quv markazi topilmadi!")
        print("Mavjud markazlar ro'yxati:")
        for c in Center.objects.all():
            print(f" - Slug: {c.slug} | Nomi: {c.name}")
        return

    target_month = date(2026, 6, 1)  # Iyun 2026
    
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
            
            # A. Iyun 2026 va undan keyingi barcha qarz (TuitionMonth) yozuvlarini o'chiramiz
            tms_to_delete = TuitionMonth.objects.filter(
                enrollment__in=enrollments,
                month__gte=target_month
            )
            deleted_tms_count = tms_to_delete.count()
            tms_to_delete.update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="manual_reset_june_2026_and_later"
            )
            print(f"🗑️ 1. O'chirilgan TuitionMonth yozuvlari (Iyun 2026+): {deleted_tms_count}")
            
            # B. Iyun 2026 va undan keyingi oylar uchun to'lov taqsimotlarini (Allocations) o'chiramiz
            allocs_to_delete = PaymentAllocation.objects.filter(
                tuition_month__enrollment__in=enrollments,
                tuition_month__month__gte=target_month
            )
            deleted_allocs_count = allocs_to_delete.count()
            allocs_to_delete.update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="manual_reset_june_2026_and_later"
            )
            print(f"🗑️ 2. O'chirilgan PaymentAllocation yozuvlari (Iyun 2026+): {deleted_allocs_count}")
            
            # D. Balans va jami to'lovlarni boshidan to'g'ri hisoblash uchun credit_balance ni vaqtincha tozalaymiz
            enrollments.update(credit_balance=0)
            print("🔄 3. Barcha enrollmentlar uchun credit_balance nollashtirildi.")
            
            # E. FAQAT faol o'quvchilar uchun IYUN oyi qarzdorligini (TuitionMonth) boshidan yaratamiz
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
            
            # F. Barcha mavjud to'lovlarni boshidan boshlab qayta taqsimlaymiz (reallocate)
            reallocated_count = 0
            for enr in enrollments:
                reallocate_enrollment(enr)
                reallocated_count += 1
            print(f"⚡ 5. Barcha {reallocated_count} ta o'quvchi to'lovlari qayta taqsimlandi.")
            
            print("=" * 80)
            print("🎉 BARCHASI MUVAFFAQIYATLI TUGADI! Tranzaksiya saqlandi (committed).")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ XATO YUZ BERDI: {str(e)}")
        print("Baza holati o'zgartirilmadi (Rollback qilindi).")

if __name__ == "__main__":
    run_reset()
