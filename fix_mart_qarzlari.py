import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Sum
from education.models import Enrollment, TuitionMonth, PaymentAllocation
from education.services.tuition import tuition_month_fee_field, ensure_tuition_month, reallocate_enrollment

def fix_debts():
    fee_field = tuition_month_fee_field()
    march = date(2026, 3, 1)

    print("Qarzdorliklarni to'g'irlash boshlandi...")

    # Faqat faol o'quvchilar va faol guruhlarni olamiz
    enrollments = Enrollment.objects.filter(is_active=True, student__is_archived=False)

    count_updated = 0
    for e in enrollments:
        # 1. Barcha eski oylar qarzlarini nollash (avvalgi hisob-kitob nol qilinadi ki, qarz bo'lmasin)
        past_months = TuitionMonth.objects.filter(enrollment=e, month__lt=march)
        for pm in past_months:
            paid = PaymentAllocation.objects.filter(tuition_month=pm).aggregate(s=Sum("amount"))["s"] or 0
            if getattr(pm, fee_field, 0) != paid:
                setattr(pm, fee_field, paid)
                pm.save(update_fields=[fee_field])

        # 2. Faqat joriy Mart oyi uchun narxni o'rnatamiz
        tm_march = ensure_tuition_month(e, march)
        narx = e.kurs_narhi
        if not narx and e.group:
            narx = getattr(e.group, "kurs_narxi", 0) or getattr(e.group, "kurs_narhi", 0) or 0
        
        setattr(tm_march, fee_field, narx)
        tm_march.save(update_fields=[fee_field])

        # 3. Pullar qayta tartibli taqsimlanishi uchun qayta hisoblash base funksiyasi orqali ishga tushiramiz
        try:
            reallocate_enrollment(e)
        except Exception:
            pass
            
        count_updated += 1

    print(f"MUVAFFAQIYATLI BAJARILDI! Jami {count_updated} ta guruhga biriktirilgan o'quvchiga FAQAT Mart oyi qarzi belgilandi (eskilari olib tashlandi).")


if __name__ == '__main__':
    fix_debts()
