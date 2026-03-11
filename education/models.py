from django.db import models
from django.conf import settings
from accounts.models import Center
from django.core.validators import MinValueValidator
from django.utils import timezone
User = settings.AUTH_USER_MODEL
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum
from django.db.models.signals import pre_save
from django.dispatch import receiver
from decimal import Decimal
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
    
    is_archived = models.BooleanField(default=False, verbose_name="Arxivlangan")

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"

    def __str__(self):
        return self.nom

    def dars_boshiga_tolov(self) -> float:
        if self.kurs_narxi > 0 and self.oqituvchi_foiz > 0 and self.oy_dars_soni > 0:
            return round((self.kurs_narxi * self.oqituvchi_foiz / 100) / self.oy_dars_soni, 2)
        return 0.0


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

    def __str__(self):
        ism = getattr(self.student, "ism", "")
        familya = getattr(self.student, "familya", "")
        return f"{ism} {familya} → {self.group.nom}"

    @property
    def oqituvchi_daromadi(self) -> int:
        """
        Bu - 1 oy uchun o‘qituvchining full (100% dars) daromadi.
        Davomatga qarab kamayishi/ko‘payishi boshqa metodda hisoblanadi.
        """
        return round((self.kurs_narhi or 0) * (self.oqituvchi_foiz or 0) / 100)

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
                from chaqmoq.services import check_payment_bonus
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
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    attendance = models.OneToOneField(Attendance, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(default=0)
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

    class Meta:
        ordering = ("tuition_month__month", "id")

    def __str__(self):
        return f"pay#{self.payment_id} -> {self.tuition_month.month}: {self.amount}"
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

