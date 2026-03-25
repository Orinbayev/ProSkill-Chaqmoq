from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import math


from django.utils.text import slugify
from core.soft_delete import SoftDeleteMixin

class Center(SoftDeleteMixin, models.Model):
    class Plan(models.TextChoices):
        FREE = "FREE", "FREE"
        STANDARD = "STANDARD", "STANDARD"
        PREMIUM = "PREMIUM", "PREMIUM"
        PRO = "PRO", "PRO"

    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="") 
    db_name = models.CharField(max_length=128, blank=True, null=True, help_text="Имя отдельной базы данных центра (PostgreSQL)")
    db_user = models.CharField(max_length=128, blank=True, null=True, help_text="Пользователь БД центра")
    db_password = models.CharField(max_length=128, blank=True, null=True, help_text="Пароль БД центра (TODO: хранить безопасно, использовать env или vault)")
    db_host = models.CharField(max_length=128, blank=True, null=True, help_text="Хост БД центра")
    db_port = models.CharField(max_length=16, blank=True, null=True, help_text="Порт БД центра")

    slug = models.SlugField(unique=True) 
    # active field removed in favor of status
    created_at = models.DateTimeField(auto_now_add=True)

    plan = models.CharField(max_length=50, default="FREE")

    # Subscription Properties to handle Stack Logic
    from django.utils.functional import cached_property

    @cached_property
    def subscription(self):
        """
        Backward compatibility: Returns the currently ACTIVE or PAUSED (best candidate) subscription.
        Used for existing code that expects 'center.subscription'.
        Efficient even when prefetched.
        """
        subs = list(self.subscriptions.all())
        if not subs:
            return None
            
        # 1. Look for ACTIVE
        active_subs = [s for s in subs if s.status == "ACTIVE"]
        if active_subs:
            active_subs.sort(key=lambda s: (s.plan.tier, s.expires_at), reverse=True)
            return active_subs[0]
        
        # 2. Look for PAUSED
        paused_subs = [s for s in subs if s.status == "PAUSED"]
        if paused_subs:
            paused_subs.sort(key=lambda s: s.plan.tier, reverse=True)
            return paused_subs[0]

        # 3. Fallback to the most recent one
        return subs[0] if subs else None

    @cached_property
    def active_subscription(self):
        """
        Returns the real active subscription or None.
        Efficient even when prefetched.
        """
        subs = list(self.subscriptions.all())
        active_subs = [s for s in subs if s.status == "ACTIVE"]
        if not active_subs:
            return None
        # Sort by tier desc, expires_at desc
        active_subs.sort(key=lambda s: (s.plan.tier, s.expires_at), reverse=True)
        return active_subs[0]

    max_users = models.PositiveIntegerField(default=50)

    max_users = models.PositiveIntegerField(default=50)
    max_groups = models.PositiveIntegerField(default=30)
    max_students = models.PositiveIntegerField(default=100)
    capacity_limit = models.IntegerField(default=100, verbose_name="O'quvchilar limiti")
    
    # Financials
    payment_day = models.PositiveSmallIntegerField(default=5, verbose_name="To'lov sanasi")
    monthly_price = models.PositiveIntegerField(default=0, verbose_name="Oylik to'lov")
    trial_ends = models.DateField(null=True, blank=True, verbose_name="Sinov davri tugashi")

    # Manual feature overrides (e.g. {"leads": true, "finance": false})
    features = models.JSONField(default=dict, blank=True)

    # Chaqmoq settings
    max_daily_lightning = models.PositiveIntegerField(default=0, verbose_name="Bir kunda max chaqmoq (0=cheksiz)")
    max_daily_deduction = models.PositiveIntegerField(default=0, verbose_name="Bir kunda max ayirish (0=cheksiz)")

    # Donation Settings
    donation_enabled = models.BooleanField(default=False)
    donation_card_number = models.CharField(max_length=20, blank=True, default="")
    donation_card_holder = models.CharField(max_length=100, blank=True, default="")
    donation_qr_image = models.ImageField(upload_to="center/qr/", blank=True, null=True)

    # Promo Settings
    promo_code = models.CharField(max_length=50, blank=True, null=True)
    discount_amount = models.PositiveIntegerField(default=0)
    discount_percent = models.PositiveIntegerField(default=0)
    promo_start = models.DateField(null=True, blank=True)
    promo_end = models.DateField(null=True, blank=True)

    # ✅ Trash settings
    manager_can_access_trash = models.BooleanField(default=False, verbose_name="Manager trashga kira olsinmi?")

    # ✅ Student Management settings
    manager_can_add_student = models.BooleanField(default=True, verbose_name="Manager o'quvchi qo'shishi mumkinmi?")
    manager_can_remove_student = models.BooleanField(default=True, verbose_name="Manager o'quvchilarni o'chirishi mumkinmi?")
    teacher_can_add_student = models.BooleanField(default=False, verbose_name="O'qituvchi o'quvchi qo'shishi mumkinmi?")
    teacher_can_remove_student = models.BooleanField(default=False, verbose_name="O'qituvchi o'quvchilarni o'chirishi mumkinmi?")


    STATUS_ACTIVE = "ACTIVE"
    STATUS_BLOCKED = "BLOCKED"
    STATUS_ARCHIVED = "ARCHIVED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "ACTIVE"),
        (STATUS_BLOCKED, "BLOCKED"),
        (STATUS_ARCHIVED, "ARCHIVED"),
    ]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)
    # is_deleted field is now provided by SoftDeleteMixin
    
    # ✅ System Center - o'chirib bo'lmaydi (asosiy markaz)
    is_system = models.BooleanField(default=False, help_text="Tizim markazi - o'chirib bo'lmaydi") 
    is_demo = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Demo markazmi (savdo/demo uchun test ma'lumotlar).",
    )



    def save(self, *args, **kwargs):
        # Auto-fill tenant DB credentials from default DB config when not provided manually.
        default_db = (getattr(settings, "DATABASES", {}) or {}).get("default", {})
        if default_db and "postgresql" in str(default_db.get("ENGINE", "")).lower():
            self.db_name = self.db_name or str(default_db.get("NAME", "") or "").strip() or None
            self.db_user = self.db_user or str(default_db.get("USER", "") or "").strip() or None
            self.db_password = self.db_password or str(default_db.get("PASSWORD", "") or "").strip() or None
            self.db_host = self.db_host or str(default_db.get("HOST", "") or "localhost").strip() or "localhost"
            self.db_port = self.db_port or str(default_db.get("PORT", "") or "5432").strip() or "5432"

        # 1. Generate or Clean Slug
        if not self.slug:
            # Auto-generate from name
            base = slugify(self.name)[:70] or "center"
        else:
             # Clean manual input
            base = slugify(self.slug)[:70]
            
        # 2. Ensure Uniqueness
        slug = base
        i = 2
        # Check for conflicts (excluding self)
        while Center.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{i}"
            i += 1
            
        self.slug = slug
        super().save(*args, **kwargs)



    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name

    @property
    def effective_student_limit(self):
        """
        Returns the effective student limit.
        Takes the maximum of:
        1. Manual capacity_limit
        2. Manual max_students (redundant field check)
        3. Active subscription plan limit
        Default fallback is 50.
        """
        # Take the higher of the manual limit fields
        manual_limit = max(self.capacity_limit or 0, self.max_students or 0)
        limit = manual_limit or 50
        
        sub = self.active_subscription
        if sub:
            plan_limit = sub.plan.max_students
            if plan_limit > limit:
                limit = plan_limit
        return limit

    @property
    def days_left(self):
        """
        - expires_at bo‘lmasa -> None (templateda '—' ko‘rsatamiz)
        - expired bo‘lsa -> 0
        - aks holda -> ceil(days)
        """
        if not self.expires_at:
            return None
        now = timezone.now()
        diff = (self.expires_at - now).total_seconds()
        if diff <= 0:
            return 0
        return int(math.ceil(diff / 86400.0))

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    @property
    def get_counts(self):
        """O'quvchilar va guruhlar sonini hisoblash"""
        from education.models import Group
        from accounts.models import User
        
        # ✅ User modelidan to'g'ridan-to'g'ri o'quvchilar sonini olamiz
        students_count = User.objects.filter(
            center=self,
            role='student',
            is_archived=False
        ).count()
        
        groups_count = Group.objects.filter(center=self, is_archived=False).count()
        
        return {
            'students': students_count,
            'groups': groups_count
        }




from core.soft_delete import SoftDeleteQuerySet

class UserManager(BaseUserManager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email majburiy")
        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        if password is None:
            password = BaseUserManager().make_random_password()

        return self._create_user(email=email, password=password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser uchun is_staff=True bo‘lishi shart")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser uchun is_superuser=True bo‘lishi shart")

        if not password:
            raise ValueError("Superuser uchun password majburiy")

        return self._create_user(email=email, password=password, **extra_fields)


class Roles(models.TextChoices):
    DIREKTOR = "director", _("Direktor")
    MANAGER = "manager", _("Manager")
    OQITUVCHI = "teacher", _("O‘qituvchi")
    OQUVCHI = "student", _("O‘quvchi")
    OTA_ONA = "parent", _("Ota-ona")


class User(SoftDeleteMixin, AbstractUser):
    # ✅ username ishlatilmaydi
    username = None

    # ✅ login email bo‘ladi
    email = models.EmailField(_("Login email (Gmail bo‘lishi mumkin)"), unique=True)

    # ✅ phone login
    phone_number = models.CharField(_("Telefon raqami (Login uchun)"), max_length=20, null=True, blank=True)
    
    # ✅ Telegram bot
    telegram_id = models.CharField(_("Telegram ID"), max_length=50, null=True, blank=True)
    telegram_username = models.CharField(_("Telegram Username"), max_length=100, null=True, blank=True)
    is_telegram_linked = models.BooleanField(_("Telegram Ulangan"), default=False)
    
    reset_code = models.CharField(_("Reset kod"), max_length=10, null=True, blank=True)
    reset_code_expire_at = models.DateTimeField(null=True, blank=True)
    reset_code_used = models.BooleanField(default=False)
    reset_attempts = models.PositiveIntegerField(default=0)

    # ✅ Special Permissions
    can_access_trash = models.BooleanField(default=False, verbose_name="Trash bo'limiga kira oladimi?")
    reset_last_attempt = models.DateTimeField(null=True, blank=True)

    # ✅ profil rasm
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    # asosiy ma'lumotlar
    ism = models.CharField(max_length=100)
    familya = models.CharField(max_length=120)
    otchestvo = models.CharField(max_length=150, blank=True, null=True)

    telefon1 = models.CharField(max_length=20, blank=True, default="")
    telefon2 = models.CharField(max_length=20, blank=True, default="")

    # ✅ STUDENT FIELDS (Faqat student uchun majburiy qilinadi form darajasida)
    birth_date = models.DateField(_("Tug‘ilgan sana"), null=True, blank=True)
    
    class Gender(models.TextChoices):
        MALE = "male", _("Erkak")
        FEMALE = "female", _("Ayol")

    gender = models.CharField(
        _("Jinsi"), 
        max_length=10, 
        choices=Gender.choices, 
        null=True, 
        blank=True
    )
    
    passport_id = models.CharField(_("Passport ID"), max_length=20, blank=True, null=True)
    jshr = models.CharField(_("JSHR Pinfl"), max_length=14, blank=True, null=True)
    address = models.TextField(_("Manzil"), blank=True, null=True)

    lavozim = models.CharField(max_length=50, blank=True, default="")

    # rollar
    role = models.CharField(max_length=20, choices=Roles.choices)
    center = models.ForeignKey(Center, on_delete=models.SET_NULL, null=True, blank=True)

    # email ko‘rinishi (ixtiyoriy)
    gmail = models.EmailField(_("Gmail"), blank=True, default="")

    # chaqmoq sistemi
    chaqmoq = models.PositiveIntegerField(default=0, verbose_name="Chaqmoq soni")

    # ⭐ O‘qituvchi foizi
    oqituvchi_foizi = models.PositiveIntegerField(
        default=40,
        verbose_name="O‘qituvchi ulushi (%)"
    )

    is_archived = models.BooleanField(default=False, verbose_name="Arxivlangan")
    is_demo_user = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Demo foydalanuvchi",
        help_text="Demo markaz uchun yaratilgan test foydalanuvchi.",
    )

    # Parent children
    children = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="parents",
        blank=True,
        limit_choices_to={"role": "student"},
        verbose_name="Farzandlari"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        from accounts.utils import normalize_phone
        if self.phone_number:
            self.phone_number = normalize_phone(self.phone_number)
        if self.telefon1:
            self.telefon1 = normalize_phone(self.telefon1)
        super().save(*args, **kwargs)


    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def full_name(self) -> str:
        parts = []
        seen = set()
        for val in [self.ism, self.familya, self.otchestvo]:
            if val and str(val).strip().lower() not in ('none', 'null', ''):
                word = str(val).strip()
                if word not in seen:
                    parts.append(word)
                    seen.add(word)
        return " ".join(parts).strip()

    def get_full_name(self) -> str:
        return self.full_name()

class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"

    def __str__(self):
        return f"{self.user.email} - {self.action} ({self.created_at})"

class BotAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="bot_admin_profile")
    telegram_id = models.CharField(max_length=50, unique=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="added_admins")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bot Admin"
        verbose_name_plural = "Bot Adminlari"

    def __str__(self):
        return f"{self.user.full_name()} ({self.telegram_id})"

class BotSettings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot Sozlamasi"
        verbose_name_plural = "Bot Sozlamalari"

    @classmethod
    def get_val(cls, key, default=None):
        setting = cls.objects.filter(key=key).first()
        return setting.value if setting else default

    def __str__(self):
        return f"{self.key}: {self.value}"

class AdminAuditLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name="admin_actions")
    action_type = models.CharField(max_length=100)
    target_audience = models.CharField(max_length=255, null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Admin Audit Log"
        verbose_name_plural = "Admin Audit Loglari"

    def __str__(self):
        return f"{self.admin.email} - {self.action_type} - {self.timestamp}"

    # --- Multi-tenant DB metadata (foundation, safe for future use) ---
    db_name = models.CharField(max_length=128, blank=True, null=True, help_text="Имя отдельной базы данных центра (PostgreSQL)")
    db_user = models.CharField(max_length=128, blank=True, null=True, help_text="Пользователь БД центра")
    db_password = models.CharField(max_length=128, blank=True, null=True, help_text="Пароль БД центра (TODO: хранить безопасно, использовать env или vault)")
    db_host = models.CharField(max_length=128, blank=True, null=True, help_text="Хост БД центра")
    db_port = models.CharField(max_length=16, blank=True, null=True, help_text="Порт БД центра")
    is_active = models.BooleanField(default=True, help_text="Активен ли центр и его база данных")
    # --- Конец foundation для multi-tenant ---
