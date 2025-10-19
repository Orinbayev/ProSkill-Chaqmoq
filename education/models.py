from django.db import models
from django.conf import settings
from accounts.models import Center
from django.core.validators import MinValueValidator
from django.utils import timezone
User = settings.AUTH_USER_MODEL
from django.core.validators import MinValueValidator, MaxValueValidator

# education/models.py
class Group(models.Model):
    LANG = "lang"
    IT = "it"
    CATEGORY_CHOICES = (
        (LANG, "Tillar"),
        (IT, "IT"),
    )

    category = models.CharField(max_length=8, choices=CATEGORY_CHOICES, default=LANG)
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

    kurs_narxi = models.PositiveIntegerField(default=500000, help_text="Bir oylik to‘lov (so‘mda)")
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
            return (self.kurs_narxi * self.oqituvchi_foiz / 100) / self.oy_dars_soni
        else:
            # Default qiymat (agar admin unutgan bo‘lsa)
            return 0


    
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
    
    
class Payment(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='payments')
    summa = models.PositiveIntegerField()
    sana = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "To‘lov"
        verbose_name_plural = "To‘lovlar"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total = sum(p.summa for p in self.enrollment.payments.all())
        Enrollment.objects.filter(id=self.enrollment_id).update(jami_tolangan=total)



# ====== YANGI: Davomat ======

class Attendance(models.Model):
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
        default=timezone.localdate,  # Django versiyasi – to‘g‘ri
        verbose_name="Sana"
    )
    present = models.BooleanField(
        default=False,
        verbose_name="Kelganmi"
    )

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"
        unique_together = ('group', 'student', 'date')
        ordering = ['-date']

    def __str__(self):
        belgi = "✅" if self.present else "❌"
        return f"{self.date} | {self.group} | {self.student} | {belgi}"

    def save(self, *args, **kwargs):
        # Agar sana kiritilmagan bo‘lsa, bugungi sanani qo‘yadi
        if not self.date:
            self.date = timezone.localdate()

        # Har doim kechasi 00:00 gacha shu sana sifatida qoladi
        now = timezone.localtime()
        if now.hour == 0 and now.minute < 5:
            # 00:00 dan 00:05 gacha bo‘lsa – yangi kun sifatida
            self.date = timezone.localdate()

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


