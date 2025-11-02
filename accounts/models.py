from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

class Center(models.Model):
    nom = models.CharField(max_length=150)
    manzil = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'O‘quv markaz'
        verbose_name_plural = 'O‘quv markazlar'

    def __str__(self):
        return self.nom

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email majburiy')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password or BaseUserManager().make_random_password(), **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser uchun is_staff=True bo‘lishi shart')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser uchun is_superuser=True bo‘lishi shart')
        return self._create_user(email, password, **extra_fields)

class Roles(models.TextChoices):
    DIREKTOR = 'director', _('Direktor')
    MANAGER  = 'manager',  _('Manager')
    OQITUVCHI= 'teacher',  _("O‘qituvchi")
    OQUVCHI  = 'student',  _("O‘quvchi")

class User(AbstractUser):
    username = None  # ishlatmaymiz
    email = models.EmailField('Login email (Gmail bo‘lishi mumkin)', unique=True)

    ism = models.CharField(max_length=100)
    familya = models.CharField(max_length=120)
    telefon1 = models.CharField(max_length=20)
    telefon2 = models.CharField(max_length=20, blank=True)

    # qo‘shimcha ko‘rsatish uchun
    lavozim = models.CharField(max_length=50, blank=True)

    # rollar va markaz
    role = models.CharField(max_length=20, choices=Roles.choices)
    center = models.ForeignKey(Center, on_delete=models.SET_NULL, null=True, blank=True)

    # ixtiyoriy: asl Gmail kiritish uchun alohida maydon (vizual)
    gmail = models.EmailField('Gmail', blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'

    def full_name(self):
        return f"{self.ism} {self.familya}"
    
    def get_full_name(self):
        """Django bilan mos bo‘lgan nom (oldingi full_name bilan bir xil natija)"""
        return f"{self.ism} {self.familya}".strip()

    def __str__(self):
        return f"{self.full_name()} — {self.get_role_display()}"


