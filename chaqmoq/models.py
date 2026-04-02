from django.db import models
from django.conf import settings
from education.models import Group, Student
from django.utils import timezone
User = settings.AUTH_USER_MODEL

class Rule(models.Model):
    PLUS = 'plus'
    MINUS = 'minus'
    ATTENDANCE_PENALTY = 'attendance_penalty'
    ATTENDANCE_BONUS = 'attendance_bonus'
    PAYMENT_BONUS = 'payment_bonus'
    PAYMENT_DISCIPLINE = 'payment_discipline'
    TUR_CHOICES = (
        (PLUS, '+ Chaqmoq'),
        (MINUS, '− Chaqmoq'),
        (ATTENDANCE_PENALTY, 'Davomat jarimasi'),
        (ATTENDANCE_BONUS, 'Davomat bonusi'),
        (PAYMENT_BONUS, 'To‘lov bonusi'),
        (PAYMENT_DISCIPLINE, 'To‘lov intizomi'),
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

    # Payment Discipline fields (New)
    discipline_deadline_day = models.PositiveSmallIntegerField(default=10, verbose_name="Deadline sanasi (oyning sanasi)")
    discipline_bonus_score = models.SmallIntegerField(default=5, verbose_name="Deadline gacha to'lov bonusi")
    discipline_penalty_score = models.SmallIntegerField(default=-10, verbose_name="Dedline gacha to'lov qilmaganlarga jarima")
    discipline_active = models.BooleanField(default=False, verbose_name="Qoida faolmi?")


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
    
    # Qaysi oy/yil uchun qo'llanganligi (Audit/Duplicate protection)
    # Masalan: 2026-03-01
    related_month = models.DateField(null=True, blank=True, verbose_name="Tegishli oy")

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
        from chaqmoq.models import LightningHistory
        from django.db.models.functions import Coalesce
        from django.db.models import Sum
        from django.db.models import Q

        # Asosiy manba: Ledger (ham eski, ham yangi yozuvlar shu yerda bor).
        # student_id ba'zan User.id, ba'zan Student.id bo'lib kelishi mumkin.
        resolved_user_id = student_id
        if not Student.objects.filter(user_id=student_id).exists():
            resolved_user_id = (
                Student.objects.filter(id=student_id).values_list("user_id", flat=True).first()
                or student_id
            )

        ledger_qs = Ledger.objects.filter(student_id=resolved_user_id)
        if center:
            ledger_qs = ledger_qs.filter(
                Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True)
            )
        if ledger_qs.exists():
            total = ledger_qs.aggregate(total=Coalesce(Sum("ball"), 0))["total"]
            return int(total or 0)

        # Fallback: faqat history bor holatlar uchun.
        student_obj = Student.objects.filter(user_id=resolved_user_id).first()
        if not student_obj:
            student_obj = Student.objects.filter(id=student_id).first()
        if not student_obj:
            return 0

        history_qs = LightningHistory.objects.filter(student=student_obj)
        if center:
            history_qs = history_qs.filter(student__user__center=center)
        total = history_qs.aggregate(total=Coalesce(Sum("points"), 0))["total"]
        return int(total or 0)

class LightningHistory(models.Model):
    SOURCE_CHOICES = (
        ("attendance", "Davomat"),
        ("bonus", "Bonus"),
        ("penalty", "Jarima"),
        ("manual", "Boshqa"),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="lightning_history")
    points = models.IntegerField(default=0)
    reason = models.CharField(max_length=255)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default="manual")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Chaqmoq tarixi'
        verbose_name_plural = 'Chaqmoq tarixlari'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} — {self.points} ({self.source})"
