from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Attendance, TeacherIncome, Enrollment, Group


@receiver(post_save, sender=Attendance)
def create_teacher_income(sender, instance, created, **kwargs):
    """
    Davomat saqlanganda o'qituvchining darslik ulushini (TeacherIncome) hisoblaydi.
    """
    # 0. MOLIYA YOPILGANLIKKA TEKSHIRAMIZ (TARIXIY HIMOYALANISH)
    # Agar bu oy yopilgan bo'lsa (Moliya muzlatilgan), hech qanday o'zgartirish qilish mumkin emas!
    from .models import FinancialMonth
    center = instance.center or (instance.group.center if instance.group else None)
    if center and instance.date:
        closed = FinancialMonth.objects.filter(center=center, year=instance.date.year, month=instance.date.month, is_closed=True).exists()
        if closed:
            return  # QULFLANGAN OY - tegilmasin!

    # 1. To'lanadigan holatlar: "Keldi" yoki "Sababsiz"
    is_billable = instance.status == 'present' or instance.status == 'absent_unexcused' or getattr(instance, 'forced', False) or getattr(instance, 'present', False)

    if not is_billable:
        # To'lanmaydigan holatda (Sababli) eski yozuvni o'chiradi
        TeacherIncome.objects.filter(attendance=instance).delete()
        return

    # 2. O'quvchining ushbu guruhdagi faol Enrollmentini topish
    try:
        from .models import Enrollment
        enrollment = Enrollment.all_objects.filter(
            group=instance.group,
            student=instance.student,
        ).order_by('-is_active', '-created_at').first()
        
        if not enrollment:
            return
    except Exception:
        return

    # 4. Yozuvni yangilash yoki yaratish (FAQAT guruh o'qituvchisiga yozamiz)
    teacher = instance.group.oqituvchi if instance.group else None
    if not teacher:
        return

    # 3. Daromad mantiqiy hisobi
    # MUHIM: Foydalanuvchi talabiga ko'ra, O'qituvchi profildagi foiz MASTER (asosiy) hisoblanadi.
    # Agar profildagi foiz 0 bo'lmasa, uni ishlatamiz.
    foiz = getattr(teacher, 'oqituvchi_foizi', 0)
    
    # Agar o'qituvchi profilida foiz bo'lmasa (0 bo'lsa), unda Enrollmentdagi foizga qaraymiz
    if foiz is None or foiz == 0:
        foiz = enrollment.oqituvchi_foiz
        
    kurs_narhi = enrollment.kurs_narhi or 0
    
    oy_dars_soni = instance.group.oy_dars_soni or 12
    if oy_dars_soni <= 0: oy_dars_soni = 12

    if kurs_narhi > 0 and foiz > 0:
        total_per_lesson = kurs_narhi / oy_dars_soni
        amount = round(total_per_lesson * (foiz / 100))
        center_amount = round(total_per_lesson * ((100 - foiz) / 100))
        total_amount = round(total_per_lesson)
    else:
        amount = 0
        center_amount = 0
        total_amount = 0

    TeacherIncome.objects.update_or_create(
        attendance=instance,
        defaults={
            'center': instance.center or (instance.group.center if instance.group else None),
            'teacher': teacher,
            'group': instance.group,
            'amount': amount,
            'center_amount': center_amount,
            'total_amount': total_amount
        }
    )

from django.contrib.auth import get_user_model
User = get_user_model()

@receiver(post_save, sender=Enrollment)
@receiver(post_save, sender=Group)
@receiver(post_save, sender=User)
def handle_rate_change(sender, instance, **kwargs):
    """
    Kurs narxi yoki foiz o'zgarganda tegishli barcha ochiq oylar daromadlarini qayta hisoblaydi.
    """
    from .models import Attendance
    
    if isinstance(instance, Group):
        atts = Attendance.objects.filter(group=instance)
    elif isinstance(instance, Enrollment):
        atts = Attendance.objects.filter(group=instance.group, student=instance.student)
    elif isinstance(instance, User) and instance.role == 'teacher':
        # Agar o'qituvchi o'z foizini o'zgartirsa, barcha tegishli davomatlar qayta hisoblanadi.
        atts = Attendance.objects.filter(group__oqituvchi=instance)
    else:
        return
        
    for att in atts:
        create_teacher_income(Attendance, att, created=False)

    # NOTE: Enrollment yaratilganda avtomatik TuitionMonth YARATILMAYDI.
    # Yangi qo'shilgan o'quvchi KEYINGI oydan boshlab qarzli hisoblanadi.
    # Qarzdorlar sahifasi (qarzdorlar_home) lazily yaratadi va ensure qiladi.
