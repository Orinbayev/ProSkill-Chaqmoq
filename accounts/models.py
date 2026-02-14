from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import math


# accounts/models.py
from django.db import models
from django.utils.text import slugify

class Center(models.Model):
    class Plan(models.TextChoices):
        FREE = "FREE", "FREE"
        STANDARD = "STANDARD", "STANDARD"
        PREMIUM = "PREMIUM", "PREMIUM"
        PRO = "PRO", "PRO"

    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="") 

    slug = models.SlugField(unique=True) 
    # active field removed in favor of status
    created_at = models.DateTimeField(auto_now_add=True)

    plan = models.CharField(max_length=50, default="FREE")

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
    is_deleted = models.BooleanField(default=False)
    
    # ✅ System Center - o'chirib bo'lmaydi (asosiy markaz)
    is_system = models.BooleanField(default=False, help_text="Tizim markazi - o'chirib bo'lmaydi") 



    def save(self, *args, **kwargs):
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
        
        groups_count = Group.objects.filter(center=self).count()
        
        return {
            'students': students_count,
            'groups': groups_count
        }




class UserManager(BaseUserManager):
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


class User(AbstractUser):
    # ✅ username ishlatilmaydi
    username = None

    # ✅ login email bo‘ladi
    email = models.EmailField(_("Login email (Gmail bo‘lishi mumkin)"), unique=True)

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

    def __str__(self):
        try:
            role = self.get_role_display()
        except Exception:
            role = self.role
        return f"{self.get_full_name()} — {role}"
