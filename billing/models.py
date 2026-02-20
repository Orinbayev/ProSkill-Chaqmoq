# billing/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator

from accounts.models import Center


class PlanFeature(models.Model):
    """
    Alohida feature/huquq elementi.
    Har bir plan ushbu featurelardan ManyToMany orqali tanlaydi.
    """
    class Category(models.TextChoices):
        CORE      = "core",      "Asosiy"
        STUDENTS  = "students",  "O'quvchilar"
        GROUPS    = "groups",    "Guruhlar"
        PAYMENTS  = "payments",  "Moliya / To'lov"
        DEBTORS   = "debtors",   "Qarzdorlar"
        SCHEDULE  = "schedule",  "Jadval / Davomat"
        COURSES   = "courses",   "Kurslar / Darslar"
        STAFF     = "staff",     "Xodimlar / Rollar"
        BROADCAST = "broadcast", "SMS / Reklama"
        REPORTS   = "reports",   "Hisobot / Export"
        CRM       = "crm",       "CRM / Analytics"
        SETTINGS  = "settings",  "Sozlamalar"

    code        = models.CharField(max_length=50, unique=True, verbose_name="Kod (unique)")
    name        = models.CharField(max_length=100, verbose_name="Nomi")
    description = models.CharField(max_length=255, blank=True, default="", verbose_name="Qisqa izoh")
    category    = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.CORE,
        verbose_name="Kategoriya"
    )
    is_core     = models.BooleanField(default=False, verbose_name="Asosiy feature?")
    order       = models.PositiveSmallIntegerField(default=0, verbose_name="Tartib")

    class Meta:
        ordering  = ("category", "order", "name")
        verbose_name = "Plan Feature"
        verbose_name_plural = "Plan Features"

    def __str__(self):
        return f"[{self.category}] {self.name} ({self.code})"


class SubscriptionPlan(models.Model):
    """
    Tarif konfiguratsiyasi:
    - oy narxi (UZS)
    - limitlar
    """
    # Tier: 1=Free, 10=Standard, 20=Pro, etc. Used for hierarchy.
    tier = models.PositiveSmallIntegerField(default=1, verbose_name="Daraja (Tier)")
    
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=50)
    monthly_price = models.PositiveIntegerField(default=0)

    max_users = models.PositiveIntegerField(default=50)
    max_groups = models.PositiveIntegerField(default=30)
    max_students = models.PositiveIntegerField(default=100)

    is_popular = models.BooleanField(default=False)
    discount_percent = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    caption = models.TextField(blank=True, default="", verbose_name="Qo'shimcha ma'lumot")
    features = models.JSONField(blank=True, default=dict, verbose_name="Ruxsatlar (modullar)")

    # ✅ Professional M2M Features
    plan_features = models.ManyToManyField(
        PlanFeature,
        blank=True,
        related_name="plans",
        verbose_name="Ruxsatlar (M2M)"
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("tier", "monthly_price",) # Order by Tier first

    def __str__(self):
        return f"[{self.tier}] {self.title} ({self.code})"


def default_trial_expires():
    # trial default 7 kun
    return timezone.now() + timezone.timedelta(days=7)


class CenterSubscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "ACTIVE"
        PAUSED = "PAUSED", "PAUSED"    # ⏸ Frozen state
        EXPIRED = "EXPIRED", "EXPIRED" # ⌛ Finished
        BLOCKED = "BLOCKED", "BLOCKED" # 🚫 Admin blocked

    # ⚠️ Changed from OneToOne to ForeignKey to support Stacking
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name="subscriptions")

    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_trial_expires)
    
    # ⏯ Pause Logic
    paused_at = models.DateTimeField(null=True, blank=True)
    remaining_seconds = models.PositiveIntegerField(default=0, help_text="Pauza qilinganda qolgan vaqt (sekund)")

    manual_block = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    GRACE_PERIOD_HOURS = 72

    class Meta:
        ordering = ("-plan__tier", "-expires_at") # Highest tier first, then latest expiry
        constraints = [
            models.UniqueConstraint(
                fields=['center'], 
                condition=models.Q(status='ACTIVE'), 
                name='unique_active_center_sub'
            )
        ]

    @property
    def hard_expires_at(self):
        return self.expires_at + timezone.timedelta(hours=self.GRACE_PERIOD_HOURS)

    def is_expired(self) -> bool:
        if self.status == self.Status.PAUSED:
            return False # Paused never expires until resumed
        return timezone.now() >= self.expires_at

    def is_hard_expired(self) -> bool:
        if self.status == self.Status.PAUSED:
            return False
        return timezone.now() >= self.hard_expires_at

    def is_blocked(self) -> bool:
        return self.manual_block or (self.is_hard_expired() and self.status != self.Status.PAUSED) or self.status == self.Status.BLOCKED

    def in_grace_period(self) -> bool:
        if self.status == self.Status.PAUSED: return False
        return self.is_expired() and not self.is_hard_expired() and not self.manual_block and self.status != self.Status.BLOCKED

    def is_over_student_limit(self) -> bool:
        from accounts.models import User
        current_students = User.objects.filter(
            center=self.center,
            role='student',
            is_archived=False
        ).count()
        return current_students > self.plan.max_students

    def days_left(self) -> int:
        if self.status == self.Status.PAUSED:
            return int(self.remaining_seconds / 86400)
        delta = self.expires_at.date() - timezone.now().date()
        return delta.days

    def __str__(self):
        return f"{self.center} → {self.plan.code} [{self.status}]"


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
