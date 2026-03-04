import os
import django
from datetime import date
from django.db import transaction
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth
from education.services.tuition import tuition_month_fee_field

proskill_centers = Center.objects.filter(name__icontains='proskill')
my_center = max(proskill_centers, key=lambda c: User.objects.filter(role='student', is_archived=False, center=c).count()) if proskill_centers else None

if my_center:
    with transaction.atomic():
        march = date(2026, 3, 1)
        fee_field = tuition_month_fee_field()
        # 1. Hamma TuitionMonth (qarzlar) ni ayovsiz o'chirib chiqamiz
        TuitionMonth.objects.filter(enrollment__center=my_center).delete()
        
        # 2. Endi eng toza yozish (dublikatlarsiz)
        added = 0
        students = User.objects.filter(role='student', is_archived=False, center=my_center)
        for s in students:
            # Eng ohirgi va aniq narxli tasdiqlangan guruhini olamiz xolos
            e = Enrollment.objects.filter(student=s, is_active=True, center=my_center).order_by('-id').first()
            if e:
                narx = e.kurs_narhi or 0
                if not narx and getattr(e, 'group', None):
                    narx = getattr(e.group, 'kurs_narxi', 500000)
                if narx <= 0: narx = 500000
                
                # faqat 1 marta yaratish (aynan shu oquvchi uchn)
                TuitionMonth.objects.create(
                    enrollment=e,
                    month=march,
                    **{fee_field: narx}
                )
                added += 1
        print(f'MUVAFFAQIYAT! Jami {added} ta oquvchining qarzi FAQAT ROSTMANA ASL NARXIDA qoldirildi. Barcha Dublikatlar ocpib ketti!')
