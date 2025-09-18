from django.db import models
from django.conf import settings
from accounts.models import Center

User = settings.AUTH_USER_MODEL

# education/models.py
class Group(models.Model):
    LANG = "lang"
    IT = "it"
    CATEGORY_CHOICES = (
        (LANG, "Tillar"),
        (IT, "IT"),
    )

    category   = models.CharField(max_length=8, choices=CATEGORY_CHOICES, default=LANG)
    center     = models.ForeignKey(Center, on_delete=models.CASCADE)
    nom        = models.CharField(max_length=150)
    izoh       = models.TextField(blank=True)
    oqituvchi  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   limit_choices_to={'role': 'teacher'})
    tuzilgan   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"

    def __str__(self):
        return self.nom
    



class Enrollment(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    kurs_narhi = models.PositiveIntegerField(default=0)
    jami_tolangan = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Guruhga qo‘shilish"
        verbose_name_plural = "Guruhga qo‘shilishlar"
        unique_together = ('group', 'student')

    def qoldiq(self):
        return max(self.kurs_narhi - self.jami_tolangan, 0)
    

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
    group   = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    teacher = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='taken_attendances', limit_choices_to={'role': 'teacher'}
    )
    date    = models.DateField(auto_now_add=True)
    present = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomat"
        unique_together = ('group', 'student', 'date')

    def __str__(self):
        return f"{self.date} • {self.group} • {self.student} • {'✓' if self.present else '✗'}"