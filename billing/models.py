# billing/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator

from accounts.models import Center


class SubscriptionPlan(models.Model):
    """
    Tarif konfiguratsiyasi:
    - oy narxi (UZS)
    - limitlar
    """
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=50)
    monthly_price = models.PositiveIntegerField(default=0)

    max_users = models.PositiveIntegerField(default=50)
    max_groups = models.PositiveIntegerField(default=30)
    max_students = models.PositiveIntegerField(default=100)

    is_popular = models.BooleanField(default=False)
    discount_percent = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    caption = models.TextField(blank=True, default="", verbose_name="Qo'shimcha ma'lumot")  # ✅ Yangi field
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("monthly_price",)

    def __str__(self):
        return f"{self.title} ({self.code})"


def default_trial_expires():
    # trial default 7 kun: migratsiyada prompt chiqmasin
    return timezone.now() + timezone.timedelta(days=7)


class CenterSubscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "ACTIVE"
        BLOCKED = "BLOCKED", "BLOCKED"

    center = models.OneToOneField(Center, on_delete=models.CASCADE, related_name="subscription")

    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_trial_expires)

    manual_block = models.BooleanField(default=False)  # admin xohlasa bloklaydi

    updated_at = models.DateTimeField(auto_now=True)

    GRACE_PERIOD_HOURS = 72

    @property
    def hard_expires_at(self):
        return self.expires_at + timezone.timedelta(hours=self.GRACE_PERIOD_HOURS)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_hard_expired(self) -> bool:
        return timezone.now() >= self.hard_expires_at

    def is_blocked(self) -> bool:
        return self.manual_block or self.is_hard_expired() or self.status == self.Status.BLOCKED

    def in_grace_period(self) -> bool:
        # Expired but not yet blocked (Grace period)
        return self.is_expired() and not self.is_hard_expired() and not self.manual_block and self.status != self.Status.BLOCKED

    def is_over_student_limit(self) -> bool:
        """
        Check if center has exceeded student limit
        """
        from accounts.models import User
        current_students = User.objects.filter(
            center=self.center,
            role='student',
            is_archived=False
        ).count()
        return current_students > self.plan.max_students

    def days_left(self) -> int:
        """Returns days until expiry. Negative if already expired."""
        delta = self.expires_at.date() - timezone.now().date()
        return delta.days

    def __str__(self):
        return f"{self.center} → {self.plan.code} (until {self.expires_at.date()})"


class PromoCode(models.Model):
    code = models.CharField(max_length=30, unique=True)
    percent_off = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    active = models.BooleanField(default=True)

    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    once_per_center = models.BooleanField(default=True)  # ✅ Yangi: Har bir markaz faqat 1 marta ishlata olsin

    # qaysi planlarga ishlasin (bo'sh bo'lsa hammasiga)
    plans = models.ManyToManyField(SubscriptionPlan, blank=True, related_name="promocodes")

    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid_now(self) -> bool:
        now = timezone.now()
        if not self.active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def __str__(self):
        return f"{self.code} (-{self.percent_off}%)"


class SubscriptionOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        PAID = "PAID", "PAID"
        CANCELED = "CANCELED", "CANCELED"

    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name="orders")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)

    duration_months = models.PositiveIntegerField(default=1)
    base_price = models.PositiveIntegerField(default=0)       # hisoblangan
    discount_percent = models.PositiveIntegerField(default=0) # promo
    final_price = models.PositiveIntegerField(default=0)

    promo = models.ForeignKey(PromoCode, null=True, blank=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"#{self.id} {self.center.slug} {self.plan.code} x{self.duration_months} ({self.status})"
