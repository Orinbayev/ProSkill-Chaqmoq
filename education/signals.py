from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Attendance, TeacherIncome, Enrollment

@receiver(post_save, sender=Attendance)
def create_teacher_income(sender, instance, created, **kwargs):
    if not created or not instance.present:
        return

    try:
        enrollment = Enrollment.objects.get(
            group=instance.group,
            student=instance.student
        )
    except Enrollment.DoesNotExist:
        return  # Enrollment yo‘q bo‘lsa, chiqib ketamiz

    # Daromadni hisoblaymiz: kurs narxidan foiz va oyga nisbatan
    kurs_narhi = enrollment.kurs_narhi or 0
    foiz = enrollment.oqituvchi_foiz or 0
    oy_dars_soni = instance.group.oy_dars_soni or 12  # default: 12

    if kurs_narhi > 0 and foiz > 0 and oy_dars_soni > 0:
        amount = round((kurs_narhi * foiz / 100) / oy_dars_soni)
    else:
        amount = 0

    TeacherIncome.objects.get_or_create(
        attendance=instance,
        teacher=instance.teacher,
        group=instance.group,  # 🔥 BU MUHIM!
        defaults={'amount': amount}
    )

