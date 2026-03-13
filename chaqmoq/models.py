from django.db import models
from django.conf import settings
from education.models import Group
from django.utils import timezone
User = settings.AUTH_USER_MODEL

class Rule(models.Model):
    PLUS = 'plus'
    MINUS = 'minus'
    ATTENDANCE_PENALTY = 'attendance_penalty'
    ATTENDANCE_BONUS = 'attendance_bonus'
    PAYMENT_BONUS = 'payment_bonus'
    TUR_CHOICES = (
        (PLUS, '+ Chaqmoq'),
        (MINUS, '− Chaqmoq'),
        (ATTENDANCE_PENALTY, 'Davomat jarimasi'),
        (ATTENDANCE_BONUS, 'Davomat bonusi'),
        (PAYMENT_BONUS, 'To‘lov bonusi'),
    )
    nom = models.CharField(max_length=150)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    tur = models.CharField(max_length=50, choices=TUR_CHOICES)
    min_baho = models.PositiveSmallIntegerField(default=1)
    max_baho = models.PositiveSmallIntegerField(default=10)

    # Roles permissions
    can_director = models.BooleanField(default=True, verbose_name="Director ishlata oladi")
    can_manager = models.BooleanField(default=True, verbose_name="Manager ishlata oladi")
    can_teacher = models.BooleanField(default=True, verbose_name="O'qituvchi ishlata oladi")

    # Attendance Penalty/Bonus fields
    absence_limit = models.PositiveSmallIntegerField(default=3, blank=True, null=True, verbose_name="Sababsiz qoldirish limiti")
    presence_limit = models.PositiveSmallIntegerField(default=12, blank=True, null=True, verbose_name="Darsga kelish limiti")
    
    PERIOD_CHOICES = (
        ('monthly', 'Oylik'),
    )
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='monthly', blank=True, null=True)
    lightning_penalty = models.SmallIntegerField(default=-5, blank=True, null=True, verbose_name="Ayiriladigan chaqmoq")
    lightning_bonus = models.SmallIntegerField(default=10, blank=True, null=True, verbose_name="Qo'shiladigan chaqmoq")

    # Payment Bonus fields
    payment_bonus_lightning = models.SmallIntegerField(default=5, blank=True, null=True, verbose_name="To'lov uchun bonus chaqmoq")


    class Meta:
        verbose_name = 'Chaqmoq qoida'
        verbose_name_plural = 'Chaqmoq qoidalari'

    def __str__(self):
        belgi = '+' if self.tur == self.PLUS else '-'
        return f"{self.nom} ({belgi}{self.min_baho}..{self.max_baho})"

class Ledger(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    beruvchi = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='chaqmoq_beruvchi')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)

    # ✅ Rule o‘chsa ham Ledger qoladi
    rule = models.ForeignKey(Rule, on_delete=models.SET_NULL, null=True, blank=True)

    # ✅ History uchun snapshot (qoida o‘chsa ham nomi qoladi)
    rule_nom = models.CharField(max_length=150, blank=True, default="")
    rule_tur = models.CharField(max_length=50, blank=True, default="")
    rule_min_baho = models.PositiveSmallIntegerField(null=True, blank=True)
    rule_max_baho = models.PositiveSmallIntegerField(null=True, blank=True)

    ball = models.SmallIntegerField()
    sana = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Chaqmoq yozuvi'
        verbose_name_plural = 'Chaqmoq yozuvlari'

    def __str__(self):
        rule_name = self.rule_nom or (self.rule.nom if self.rule else "Qoida o‘chirilgan")
        return f"{self.student} — {self.ball} — {rule_name}"

    def save(self, *args, **kwargs):
        # Snapshotni doim to‘ldirib qo‘yamiz (keyin rule o‘chsa ham history saqlanadi)
        if self.rule:
            self.rule_nom = self.rule.nom
            self.rule_tur = self.rule.tur
            self.rule_min_baho = self.rule.min_baho
            self.rule_max_baho = self.rule.max_baho
        super().save(*args, **kwargs)

    @staticmethod
    def student_balansi(student_id: int, center=None) -> int:
        from django.db.models import Sum, Q
        qs = Ledger.objects.filter(student_id=student_id)
        if center:
            qs = qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))
        s = qs.aggregate(Sum('ball'))['ball__sum']
        return s or 0