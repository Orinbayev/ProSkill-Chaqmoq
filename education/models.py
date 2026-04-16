from django.db import models
from django.conf import settings
from accounts.models import Center
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
User = settings.AUTH_USER_MODEL
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum
from django.db.models.signals import pre_save
from django.dispatch import receiver
from decimal import Decimal
import uuid
from django.db import models
from django.conf import settings
from django.db.models import Sum
from django.db.models import Q
from core.soft_delete import SoftDeleteMixin

# education/models.py
from django.db import models
from django.conf import settings


class Group(SoftDeleteMixin, models.Model):
    LANG = "lang"
    IT = "it"
    CATEGORY_CHOICES = (
        (LANG, "Tillar"),
        (IT, "IT"),
    )

    category = models.CharField(max_length=8, choices=CATEGORY_CHOICES, default=LANG)

    category_obj = models.ForeignKey(
        "education.Category",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="groups",
        verbose_name="Bo‘lim (Category)"
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE)
    branch = models.ForeignKey(
        "accounts.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="groups",
        verbose_name="Filial",
    )
    nom = models.CharField(max_length=150)
    izoh = models.TextField(blank=True)

    oqituvchi = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={"role": "teacher"},
    )

    tuzilgan = models.DateTimeField(auto_now_add=True)

    kurs_narxi = models.PositiveIntegerField(default=500000, help_text="Bir oylik to‘lov (so‘mda)")
    oqituvchi_foiz = models.PositiveIntegerField(default=40, help_text="O‘qituvchi foizi (%)")
    oy_dars_soni = models.PositiveIntegerField(default=12, help_text="Bir oyda nechta dars bo‘ladi")
    max_students = models.PositiveSmallIntegerField(default=15, verbose_name="Maksimal o'quvchi soni")

    # Course duration planning (backward-compatible)
    course_start_date = models.DateField(null=True, blank=True, verbose_name="Kurs boshlanish sanasi")
    duration_months = models.PositiveSmallIntegerField(default=0, verbose_name="Davomiyligi (oy)")
    lessons_per_week = models.PositiveSmallIntegerField(default=3, verbose_name="Haftalik darslar soni")
    estimated_end_date = models.DateField(null=True, blank=True, verbose_name="Taxminiy tugash sanasi")
    schedule_estimation_note = models.CharField(
        max_length=255,
        blank=True,
        default="Bu sana taxminiy hisob bo‘lib, bayramlar, tadbirlar yoki dars ko‘chirilishlari sabab o‘zgarishi mumkin",
        verbose_name="Tahmin izohi",
    )
    estimated_end_date_manual = models.BooleanField(default=False, verbose_name="Taxminiy sana qo'lda belgilang")

    is_archived = models.BooleanField(default=False, verbose_name="Arxivlangan")
    # Group closure foundation (DB bilan backward-compatible sync)
    is_closed = models.BooleanField(default=False, verbose_name="Yopilganmi?")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_groups",
    )

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"

    def __str__(self):
        return self.nom

    def dars_boshiga_tolov(self) -> float:
        if self.kurs_narxi > 0 and self.oqituvchi_foiz > 0 and self.oy_dars_soni > 0:
            return round((self.kurs_narxi * self.oqituvchi_foiz / 100) / self.oy_dars_soni, 2)
        return 0.0


class GroupSchedule(models.Model):
    MON = 1
    TUE = 2
    WED = 3
    THU = 4
    FRI = 5
    SAT = 6
    SUN = 7

    WEEKDAY_CHOICES = [
        (1, "Dushanba"),
        (2, "Seshanba"),
        (3, "Chorshanba"),
        (4, "Payshanba"),
        (5, "Juma"),
        (6, "Shanba"),
        (7, "Yakshanba"),
    ]

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="schedules")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="schedules")
    weekday = models.SmallIntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    room = models.CharField(max_length=60, blank=True, default="")

    class Meta:
        unique_together = (("group", "weekday", "start_time"),)
        ordering = ("weekday", "start_time")
        verbose_name = "Dars jadvali"
        verbose_name_plural = "Dars jadvallari"

    def __str__(self):
        return f"{self.group.nom} / {self.weekday_uz} / {self.time_range}"

    @property
    def weekday_uz(self):
        return dict(self.WEEKDAY_CHOICES).get(self.weekday, "")

    @property
    def time_range(self):
        start = self.start_time.strftime("%H:%M")
        if self.end_time:
            return f"{start}–{self.end_time.strftime('%H:%M')}"
        return start


class Oquvchi(models.Model):
    """Guruhdagi o‘quvchi"""
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    ism = models.CharField(max_length=100)
    guruh = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='oquvchilar')
    tolov = models.PositiveIntegerField(default=0, help_text="O‘quvchining oylik to‘lovi (so‘mda)")

    def __str__(self):
        return f"{self.ism} ({self.guruh.nom})"


class Dars(models.Model):
    """Har bir o‘qituvchining darslari"""
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    guruh = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='darslar')
    oqituvchi = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sana = models.DateField(auto_now_add=True)
    davom_etilgan = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.guruh.nom} - {self.sana}"


class OylikHisobot(models.Model):
    """Avtomatik oylik hisobot jadvali"""
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    oqituvchi = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    oy = models.CharField(max_length=15)
    yil = models.IntegerField()
    jami_darslar = models.PositiveIntegerField(default=0)
    jami_daromad = models.PositiveIntegerField(default=0)
    markaz_foydasi = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.oqituvchi} — {self.oy} {self.yil}"


    
class GroupStudent(models.Model):
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='students')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Guruhdagi o‘quvchi"
        verbose_name_plural = "Guruhdagi o‘quvchilar"

    def __str__(self):
        return f"{self.student.get_full_name()} → {self.group.nom}"



class Enrollment(SoftDeleteMixin, models.Model):
    group = models.ForeignKey(
        "education.Group",
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Guruh",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "student"},
        verbose_name="O‘quvchi",
    )
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    # oy narxi (Enrollment darajasida saqlaymiz)
    kurs_narhi = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Oylik kurs narxi (so‘mda)",
    )

    oqituvchi_foiz = models.PositiveIntegerField(
        default=40,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="O‘qituvchi ulushi (%)",
    )

    is_active = models.BooleanField(default=True, verbose_name="Faolmi?")
    is_deferred = models.BooleanField(default=False, verbose_name="Kechiktirilganmi?")
    student_payable_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=None,
        verbose_name="O'quvchidan olinadigan summa (so'mda)",
        help_text="O‘quvchidan real olinadigan summa. Bo‘sh bo‘lsa, to‘liq kurs narxi olinadi.",
    )

    # umumiy to‘langan (avto update bo‘ladi)
    jami_tolangan = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Jami to‘langan (so‘mda)",
    )

    class Meta:
        unique_together = ("group", "student")
        verbose_name = "Guruhga qo‘shilish"
        verbose_name_plural = "Guruhga qo‘shilishlar"
        ordering = ["group", "student"]
        indexes = [
            models.Index(fields=["center", "is_active", "is_deleted"], name="enr_center_active_idx"),
            models.Index(fields=["group", "is_active"], name="enr_group_active_idx"),
            models.Index(fields=["student", "is_active"], name="enr_student_active_idx"),
        ]

    def __str__(self):
        ism = getattr(self.student, "ism", "")
        familya = getattr(self.student, "familya", "")
        return f"{ism} {familya} → {self.group.nom}"

    @property
    def full_course_amount(self) -> int:
        enr_fee = getattr(self, "kurs_narhi", None)
        if enr_fee not in (None, ""):
            return int(enr_fee or 0)

        group = getattr(self, "group", None)
        if not group:
            return 0

        return int(getattr(group, "kurs_narxi", 0) or getattr(group, "kurs_narhi", 0) or 0)

    @property
    def effective_student_payable_amount(self) -> int:
        if self.student_payable_amount not in (None, ""):
            return int(self.student_payable_amount or 0)
        return self.full_course_amount

    def clean(self):
        super().clean()

        if self.student_payable_amount is None:
            return

        full_amount = self.full_course_amount
        if self.student_payable_amount > full_amount:
            raise ValidationError({
                "student_payable_amount": "O'quvchidan olinadigan summa kurs narxidan katta bo'lishi mumkin emas."
            })

    @property
    def oqituvchi_daromadi(self) -> int:
        """
        Bu - 1 oy uchun o‘qituvchining full (100% dars) daromadi.
        Davomatga qarab kamayishi/ko‘payishi boshqa metodda hisoblanadi.
        """
        return round(self.full_course_amount * (self.oqituvchi_foiz or 0) / 100)

    def real_oqituvchi_daromadi(self, year=None, month=None) -> int:
        """
        Real o‘qituvchi daromadi (davomatga qarab):
        - Group.oy_dars_soni ga nisbatan hisoblanadi
        - faqat tanlangan year/month bo‘yicha Attendance lar olinadi
        - present=True yoki forced=True bo‘lsa "kelgan" hisoblanadi

        year/month berilmasa: hamma vaqt bo‘yicha hisoblaydi (eski kabi).
        """

        # 1) Guruhda oyiga nechta dars bor?
        total_lessons = getattr(self.group, "oy_dars_soni", 0) or 0
        if total_lessons <= 0:
            return 0

        # 2) Attendance larni olish (student + group)
        # ⚠️ Sizda: group.attendances ishlatyapsiz, shuning uchun shu yo‘l to‘g‘ri.
        qs = self.group.attendances.filter(student=self.student)

        # 3) Agar year/month berilgan bo‘lsa o‘sha oy bo‘yicha filter
        if year and month:
            qs = qs.filter(date__year=year, date__month=month)

        # 4) Kelganlar soni (present=True yoki forced=True)
        attended = qs.filter(Q(present=True) | Q(forced=True)).count()

        # 5) Proporsiya: attended / total_lessons
        ratio = attended / total_lessons

        # 6) Oylik full daromad * ratio
        return round(self.oqituvchi_daromadi * ratio)
    

    
class Payment(SoftDeleteMixin, models.Model):
    PAYMENT_TYPES = (
        ("cash", "Naqd"),
        ("card", "Karta"),
        ("mixed", "Aralash"),
    )

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
    )

    # qulay access uchun (read-only sifatida ishlatamiz)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        verbose_name="O‘quvchi",
    )
    group = models.ForeignKey(
        "education.Group",
        on_delete=models.CASCADE,
        related_name="group_payments",
        verbose_name="Guruh",
    )
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)

    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES, default="cash")

    cash_amount = models.PositiveIntegerField(default=0, verbose_name="Naqd (so'mda)")

    # karta valyutada bo‘lishi ham mumkin
    card_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Karta summasi")
    card_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1, verbose_name="Kurs")
    card_currency = models.CharField(max_length=10, default="UZS", verbose_name="Karta valyutasi")

    note = models.TextField(blank=True, null=True, verbose_name="Izoh")

    # Umumiy so‘m (hisoblab saqlaymiz)
    summa = models.PositiveIntegerField(default=0, verbose_name="Jami (so‘mda)")

    paid_date = models.DateField(default=timezone.localdate, verbose_name="To‘lov sanasi")
    paid_time = models.TimeField(default=timezone.now, verbose_name="To‘lov vaqti")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments",
        verbose_name="Kiritgan xodim"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "To‘lov"
        verbose_name_plural = "To‘lovlar"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=['paid_date', 'center']),
            models.Index(fields=['group']),
            models.Index(fields=['center', 'is_deleted', 'paid_date'], name="pay_center_del_date_idx"),
            models.Index(fields=['enrollment', 'is_deleted'], name="pay_enr_del_idx"),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.summa:,} so‘m ({self.paid_date})"

    @property
    def card_amount_som(self) -> int:
        return int((self.card_amount or Decimal("0")) * (self.card_rate or Decimal("1")))

    def save(self, *args, **kwargs):
        # 1) Enrollment/student/group mosligini kafolatlaymiz
        if self.enrollment_id:
            if not self.student_id:
                self.student_id = self.enrollment.student_id
            if not self.group_id:
                self.group_id = self.enrollment.group_id

        # 2) Center ni avtomatik aniqlash
        if not self.center_id:
            if self.group_id and hasattr(self.group, 'center'):
                self.center = self.group.center
            elif self.enrollment_id and hasattr(self.enrollment, 'group'):
                self.center = self.enrollment.group.center

        # 3) Umumiy summa
        self.summa = int(self.cash_amount or 0) + int(self.card_amount_som or 0)

        super().save(*args, **kwargs)

        # 4) Enrollment jami_tolangan ni yangilaymiz
        agg = Payment.objects.filter(enrollment_id=self.enrollment_id).aggregate(s=Sum("summa"))
        Enrollment.objects.filter(pk=self.enrollment_id).update(jami_tolangan=agg["s"] or 0)

        # 5) ✅ PAYMENT BONUS: 100% to'lov bo'lsa chaqmoq bonus bering
        if self.enrollment_id:
            try:
                enr = Enrollment.objects.get(pk=self.enrollment_id)
                from chaqmoq.services import check_payment_bonus, check_payment_discipline_bonus
                
                # Standart 100% to'lov bonusi
                check_payment_bonus(
                    enrollment=enr,
                    center=enr.center,
                    created_by=self.created_by,
                )
            except Exception:
                pass  # Xato bo'lsa ham asosiy to'lovni buzmalik







# ====== YANGI: Davomat ======

class Attendance(models.Model):
    """
    Har bir guruh uchun alohida davomat.
    Masalan, bir o‘quvchi bir kunda IT va English guruhida qatnashsa,
    ikkita alohida Attendance yozuvi bo‘ladi.
    """
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Guruh"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},
        verbose_name="O‘quvchi"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='taken_attendances',
        limit_choices_to={'role': 'teacher'},
        verbose_name="O‘qituvchi"
    )
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)

    date = models.DateField(
        default=timezone.localdate,
        verbose_name="Sana"
    )

    # 🔥 YANGI STATUS MAYDONI
    STATUS_CHOICES = (
        ('present', 'Keldi'),
        ('absent_excused', 'Sababli (Kelmadi)'),
        ('absent_unexcused', 'Sababsiz (Kelmadi)'),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='present', verbose_name="Holati"
    )

    # Eski maydon. Backward compatibility uchun
    present = models.BooleanField(
        default=False,
        verbose_name="Kelganmi"
    )

    # Eski maydon
    forced = models.BooleanField(
        default=False,
        verbose_name="Kelmadi – lekin o‘qituvchiga pul yozilsin"
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_attendances", verbose_name="Kiritgan xodim"
    )

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"
        unique_together = ('group', 'student', 'date')  # 🔥 Har bir guruh uchun alohida davomat
        ordering = ['-date']

    def __str__(self):
        if self.status == 'present' or self.present:
            belgi = "✅ Kelgan"
        elif self.status == 'absent_excused':
            belgi = "🟡 Sababli Kelmadi"
        elif self.status == 'absent_unexcused':
            belgi = "🔴 Sababsiz Kelmadi"
        elif self.forced:
            belgi = "🔴 Kelmadi (pul yozildi)"
        else:
            belgi = "❌ Kelmadi"

        return f"{self.date} | {self.group.nom} | {self.student.get_full_name()} | {belgi}"

    def save(self, *args, **kwargs):
        """Davomat saqlanganda avtomatik o‘qituvchi belgilanadi."""

        # Sana bo‘lmasa — avtomatik qo‘yamiz
        if not self.date:
            self.date = timezone.localdate()

        # O‘qituvchi bo‘lmasa — guruh o‘qituvchisini avtomatik bog‘laymiz
        if not self.teacher and hasattr(self.group, 'oqituvchi'):
            self.teacher = self.group.oqituvchi

        super().save(*args, **kwargs)


class AttendanceHistory(models.Model):
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    date = models.DateField()
    is_present = models.BooleanField(default=False)
    plus_coin = models.IntegerField(default=0)
    minus_coin = models.IntegerField(default=0)

    class Meta:
        unique_together = (('student', 'date'), ('center', 'student', 'date'))
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.date} — {'✅' if self.is_present else '❌'}"


class DailyLightningRecord(models.Model):
    """
    Har bir student/guruh/sana uchun kunlik chaqmoq o'zgarishi.
    Bu jadval UI uchun kunlik ko'rinishni ajratadi, umumiy balans esa
    LightningHistory orqali hisoblanadi.
    """
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="daily_lightning_records")
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        related_name="daily_lightning_records",
    )
    date = models.DateField()
    attendance_status = models.CharField(max_length=20, blank=True, default="")
    plus_points = models.IntegerField(default=0)
    minus_points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("group", "student", "date"), ("center", "group", "student", "date"))
        ordering = ("-date", "-updated_at")
        verbose_name = "Kunlik chaqmoq yozuvi"
        verbose_name_plural = "Kunlik chaqmoq yozuvlari"

    def __str__(self):
        return f"{self.student.get_full_name()} | {self.group.nom} | {self.date} (+{self.plus_points} / {self.minus_points})"


class Category(SoftDeleteMixin, models.Model):
    """Guruhlar kategoriyasi (masalan: Tillar, IT, Dizayn...)"""
    name = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    icon = models.CharField(max_length=10, blank=True, null=True, help_text="Emoji yoki belgi masalan 💻 📘 🎨")
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True, verbose_name="Bo‘lim rasmi")

    class Meta:
        unique_together = ('name', 'center')

    def __str__(self):
        return f"{self.name} ({self.center.name if self.center else 'Global'})"


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    center = models.ForeignKey(Center, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name()


class DailyLightningSetting(models.Model):
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    max_lightning = models.PositiveIntegerField(default=0)  # 0 → cheklanmagan
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Kunlik chaqmoq limiti"
        verbose_name_plural = "Kunlik chaqmoq limitlari"
        unique_together = ('center', 'date')

    def __str__(self):
        return f"{self.date} — {self.max_lightning or 'Cheklanmagan'}"

class TeacherIncome(models.Model):
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teacher_incomes")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="teacher_incomes")
    attendance = models.OneToOneField(Attendance, on_delete=models.CASCADE, related_name="teacher_income_record")
    
    amount = models.PositiveIntegerField(default=0, verbose_name="O'qituvchi ulushi")
    center_amount = models.PositiveIntegerField(default=0, verbose_name="Markaz ulushi")
    total_amount = models.PositiveIntegerField(default=0, verbose_name="Umumiy aylanma")
    
    created_at = models.DateTimeField(auto_now_add=True)



@receiver(pre_save, sender=Payment)
def auto_attach_enrollment(sender, instance, **kwargs):
    """
    ✅ To‘lov saqlanayotganda agar enrollment berilmagan bo‘lsa —
    o‘quvchini va guruhni aniqlab, to‘g‘ri Enrollment yozuviga bog‘laydi.
    """
    # Agar enrollment allaqachon bor bo‘lsa — chiqamiz
    if instance.enrollment_id:
        return

    # Agar instance’da student yoki group haqida ma’lumot yo‘q bo‘lsa — hech narsa qilmaymiz
    # (ya’ni Payment yaratishda bu ma’lumotlar yo‘q bo‘lsa)
    student_id = getattr(instance, "student_id", None)
    group_id = getattr(instance, "group_id", None)

    if not student_id or not group_id:
        return

    # Endi Enrollment’ni topamiz
    enroll = Enrollment.objects.filter(group_id=group_id, student_id=student_id).first()
    if enroll:
        instance.enrollment = enroll








class TuitionMonth(SoftDeleteMixin, models.Model):
    """
    Har bir Enrollment uchun har oy narx.
    month = oy 1-kuni (2026-01-01)
    """
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    enrollment = models.ForeignKey(
        "education.Enrollment",
        on_delete=models.CASCADE,
        related_name="tuition_months",
    )
    month = models.DateField()  # always first day of month
    fee_amount = models.PositiveIntegerField(default=0)  # oylik narx (so'm)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("enrollment", "month"), ("center", "enrollment", "month"))
        ordering = ("month",)
        indexes = [
            models.Index(fields=["enrollment", "month", "is_deleted"], name="tm_enr_month_idx"),
            models.Index(fields=["center", "month", "is_deleted"], name="tm_center_month_idx"),
        ]

    def __str__(self):
        return f"enr#{self.enrollment_id} - {self.month} - {self.fee_amount}"


class PaymentAllocation(SoftDeleteMixin, models.Model):
    """
    Payment qaysi oy(lar)ni yopganini yozib boradi.
    Masalan: 600k payment -> Jan 550k + Feb 50k
    """
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(
        "education.Payment",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    tuition_month = models.ForeignKey(
        "education.TuitionMonth",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    amount = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            try:
                from chaqmoq.services import check_payment_discipline_bonus
                check_payment_discipline_bonus(
                    enrollment=self.tuition_month.enrollment,
                    center=self.center or self.payment.center,
                    created_by=self.payment.created_by
                )
            except Exception:
                pass

    class Meta:
        ordering = ("tuition_month__month", "id")
        indexes = [
            models.Index(fields=["tuition_month", "is_deleted"], name="pa_tm_deleted_idx"),
            models.Index(fields=["payment", "is_deleted"], name="pa_payment_deleted_idx"),
        ]

    def __str__(self):
        return f"pay#{self.payment_id} -> {self.tuition_month.month}: {self.amount}"


class CenterExpense(models.Model):
    CATEGORY_RENT = "rent"
    CATEGORY_SALARY = "salary"
    CATEGORY_UTILITY = "utility"
    CATEGORY_EQUIPMENT = "equipment"
    CATEGORY_MARKETING = "marketing"
    CATEGORY_OTHER = "other"

    CATEGORY_CHOICES = [
        (CATEGORY_RENT, "Ijara"),
        (CATEGORY_SALARY, "Xodim maoshi"),
        (CATEGORY_UTILITY, "Kommunal"),
        (CATEGORY_EQUIPMENT, "Jihozlar"),
        (CATEGORY_MARKETING, "Reklama"),
        (CATEGORY_OTHER, "Boshqa"),
    ]

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.PositiveIntegerField()
    description = models.CharField(max_length=255, blank=True)
    date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_category_display()} — {self.amount}"


class TeacherCompensationRule(models.Model):
    COMPENSATION_TYPES = (
        ("PERCENT", "Percent"),
        ("FIXED", "Fixed"),
        ("PER_STUDENT", "Per Student"),
        ("PER_LESSON", "Per Lesson"),
    )
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="compensation_rules")
    type = models.CharField(max_length=20, choices=COMPENSATION_TYPES, default="PERCENT")
    percent = models.PositiveIntegerField(null=True, blank=True)
    fixed_amount = models.BigIntegerField(null=True, blank=True)
    per_student_amount = models.BigIntegerField(null=True, blank=True)
    per_lesson_amount = models.BigIntegerField(null=True, blank=True)
    effective_from = models.DateField(default=timezone.localdate)
    active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-effective_from']

class SalaryPayout(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="salary_payouts")
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    period_year = models.IntegerField()
    period_month = models.IntegerField()
    amount = models.BigIntegerField()
    paid_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-paid_at']
        indexes = [
            models.Index(fields=['teacher', 'period_year', 'period_month', 'center']),
        ]

class TeacherExpectedIncomeSnapshot(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="expected_snapshots")
    center = models.ForeignKey("accounts.Center", on_delete=models.SET_NULL, null=True, blank=True)
    year = models.IntegerField()
    month = models.IntegerField()
    active_students = models.IntegerField(default=0)
    expected_income = models.BigIntegerField(default=0)
    income_per_student = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-year', '-month']
        indexes = [
            models.Index(fields=['teacher', 'year', 'month', 'center']),
        ]
        unique_together = [['teacher', 'year', 'month', 'center']]


class StudentGroupHistory(models.Model):
    """Tracks student's membership in a group over time for accurate historical calculations."""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_history')
    group = models.ForeignKey('Group', on_delete=models.CASCADE, related_name='student_history')
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True, help_text="Null means currently in the group")
    
    # Store rates at the time of entry, though they could change monthly
    kurs_narxi = models.PositiveIntegerField(default=0)
    oqituvchi_foiz = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "O‘quvchi guruh tarixi"
        verbose_name_plural = "O‘quvchilar guruh tarixi"
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.student.get_full_name()} in {self.group.nom} ({self.start_date} to {self.end_date or 'Present'})"


class FinancialMonth(models.Model):
    """Represents a financial period that can be locked."""
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    is_closed = models.BooleanField(default=False, verbose_name="Yopilganmi?")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('center', 'year', 'month')
        verbose_name = "Moliyaviy oy"
        verbose_name_plural = "Moliyaviy oylar"

    def __str__(self):
        return f"{self.year}-{self.month:02d} ({self.center.name})"


class MonthlyFinanceSnapshot(models.Model):
    """Permanent storage for center-level financial data of a closed month."""
    financial_month = models.OneToOneField(FinancialMonth, on_delete=models.CASCADE, related_name='snapshot')
    total_income = models.BigIntegerField(default=0)
    total_expense = models.BigIntegerField(default=0)
    center_profit = models.BigIntegerField(default=0)
    student_count = models.IntegerField(default=0)
    attendance_rate = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Oylik moliya snapshoti"
        verbose_name_plural = "Oylik moliya snapshotlari"


class TeacherSalarySnapshot(models.Model):
    """Permanent storage for teacher salary data of a closed month."""
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salary_snapshots')
    financial_month = models.ForeignKey(FinancialMonth, on_delete=models.CASCADE, related_name='teacher_snapshots')
    salary = models.BigIntegerField(default=0)
    attendance_count = models.IntegerField(default=0)
    details = models.JSONField(default=dict, help_text="Breakdown by group and student")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'financial_month')
        verbose_name = "O‘qituvchi oylik snapshoti"
        verbose_name_plural = "O‘qituvchilar oylik snapshotlari"


def exam_upload_path(instance, filename):
    return f"education/exam_files/{timezone.localdate().year}/{timezone.localdate().month:02d}/{filename}"


class CenterExamSetting(models.Model):
    center = models.OneToOneField(
        "accounts.Center",
        on_delete=models.CASCADE,
        related_name="exam_settings",
    )
    exam_system_enabled = models.BooleanField(default=False, verbose_name="Imtihon tizimi yoqilganmi")
    exam_every_n_lessons = models.PositiveSmallIntegerField(
        default=12,
        validators=[MinValueValidator(1)],
        verbose_name="Har N-darsda imtihon",
    )
    passing_score_percent = models.PositiveSmallIntegerField(
        default=60,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
        verbose_name="O‘tish foizi (%)",
    )
    failed_student_threshold = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        verbose_name="Past natija threshold",
    )
    exam_file_upload_enabled = models.BooleanField(default=True, verbose_name="Imtihon fayl yuklash yoqilganmi")
    exam_result_required = models.BooleanField(default=False, verbose_name="Imtihon natijasi majburiymi")
    optional_task_upload_prompt_enabled = models.BooleanField(
        default=True,
        verbose_name="Ixtiyoriy topshiriq so‘rovi yoqilganmi",
    )
    minimum_certificate_attendance_percent = models.PositiveSmallIntegerField(
        default=70,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
        verbose_name="Sertifikat uchun min davomat (%)",
    )
    minimum_certificate_average_percent = models.PositiveSmallIntegerField(
        default=60,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
        verbose_name="Sertifikat uchun min o‘rtacha foiz (%)",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_exam_settings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Markaz imtihon sozlamasi"
        verbose_name_plural = "Markaz imtihon sozlamalari"

    def __str__(self):
        return f"{self.center.name} imtihon sozlamalari"


class ExamReminderLog(models.Model):
    ACTION_YES = "yes"
    ACTION_NO = "no"
    ACTION_LATER = "later"
    ACTION_CHOICES = (
        (ACTION_YES, "Ha"),
        (ACTION_NO, "Yo‘q"),
        (ACTION_LATER, "Keyinroq"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="exam_reminder_logs")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="exam_reminder_logs")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_reminder_actions",
    )
    attendance_date = models.DateField(default=timezone.localdate)
    lesson_number_reference = models.PositiveIntegerField(default=0)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    note = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Imtihon eslatma actioni"
        verbose_name_plural = "Imtihon eslatma actionlari"

    def __str__(self):
        return f"{self.group.nom} / {self.lesson_number_reference} / {self.action}"


class ExamSession(models.Model):
    DECISION_YES = "yes"
    DECISION_NO = "no"
    DECISION_LATER = "later"
    DECISION_CHOICES = (
        (DECISION_YES, "Ha"),
        (DECISION_NO, "Yo‘q"),
        (DECISION_LATER, "Keyinroq"),
    )

    STATUS_DRAFT = "draft"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Qoralama"),
        (STATUS_COMPLETED, "Yakunlangan"),
        (STATUS_CANCELLED, "Bekor qilingan"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="exam_sessions")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="exam_sessions")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_exam_sessions",
        limit_choices_to={"role": "teacher"},
    )
    attendance_date = models.DateField(default=timezone.localdate)
    exam_date = models.DateField(default=timezone.localdate)
    lesson_number_reference = models.PositiveIntegerField(default=0)
    exam_sequence_number = models.PositiveIntegerField(default=1)
    teacher_decision = models.CharField(
        max_length=10,
        choices=DECISION_CHOICES,
        default=DECISION_LATER,
    )
    decision_note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exam_sessions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_exam_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-exam_date", "-id")
        indexes = [
            models.Index(fields=["center", "group", "exam_date"]),
            models.Index(fields=["group", "lesson_number_reference"]),
        ]

    def __str__(self):
        return f"{self.group.nom} - imtihon #{self.exam_sequence_number}"


class ExamResult(models.Model):
    FOLLOW_UP_NOT_REQUIRED = "not_required"
    FOLLOW_UP_PENDING = "pending"
    FOLLOW_UP_PARENT_CONTACTED = "parent_contacted"
    FOLLOW_UP_SUPPORT_REQUIRED = "support_required"
    FOLLOW_UP_REVIEWED = "reviewed"
    FOLLOW_UP_CHOICES = (
        (FOLLOW_UP_NOT_REQUIRED, "Talab etilmaydi"),
        (FOLLOW_UP_PENDING, "Nazorat kerak"),
        (FOLLOW_UP_PARENT_CONTACTED, "Ota-ona bilan bog‘lanilgan"),
        (FOLLOW_UP_SUPPORT_REQUIRED, "Qo‘shimcha yordam kerak"),
        (FOLLOW_UP_REVIEWED, "Ko‘rib chiqilgan"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="exam_results")
    session = models.ForeignKey("education.ExamSession", on_delete=models.CASCADE, related_name="results")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="exam_results")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_results",
        limit_choices_to={"role": "student"},
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_exam_results",
        limit_choices_to={"role": "teacher"},
    )

    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    teacher_comment = models.TextField(blank=True, default="")
    assignment_description = models.TextField(blank=True, default="")
    exam_date = models.DateField(default=timezone.localdate)
    lesson_number_reference = models.PositiveIntegerField(default=0)
    absent_in_exam = models.BooleanField(default=False)
    retake_recommended = models.BooleanField(default=False)
    fail_reason = models.CharField(max_length=255, blank=True, default="")
    follow_up_status = models.CharField(
        max_length=32,
        choices=FOLLOW_UP_CHOICES,
        default=FOLLOW_UP_NOT_REQUIRED,
    )
    follow_up_note = models.TextField(blank=True, default="")
    follow_up_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_result_followups",
    )
    follow_up_updated_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exam_results",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_exam_results",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-exam_date", "-id")
        unique_together = (("session", "student"),)
        indexes = [
            models.Index(fields=["center", "group", "exam_date"]),
            models.Index(fields=["student", "exam_date"]),
            models.Index(fields=["passed", "percent"]),
            models.Index(fields=["follow_up_status", "exam_date"]),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} / {self.group.nom} / {self.percent or 0}%"


class ExamResultFile(models.Model):
    FILE_WORK = "work"
    FILE_TASK = "task"
    FILE_OTHER = "other"
    FILE_KIND_CHOICES = (
        (FILE_WORK, "O‘quvchi ishi"),
        (FILE_TASK, "Topshiriq fayli"),
        (FILE_OTHER, "Boshqa"),
    )

    result = models.ForeignKey("education.ExamResult", on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=exam_upload_path)
    file_kind = models.CharField(max_length=20, choices=FILE_KIND_CHOICES, default=FILE_WORK)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_exam_files",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Imtihon fayli"
        verbose_name_plural = "Imtihon fayllari"

    def __str__(self):
        return f"{self.result_id} - {self.file_kind}"


class ExamSessionTaskFile(models.Model):
    """
    Sessiya darajasidagi (hamma o'quvchi uchun umumiy) task fayllar.
    """
    session = models.ForeignKey("education.ExamSession", on_delete=models.CASCADE, related_name="task_files")
    file = models.FileField(upload_to=exam_upload_path)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_exam_session_task_files",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Imtihon sessiya task fayli"
        verbose_name_plural = "Imtihon sessiya task fayllari"

    def __str__(self):
        return f"Sessiya #{self.session_id} task fayli"


class EducationAuditLog(models.Model):
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="education_audit_logs")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="education_audit_actions",
    )
    action_type = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100, blank=True, default="")
    entity_id = models.CharField(max_length=64, blank=True, default="")
    message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["center", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
        ]
        verbose_name = "Education audit log"
        verbose_name_plural = "Education audit logs"

    def __str__(self):
        return f"{self.action_type} ({self.entity_type}:{self.entity_id})"


class GroupInternalRankingSnapshot(models.Model):
    """
    Guruh ichki faollik reytingi uchun kundalik snapshot.
    Global chaqmoq reytingidan alohida saqlanadi.
    """
    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="group_ranking_snapshots")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="internal_ranking_snapshots")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="internal_group_rankings",
        limit_choices_to={"role": "student"},
    )
    snapshot_date = models.DateField(default=timezone.localdate)
    rank_position = models.PositiveIntegerField(default=0)

    attendance_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    activity_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    exam_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    homework_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    discipline_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    lightning_bonus_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_internal_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    explanation_text = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calculated_group_rankings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("snapshot_date", "rank_position", "id")
        unique_together = (("group", "student", "snapshot_date"),)
        indexes = [
            models.Index(fields=["group", "snapshot_date", "rank_position"]),
            models.Index(fields=["student", "snapshot_date"]),
        ]
        verbose_name = "Guruh ichki reyting snapshoti"
        verbose_name_plural = "Guruh ichki reyting snapshotlari"

    def __str__(self):
        return f"{self.group.nom} / {self.student.get_full_name()} / #{self.rank_position}"


class StudentAcademicSummary(models.Model):
    RECOMMENDATION_ELIGIBLE = "eligible"
    RECOMMENDATION_NEEDS_REVIEW = "needs_review"
    RECOMMENDATION_NOT_ELIGIBLE = "not_eligible"
    RECOMMENDATION_CHOICES = (
        (RECOMMENDATION_ELIGIBLE, "Mos"),
        (RECOMMENDATION_NEEDS_REVIEW, "Ko‘rib chiqish kerak"),
        (RECOMMENDATION_NOT_ELIGIBLE, "Mos emas"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="academic_summaries")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="academic_summaries")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="academic_summaries",
        limit_choices_to={"role": "student"},
    )

    exam_count = models.PositiveIntegerField(default=0)
    average_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    average_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pass_count = models.PositiveIntegerField(default=0)
    fail_count = models.PositiveIntegerField(default=0)
    pass_rate_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    attendance_total_lessons = models.PositiveIntegerField(default=0)
    attendance_present_lessons = models.PositiveIntegerField(default=0)
    attendance_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    internal_rank_position = models.PositiveIntegerField(null=True, blank=True)
    internal_rank_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    completion_recommendation = models.CharField(
        max_length=20,
        choices=RECOMMENDATION_CHOICES,
        default=RECOMMENDATION_NEEDS_REVIEW,
    )
    recommendation_reason = models.TextField(blank=True, default="")
    ranking_explanation = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calculated_academic_summaries",
    )
    calculated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("group", "student"),)
        ordering = ("group", "student")
        indexes = [
            models.Index(fields=["center", "completion_recommendation"]),
            models.Index(fields=["student", "group"]),
        ]
        verbose_name = "Akademik yakuniy xulosa"
        verbose_name_plural = "Akademik yakuniy xulosalar"

    def __str__(self):
        return f"{self.student.get_full_name()} / {self.group.nom} / {self.completion_recommendation}"


def certificate_template_upload_path(instance, filename):
    center_id = getattr(instance, "center_id", "unknown")
    return f"education/certificate_templates/{center_id}/{timezone.localdate().year}/{filename}"


def certificate_pdf_upload_path(instance, filename):
    center_id = getattr(instance, "center_id", "unknown")
    return f"education/certificates/{center_id}/{timezone.localdate().year}/{filename}"


class CertificateTemplate(models.Model):
    TYPE_CERTIFICATE = "certificate"
    TYPE_DIPLOMA = "diploma"
    TYPE_CHOICES = (
        (TYPE_CERTIFICATE, "Sertifikat"),
        (TYPE_DIPLOMA, "Diplom"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="certificate_templates")
    name = models.CharField(max_length=150)
    template_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_CERTIFICATE)
    template_file = models.FileField(upload_to=certificate_template_upload_path, db_column="file")
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True, default="")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_certificate_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")
        indexes = [
            models.Index(fields=["center", "template_type", "is_active"]),
        ]
        verbose_name = "Sertifikat shabloni"
        verbose_name_plural = "Sertifikat shablonlari"

    def __str__(self):
        return f"{self.center.name} / {self.template_type} / {self.name}"


class CertificateRecord(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Qoralama"),
        (STATUS_ISSUED, "Berilgan"),
        (STATUS_REVOKED, "Bekor qilingan"),
    )

    TYPE_CERTIFICATE = "certificate"
    TYPE_DIPLOMA = "diploma"
    TYPE_CHOICES = (
        (TYPE_CERTIFICATE, "Sertifikat"),
        (TYPE_DIPLOMA, "Diplom"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="certificates")
    group = models.ForeignKey("education.Group", on_delete=models.CASCADE, related_name="certificates")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
        limit_choices_to={"role": "student"},
    )
    template = models.ForeignKey(
        "education.CertificateTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    summary = models.ForeignKey(
        "education.StudentAcademicSummary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    certificate_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_CERTIFICATE)
    certificate_number = models.CharField(max_length=64, unique=True)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    issue_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    recommendation_status = models.CharField(
        max_length=20,
        choices=StudentAcademicSummary.RECOMMENDATION_CHOICES,
        default=StudentAcademicSummary.RECOMMENDATION_NEEDS_REVIEW,
    )
    recommendation_reason = models.TextField(blank=True, default="")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_certificates",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_certificates",
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    pdf_file = models.FileField(upload_to=certificate_pdf_upload_path, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["center", "group", "status"]),
            models.Index(fields=["certificate_number"]),
            models.Index(fields=["student", "group"]),
        ]
        verbose_name = "Sertifikat yozuvi"
        verbose_name_plural = "Sertifikat yozuvlari"

    def __str__(self):
        return f"{self.certificate_number} / {self.student.get_full_name()}"


class CertificateVerificationLog(models.Model):
    certificate = models.ForeignKey("education.CertificateRecord", on_delete=models.CASCADE, related_name="verification_logs")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificate_verification_logs",
    )
    ip_address = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Sertifikat tekshiruv jurnali"
        verbose_name_plural = "Sertifikat tekshiruv jurnallari"

    def __str__(self):
        return f"verify {self.certificate.certificate_number} at {self.created_at}"


class GroupClosureWorkflow(models.Model):
    STATUS_OPEN = "open"
    STATUS_CONTINUE = "continue"
    STATUS_REMIND_LATER = "remind_later"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = (
        (STATUS_OPEN, "Ochiq"),
        (STATUS_CONTINUE, "Davom etadi"),
        (STATUS_REMIND_LATER, "Keyinroq eslatilsin"),
        (STATUS_CLOSED, "Yopilgan"),
    )

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, related_name="group_closure_workflows")
    group = models.OneToOneField("education.Group", on_delete=models.CASCADE, related_name="closure_workflow")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    decision_date = models.DateField(null=True, blank=True)
    reminder_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_group_workflows",
    )
    note = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")
        indexes = [
            models.Index(fields=["center", "status"]),
            models.Index(fields=["decision_date"]),
        ]
        verbose_name = "Guruh yopish jarayoni"
        verbose_name_plural = "Guruh yopish jarayonlari"

    def __str__(self):
        return f"{self.group.nom} / {self.status}"
