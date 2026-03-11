from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Attendance, TeacherIncome, Enrollment


@receiver(post_save, sender=Attendance)
def create_teacher_income(sender, instance, created, **kwargs):
    # To'lanadigan holatlar: "present" (Keldi) YOKI "absent_unexcused" (Sababsiz)
    # SHUNINGDEK: instance.forced (backward compatibility uchun)
    is_billable = instance.status == 'present' or instance.status == 'absent_unexcused' or instance.forced or instance.present

    if not is_billable:
        # Agar to'lanmaydigan holat bo'lsa (masalan: Sababli), mavjud income bo'lsa o'chiramiz
        TeacherIncome.objects.filter(attendance=instance).delete()
        return

    try:
        enrollment = Enrollment.objects.get(
            group=instance.group,
            student=instance.student
        )
    except Enrollment.DoesNotExist:
        return

    # Daromadni hisoblaymiz
    kurs_narhi = enrollment.kurs_narhi or 0
    foiz = enrollment.oqituvchi_foiz or 0
    oy_dars_soni = instance.group.oy_dars_soni or 12

    if kurs_narhi > 0 and foiz > 0 and oy_dars_soni > 0:
        amount = round((kurs_narhi * foiz / 100) / oy_dars_soni)
    else:
        amount = 0

    # Mavjud bo'lsa yangilaymiz, bo'lmasa yaratamiz
    TeacherIncome.objects.update_or_create(
        attendance=instance,
        defaults={
            'center': instance.center or (instance.group.center if instance.group else None),
            'teacher': instance.teacher,
            'group': instance.group,
            'amount': amount
        }
    )

    # NOTE: Enrollment yaratilganda avtomatik TuitionMonth YARATILMAYDI.
    # Yangi qo'shilgan o'quvchi KEYINGI oydan boshlab qarzli hisoblanadi.
    # Qarzdorlar sahifasi (qarzdorlar_home) lazily yaratadi va ensure qiladi.
