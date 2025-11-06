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

# education/models.py
from django.db import models
from django.conf import settings


class Group(models.Model):
    LANG = "lang"
    IT = "it"
    CATEGORY_CHOICES = (
        (LANG, "Tillar"),
        (IT, "IT"),
    )

    # Eski tizimdagi tanlov
    category = models.CharField(max_length=8, choices=CATEGORY_CHOICES, default=LANG)

    # Yangi tizim
    category_obj = models.ForeignKey(
        "education.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="groups",
        verbose_name="Bo‘lim (Category modeli orqali)"
    )

    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE)
    nom = models.CharField(max_length=150)
    izoh = models.TextField(blank=True)
    oqituvchi = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'role': 'teacher'}
    )

    tuzilgan = models.DateTimeField(auto_now_add=True)
    kurs_narxi = models.PositiveIntegerField(default=50000000, help_text="Bir oylik to‘lov (so‘mda)")
    oqituvchi_foiz = models.PositiveIntegerField(default=40, help_text="O‘qituvchi foizi (%)")
    oy_dars_soni = models.PositiveIntegerField(default=12, help_text="Bir oyda nechta dars bo‘ladi")

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"

    def __str__(self):
        return self.nom

    def dars_boshiga_tolov(self):
        """Har dars uchun to‘lovni xavfsiz hisoblash"""
        if self.kurs_narxi > 0 and self.oqituvchi_foiz > 0 and self.oy_dars_soni > 0:
            return round((self.kurs_narxi * self.oqituvchi_foiz / 100) / self.oy_dars_soni, 2)
        return 0


class Oquvchi(models.Model):
    """Guruhdagi o‘quvchi"""
    ism = models.CharField(max_length=100)
    guruh = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='oquvchilar')
    tolov = models.PositiveIntegerField(default=0, help_text="O‘quvchining oylik to‘lovi (so‘mda)")

    def __str__(self):
        return f"{self.ism} ({self.guruh.nom})"


class Dars(models.Model):
    """Har bir o‘qituvchining darslari"""
    guruh = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='darslar')
    oqituvchi = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sana = models.DateField(auto_now_add=True)
    davom_etilgan = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.guruh.nom} - {self.sana}"


class OylikHisobot(models.Model):
    """Avtomatik oylik hisobot jadvali"""
    oqituvchi = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    oy = models.CharField(max_length=15)
    yil = models.IntegerField()
    jami_darslar = models.PositiveIntegerField(default=0)
    jami_daromad = models.PositiveIntegerField(default=0)
    markaz_foydasi = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.oqituvchi} — {self.oy} {self.yil}"


    
class GroupStudent(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='students')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Guruhdagi o‘quvchi"
        verbose_name_plural = "Guruhdagi o‘quvchilar"

    def __str__(self):
        return f"{self.student.get_full_name()} → {self.group.nom}"



class Enrollment(models.Model):
    group = models.ForeignKey(
        'education.Group',
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name="Guruh"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},
        verbose_name="O‘quvchi"
    )
    kurs_narhi = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Kurs narxi (so‘mda)")
    oqituvchi_foiz = models.PositiveIntegerField(default=40, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name="O‘qituvchi ulushi (%)")
    jami_tolangan = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Jami to‘langan (so‘mda)")

    class Meta:
        unique_together = ('group', 'student')
        verbose_name = "Guruhga qo‘shilish"
        verbose_name_plural = "Guruhga qo‘shilishlar"
        ordering = ['group', 'student']

    def __str__(self):
        ism = getattr(self.student, 'ism', 'Noma’lum')
        familya = getattr(self.student, 'familya', '')
        return f"{ism} {familya} → {self.group.nom}"

    @property
    def oqituvchi_daromadi(self):
        """O‘qituvchiga to‘liq kurs uchun tushadigan summa."""
        return round(self.kurs_narhi * self.oqituvchi_foiz / 100)

    @property
    def attended_count(self):
        return self.group.attendances.filter(student=self.student, present=True).count()

    def get_monthly_payment(self):
        """Joriy oy uchun jami to‘langan summani qaytaradi"""
        now = timezone.now()
        total = Payment.objects.filter(
            student=self.student,
            group=self.group,
            month=now.month,
            year=now.year
        ).aggregate(total=Sum('summa'))['total'] or 0
        return total

    @property
    def qoldiq_oylik(self):
        """Joriy oy uchun qolgan to‘lov"""
        return max(self.kurs_narhi - self.get_monthly_payment(), 0)

    @property
    def is_full_this_month(self):
        """Joriy oy uchun to‘liq to‘langanmi?"""
        return self.get_monthly_payment() >= self.kurs_narhi

    def real_oqituvchi_daromadi(self):
        """
        O‘qituvchining haqiqiy daromadini hisoblaydi:
        faqat darsga kelgan o‘quvchilar asosida.
        """
        total_lessons = self.group.oy_dars_soni or 0
        attended = self.group.attendances.filter(student=self.student, present=True).count()

        if total_lessons == 0:
            return 0

        foiz = attended / total_lessons
        return round(self.oqituvchi_daromadi * foiz)
    
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.db.models import Sum
    
class Payment(models.Model):
    PAYMENT_TYPES = (
        ('cash', 'Naqd'),
        ('card', 'Karta'),
        ('mixed', 'Aralash'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},
        verbose_name="O‘quvchi"
    )
    group = models.ForeignKey(
        'education.Group',
        on_delete=models.CASCADE,
        related_name='group_payments',
        verbose_name="Guruh"
    )
    enrollment = models.ForeignKey(
        'education.Enrollment',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Yozilish",
        null=True,
        blank=True
    )

    # biz hozir cash va cardni alohida saqlaymiz; summa umumiy uchun ham qoladi
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES, default='cash')
    cash_amount = models.PositiveIntegerField(default=0, verbose_name="Naqd summasi (so'mda)")
    card_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Karta summasi (valyutada yoki so'mda)")
    card_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1, verbose_name="Kurs (agar karta valyutada bo'lsa)")
    card_currency = models.CharField(max_length=10, default='UZS', verbose_name="Karta valyutasi")
    note = models.TextField(blank=True, null=True, verbose_name="Izoh")
    is_full_paid = models.BooleanField(default=False, verbose_name="To'liq to'landi (belgi)")

    # legacy: summa (saqlanadigan umumiy so'm)
    summa = models.PositiveIntegerField(verbose_name="To‘lov summasi (so‘mda)", default=0) 
    total = models.FloatField(default=0)  # ✅ Qo‘shildi
 
    sana = models.DateField(auto_now_add=True, verbose_name="To‘lov sanasi")
    vaqt = models.TimeField(default=timezone.now)  # 🕒 Qo‘shildi
    month = models.PositiveSmallIntegerField(verbose_name="Oy", default=timezone.now().month)
    year = models.PositiveSmallIntegerField(verbose_name="Yil", default=timezone.now().year)

    class Meta:
        verbose_name = "To‘lov"
        verbose_name_plural = "To‘lovlar"
        ordering = ['-sana']

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.summa:,} so‘m ({self.sana})"

    @property
    def card_amount_som(self):
            # Agar card_rate = 1 bo‘lsa ham Decimal bilan hisobla, so‘ng int
            return int((self.card_amount or Decimal('0')) * (self.card_rate or Decimal('1')))

    def save(self, *args, **kwargs):
        # 1) summa (UZS) ni hisobla
        self.summa = int(self.cash_amount or 0) + self.card_amount_som  # ❌ () yo‘q endi
        self.total = float(self.summa)

        # 2) Enrollment borligini kafolatla
        if not self.enrollment_id and self.student_id and self.group_id:
            enroll = Enrollment.objects.filter(
                student_id=self.student_id,
                group_id=self.group_id
            ).first()
            if enroll:
                self.enrollment = enroll

        super().save(*args, **kwargs)

        # 3) ENROLLMENT jami to‘lovni yangila (faqat summa yig‘indisi)
        if self.enrollment_id:
            agg = Payment.objects.filter(enrollment_id=self.enrollment_id).aggregate(s=Sum('summa'))
            Enrollment.objects.filter(pk=self.enrollment_id).update(jami_tolangan=agg['s'] or 0)




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

    date = models.DateField(
        default=timezone.localdate,
        verbose_name="Sana"
    )
    present = models.BooleanField(
        default=False,
        verbose_name="Kelganmi"
    )

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"
        unique_together = ('group', 'student', 'date')  # 🔥 Har bir guruh uchun alohida davomat
        ordering = ['-date']

    def __str__(self):
        belgi = "✅" if self.present else "❌"
        return f"{self.date} | {self.group.nom} | {self.student.get_full_name()} | {belgi}"

    def save(self, *args, **kwargs):
        """Davomat saqlanganda avtomatik o‘qituvchi va sana belgilanadi."""
        if not self.date:
            self.date = timezone.localdate()

        if not self.teacher and hasattr(self.group, 'oqituvchi'):
            self.teacher = self.group.oqituvchi

        super().save(*args, **kwargs)



class AttendanceHistory(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    date = models.DateField()
    is_present = models.BooleanField(default=False)
    plus_coin = models.IntegerField(default=0)
    minus_coin = models.IntegerField(default=0)

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.date} — {'✅' if self.is_present else '❌'}"


class Category(models.Model):
    """Guruhlar kategoriyasi (masalan: Tillar, IT, Dizayn...)"""
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=10, blank=True, null=True, help_text="Emoji yoki belgi masalan 💻 📘 🎨")
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True, verbose_name="Bo‘lim rasmi")

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    center = models.ForeignKey(Center, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.full_name


class DailyLightningSetting(models.Model):
    date = models.DateField(unique=True)
    max_lightning = models.PositiveIntegerField(default=0)  # 0 → cheklanmagan
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Kunlik chaqmoq limiti"
        verbose_name_plural = "Kunlik chaqmoq limitlari"

    def __str__(self):
        return f"{self.date} — {self.max_lightning or 'Cheklanmagan'}"

class TeacherIncome(models.Model):
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

