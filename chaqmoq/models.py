from django.db import models
from django.conf import settings
from education.models import Group
from django.utils import timezone
User = settings.AUTH_USER_MODEL

class Rule(models.Model):
    PLUS = 'plus'
    MINUS = 'minus'
    TUR_CHOICES = (
        (PLUS, '+ Chaqmoq'),
        (MINUS, '− Chaqmoq'),
    )
    nom = models.CharField(max_length=150)
    tur = models.CharField(max_length=10, choices=TUR_CHOICES)
    min_baho = models.PositiveSmallIntegerField(default=1)
    max_baho = models.PositiveSmallIntegerField(default=10)

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
    rule_tur = models.CharField(max_length=10, blank=True, default="")
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
    def student_balansi(student_id: int) -> int:
        from django.db.models import Sum
        s = Ledger.objects.filter(student_id=student_id).aggregate(Sum('ball'))['ball__sum']
        return s or 0