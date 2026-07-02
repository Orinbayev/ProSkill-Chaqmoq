from django.db.models.signals import post_save, post_delete
from django.db.models import Q
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

    # 1. To'lanadigan holatlar: "Keldi", "Sababsiz" yoki "Kech qoldi"
    is_billable = instance.status in ('present', 'absent_unexcused', 'late') or getattr(instance, 'forced', False) or getattr(instance, 'present', False)

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

    kurs_narhi = enrollment.full_course_amount
    
    oy_dars_soni = instance.group.oy_dars_soni or 12
    if oy_dars_soni <= 0: oy_dars_soni = 12

    # OY LIMITI: faqat birinchi oy_dars_soni ta darsga to'lov yoziladi.
    # Misol: oy_dars_soni=12, lekin 13 dars o'tilsa — 13-chi darsga 0 yoziladi.
    month_paid_ids = list(
        Attendance.objects.filter(
            group=instance.group,
            student=instance.student,
            date__year=instance.date.year,
            date__month=instance.date.month,
            status__in=('present', 'absent_unexcused', 'late'),
        ).order_by('date', 'id').values_list('id', flat=True)[:oy_dars_soni]
    )
    if instance.pk not in month_paid_ids:
        TeacherIncome.objects.filter(attendance=instance).delete()
        return

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


@receiver(post_save, sender=Attendance)
def derive_student_activity_from_attendance(sender, instance, **kwargs):
    """Mirror billable Attendance rows into StudentActivity for the progress chart."""
    try:
        from education.services.progress_service import derive_activity_for_attendance
        derive_activity_for_attendance(instance)
    except Exception:
        pass


def _derive_student_activity_from_exam(sender, instance, **kwargs):
    try:
        from education.services.progress_service import derive_activity_for_exam
        derive_activity_for_exam(instance)
    except Exception:
        pass


def _register_exam_signal():
    try:
        from education.models import ExamResult
        post_save.connect(
            _derive_student_activity_from_exam,
            sender=ExamResult,
            dispatch_uid="derive_student_activity_from_exam",
        )
    except Exception:
        pass


_register_exam_signal()

from django.contrib.auth import get_user_model
User = get_user_model()

@receiver(post_save, sender=Enrollment)
@receiver(post_save, sender=Group)
@receiver(post_save, sender=User)
def handle_rate_change(sender, instance, update_fields=None, **kwargs):
    """
    Kurs narxi yoki foiz o'zgarganda tegishli barcha ochiq oylar daromadlarini qayta hisoblaydi.

    PERF: Agar `update_fields` berilgan bo'lsa va unda narx/foiz fieldlari yo'q bo'lsa,
    qayta hisoblash o'tkazib yuboriladi. Bu login paytida Django'ning
    `update_last_login` signal'i (`user.save(update_fields=['last_login'])`)
    teacher uchun ortiqcha 3000+ query tug'dirayotganini bartaraf etadi.
    """
    from .models import Attendance

    if isinstance(instance, Group):
        # Group'da narx/ustoz o'zgargandagina qayta hisobla.
        if update_fields is not None and not (update_fields & {"oqituvchi", "oqituvchi_id", "kurs_narxi", "kurs_narhi", "narx"}):
            return
        atts = Attendance.objects.filter(group=instance)
    elif isinstance(instance, Enrollment):
        if update_fields is not None and not (update_fields & {"kurs_narxi", "kurs_narhi", "narx", "group", "group_id", "student", "student_id"}):
            return
        atts = Attendance.objects.filter(group=instance.group, student=instance.student)
    elif isinstance(instance, User) and instance.role == 'teacher':
        # Faqat oqituvchi_foizi o'zgarganda. `update_last_login` va parol
        # update'lari bu signalni ishga tushirmasin.
        if update_fields is not None and "oqituvchi_foizi" not in update_fields:
            return
        atts = Attendance.objects.filter(group__oqituvchi=instance)
    else:
        return

    for att in atts:
        create_teacher_income(Attendance, att, created=False)

    # NOTE: Enrollment yaratilganda avtomatik TuitionMonth YARATILMAYDI.
    # Yangi qo'shilgan o'quvchi KEYINGI oydan boshlab qarzli hisoblanadi.
    # Qarzdorlar sahifasi (qarzdorlar_home) lazily yaratadi va ensure qiladi.


@receiver(post_save, sender=Attendance, dispatch_uid="recalc_inactive_tuition_on_att_save")
@receiver(post_delete, sender=Attendance, dispatch_uid="recalc_inactive_tuition_on_att_delete")
def recalc_enrollment_tuition_on_att_change(sender, instance, **kwargs):
    """
    Davomat qo'shilganda, o'zgartirilganda yoki o'chirilganda TuitionMonth
    fee ni qayta hisoblaydi.

    Inactive enrollment (chiqarilgan): har qanday oy uchun ensure_tuition_month
    → tuition_month_lesson_count davomat asosida hisoblaydi.

    Active enrollment + O'TGAN oy: TuitionMonth.fee_amount ni attendance_based_fee
    bilan yangilaymiz — davomat 0 bo'lsa fee 0 ga tushadi.

    Active enrollment + JORIY oy: tegilmasin — schedule asosida billing to'g'ri.
    """
    try:
        from .models import FinancialMonth
        from django.utils import timezone

        center = getattr(instance, "center", None) or (
            instance.group.center if instance.group else None
        )
        att_date = instance.date
        if center and att_date:
            if FinancialMonth.objects.filter(
                center=center,
                year=att_date.year,
                month=att_date.month,
                is_closed=True,
            ).exists():
                return  # Yopilgan oy — tegilmasin

        from education.services.tuition import ensure_tuition_month, month_first_day
        att_month = month_first_day(att_date)
        current_month = timezone.localdate().replace(day=1)

        # Avval inactive enrollment ni tekshiramiz
        inactive_enr = (
            Enrollment.all_objects
            .select_related("group", "student", "group__center", "course")
            .filter(student=instance.student, group=instance.group)
            .filter(Q(is_active=False) | Q(is_deleted=True))
            .first()
        )
        if inactive_enr is not None:
            ensure_tuition_month(inactive_enr, att_month)
            return

        # Active enrollment + o'tgan oy: attendance_based_fee bilan yangilaymiz
        if att_month >= current_month:
            return  # Joriy yoki kelajak oy — tegilmasin

        active_enr = (
            Enrollment.all_objects
            .select_related("group", "student", "group__center", "course")
            .filter(
                student=instance.student,
                group=instance.group,
                is_active=True,
                is_deleted=False,
            )
            .first()
        )
        if active_enr is None:
            return

        from .models import TuitionMonth as _TM
        from education.services.tuition import attendance_based_fee, tuition_month_fee_field

        tm = _TM.objects.filter(
            enrollment=active_enr, month=att_month, is_deleted=False
        ).first()
        if tm is None:
            return  # TuitionMonth yo'q — hech narsa qilmaymiz

        _protected_reason = getattr(tm, "deleted_reason", None) or ""
        if (
            _protected_reason == "manual_cleared"
            or _protected_reason.startswith(("cleanup_", "move_future_", "reset_"))
        ):
            return  # Himoyalangan — tegilmasin

        fee_field = tuition_month_fee_field()
        new_fee = attendance_based_fee(active_enr, att_month)
        if int(getattr(tm, fee_field, 0) or 0) != new_fee:
            setattr(tm, fee_field, new_fee)
            tm.save(update_fields=[fee_field])
    except Exception:
        pass
