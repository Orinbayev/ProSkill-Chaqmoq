from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils.translation import get_language


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def get_localized(self, field_base: str, language_code: str | None = None):
        lang = (language_code or get_language() or "uz")[:2]
        candidates = [f"{field_base}_{lang}", f"{field_base}_uz", field_base]
        visited = set()
        for attr in candidates:
            if attr in visited:
                continue
            visited.add(attr)
            if not hasattr(self, attr):
                continue
            value = getattr(self, attr)
            if value not in (None, ""):
                return value
        return ""


class SiteSetting(TimeStampedModel):
    site_name = models.CharField(max_length=120, default="ChaqmoqApp", verbose_name="Sayt nomi")
    logo = models.ImageField(upload_to="marketing/site/", blank=True, null=True, verbose_name="Logo")
    favicon = models.ImageField(upload_to="marketing/site/", blank=True, null=True, verbose_name="Favicon")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefon")
    telegram = models.URLField(blank=True, verbose_name="Telegram")
    instagram = models.URLField(blank=True, verbose_name="Instagram")
    youtube = models.URLField(blank=True, verbose_name="YouTube")
    address = models.CharField(max_length=255, blank=True, verbose_name="Manzil")

    meta_title = models.CharField(max_length=255, blank=True, verbose_name="Meta sarlavha")
    meta_description = models.TextField(blank=True, verbose_name="Meta tavsif")
    meta_title_uz = models.CharField(max_length=255, blank=True, verbose_name="Meta sarlavha (UZ)")
    meta_title_ru = models.CharField(max_length=255, blank=True, verbose_name="Meta sarlavha (RU)")
    meta_title_en = models.CharField(max_length=255, blank=True, verbose_name="Meta sarlavha (EN)")
    meta_description_uz = models.TextField(blank=True, verbose_name="Meta tavsif (UZ)")
    meta_description_ru = models.TextField(blank=True, verbose_name="Meta tavsif (RU)")
    meta_description_en = models.TextField(blank=True, verbose_name="Meta tavsif (EN)")

    hero_title = models.CharField(max_length=255, blank=True, verbose_name="Hero sarlavha")
    hero_subtitle = models.TextField(blank=True, verbose_name="Hero matn")
    hero_title_uz = models.CharField(max_length=255, blank=True, verbose_name="Hero sarlavha (UZ)")
    hero_title_ru = models.CharField(max_length=255, blank=True, verbose_name="Hero sarlavha (RU)")
    hero_title_en = models.CharField(max_length=255, blank=True, verbose_name="Hero sarlavha (EN)")
    hero_subtitle_uz = models.TextField(blank=True, verbose_name="Hero matn (UZ)")
    hero_subtitle_ru = models.TextField(blank=True, verbose_name="Hero matn (RU)")
    hero_subtitle_en = models.TextField(blank=True, verbose_name="Hero matn (EN)")
    hero_image = models.ImageField(upload_to="marketing/hero/", blank=True, null=True, verbose_name="Hero rasmi")

    primary_cta_text = models.CharField(max_length=60, default="Demo olish", verbose_name="Asosiy CTA matni")
    primary_cta_url = models.CharField(max_length=255, default="/demo/", verbose_name="Asosiy CTA URL")
    primary_cta_text_uz = models.CharField(max_length=60, blank=True, verbose_name="Asosiy CTA (UZ)")
    primary_cta_text_ru = models.CharField(max_length=60, blank=True, verbose_name="Asosiy CTA (RU)")
    primary_cta_text_en = models.CharField(max_length=60, blank=True, verbose_name="Asosiy CTA (EN)")

    secondary_cta_text = models.CharField(max_length=60, default="Narxlarni ko'rish", verbose_name="Ikkinchi CTA matni")
    secondary_cta_url = models.CharField(max_length=255, default="/pricing/", verbose_name="Ikkinchi CTA URL")
    secondary_cta_text_uz = models.CharField(max_length=60, blank=True, verbose_name="Ikkinchi CTA (UZ)")
    secondary_cta_text_ru = models.CharField(max_length=60, blank=True, verbose_name="Ikkinchi CTA (RU)")
    secondary_cta_text_en = models.CharField(max_length=60, blank=True, verbose_name="Ikkinchi CTA (EN)")

    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Sayt sozlamasi"
        verbose_name_plural = "Sayt sozlamalari"

    def __str__(self):
        return self.site_name


class PartnerLogo(TimeStampedModel):
    name = models.CharField(max_length=120, verbose_name="Nomi")
    image = models.ImageField(upload_to="marketing/partners/", verbose_name="Logo")
    url = models.URLField(blank=True, verbose_name="Havola")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Hamkor logosi"
        verbose_name_plural = "Hamkor logolari"

    def __str__(self):
        return self.name


class FeatureBlock(TimeStampedModel):
    class Section(models.TextChoices):
        FEATURE = "feature", "Imkoniyatlar"
        INTEGRATION = "integration", "Integratsiyalar"
        SOLUTION = "solution", "Muammo va yechim"

    section = models.CharField(max_length=20, choices=Section.choices, default=Section.FEATURE, verbose_name="Bo'lim")
    title = models.CharField(max_length=150, verbose_name="Sarlavha")
    title_uz = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (UZ)")
    title_ru = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (RU)")
    title_en = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (EN)")

    subtitle = models.CharField(max_length=180, blank=True, verbose_name="Qisqa matn")
    subtitle_uz = models.CharField(max_length=180, blank=True, verbose_name="Qisqa matn (UZ)")
    subtitle_ru = models.CharField(max_length=180, blank=True, verbose_name="Qisqa matn (RU)")
    subtitle_en = models.CharField(max_length=180, blank=True, verbose_name="Qisqa matn (EN)")

    icon = models.CharField(
        max_length=60,
        blank=True,
        help_text="Masalan: bi bi-people-fill yoki fa-solid fa-chart-line",
        verbose_name="Ikonka classi",
    )

    description = models.TextField(verbose_name="Tavsif")
    description_uz = models.TextField(blank=True, verbose_name="Tavsif (UZ)")
    description_ru = models.TextField(blank=True, verbose_name="Tavsif (RU)")
    description_en = models.TextField(blank=True, verbose_name="Tavsif (EN)")

    image = models.ImageField(upload_to="marketing/features/", blank=True, null=True, verbose_name="Rasm")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        ordering = ["section", "order", "id"]
        verbose_name = "Imkoniyat bloki"
        verbose_name_plural = "Imkoniyat bloklari"

    def __str__(self):
        return f"{self.get_section_display()} - {self.get_localized('title', 'uz') or self.title}"


class ScreenshotSection(TimeStampedModel):
    title = models.CharField(max_length=150, verbose_name="Sarlavha")
    title_uz = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (UZ)")
    title_ru = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (RU)")
    title_en = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (EN)")

    description = models.TextField(blank=True, verbose_name="Tavsif")
    description_uz = models.TextField(blank=True, verbose_name="Tavsif (UZ)")
    description_ru = models.TextField(blank=True, verbose_name="Tavsif (RU)")
    description_en = models.TextField(blank=True, verbose_name="Tavsif (EN)")

    image = models.ImageField(upload_to="marketing/screenshots/", verbose_name="Rasm")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Ekran ko'rinishi"
        verbose_name_plural = "Ekran ko'rinishlari"

    def __str__(self):
        return self.get_localized("title", "uz") or self.title


class PricingPlan(TimeStampedModel):
    name = models.CharField(max_length=120, verbose_name="Tarif nomi")
    name_uz = models.CharField(max_length=120, blank=True, verbose_name="Tarif nomi (UZ)")
    name_ru = models.CharField(max_length=120, blank=True, verbose_name="Tarif nomi (RU)")
    name_en = models.CharField(max_length=120, blank=True, verbose_name="Tarif nomi (EN)")

    student_range = models.CharField(max_length=120, help_text="Masalan: 0-200 ta", verbose_name="O'quvchi limiti")
    student_range_uz = models.CharField(max_length=120, blank=True, verbose_name="O'quvchi limiti (UZ)")
    student_range_ru = models.CharField(max_length=120, blank=True, verbose_name="O'quvchi limiti (RU)")
    student_range_en = models.CharField(max_length=120, blank=True, verbose_name="O'quvchi limiti (EN)")

    duration_months = models.PositiveSmallIntegerField(help_text="Masalan: 3, 6, 9, 12", verbose_name="Davomiylik (oy)")
    old_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Eski narx")
    current_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Joriy narx")

    discount_label = models.CharField(max_length=80, blank=True, verbose_name="Chegirma yorlig'i")
    discount_label_uz = models.CharField(max_length=80, blank=True, verbose_name="Chegirma yorlig'i (UZ)")
    discount_label_ru = models.CharField(max_length=80, blank=True, verbose_name="Chegirma yorlig'i (RU)")
    discount_label_en = models.CharField(max_length=80, blank=True, verbose_name="Chegirma yorlig'i (EN)")

    badge_text = models.CharField(max_length=80, blank=True, verbose_name="Badge matni")
    badge_text_uz = models.CharField(max_length=80, blank=True, verbose_name="Badge matni (UZ)")
    badge_text_ru = models.CharField(max_length=80, blank=True, verbose_name="Badge matni (RU)")
    badge_text_en = models.CharField(max_length=80, blank=True, verbose_name="Badge matni (EN)")

    is_recommended = models.BooleanField(default=False, verbose_name="Tavsiya etilgan")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")

    class Meta:
        ordering = ["duration_months", "order", "id"]
        verbose_name = "Tarif rejasi"
        verbose_name_plural = "Tarif rejalari"

    def __str__(self):
        return f"{self.get_localized('name', 'uz') or self.name} - {self.duration_months} oy"


class PricingFeature(TimeStampedModel):
    pricing_plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE, related_name="features", verbose_name="Tarif")
    text = models.CharField(max_length=255, verbose_name="Matn")
    text_uz = models.CharField(max_length=255, blank=True, verbose_name="Matn (UZ)")
    text_ru = models.CharField(max_length=255, blank=True, verbose_name="Matn (RU)")
    text_en = models.CharField(max_length=255, blank=True, verbose_name="Matn (EN)")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Tarif afzalligi"
        verbose_name_plural = "Tarif afzalliklari"

    def __str__(self):
        return self.get_localized("text", "uz") or self.text


class Testimonial(TimeStampedModel):
    full_name = models.CharField(max_length=120, verbose_name="F.I.Sh")
    center_name = models.CharField(max_length=120, verbose_name="Markaz nomi")
    role = models.CharField(max_length=120, blank=True, verbose_name="Lavozim")
    role_uz = models.CharField(max_length=120, blank=True, verbose_name="Lavozim (UZ)")
    role_ru = models.CharField(max_length=120, blank=True, verbose_name="Lavozim (RU)")
    role_en = models.CharField(max_length=120, blank=True, verbose_name="Lavozim (EN)")

    text = models.TextField(verbose_name="Sharh matni")
    text_uz = models.TextField(blank=True, verbose_name="Sharh matni (UZ)")
    text_ru = models.TextField(blank=True, verbose_name="Sharh matni (RU)")
    text_en = models.TextField(blank=True, verbose_name="Sharh matni (EN)")

    avatar = models.ImageField(upload_to="marketing/testimonials/", blank=True, null=True, verbose_name="Avatar")
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Reyting",
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Mijoz fikri"
        verbose_name_plural = "Mijozlar fikri"

    def __str__(self):
        return f"{self.full_name} ({self.center_name})"


class FAQ(TimeStampedModel):
    question = models.CharField(max_length=255, verbose_name="Savol")
    question_uz = models.CharField(max_length=255, blank=True, verbose_name="Savol (UZ)")
    question_ru = models.CharField(max_length=255, blank=True, verbose_name="Savol (RU)")
    question_en = models.CharField(max_length=255, blank=True, verbose_name="Savol (EN)")

    answer = models.TextField(verbose_name="Javob")
    answer_uz = models.TextField(blank=True, verbose_name="Javob (UZ)")
    answer_ru = models.TextField(blank=True, verbose_name="Javob (RU)")
    answer_en = models.TextField(blank=True, verbose_name="Javob (EN)")

    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Ko'p so'raladigan savol"
        verbose_name_plural = "Ko'p so'raladigan savollar"

    def __str__(self):
        return self.get_localized("question", "uz") or self.question


phone_validator = RegexValidator(
    regex=r"^\+?998\d{9}$",
    message="Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak.",
)


class DemoLead(TimeStampedModel):
    full_name = models.CharField(max_length=120, verbose_name="F.I.Sh")
    center_name = models.CharField(max_length=120, verbose_name="Markaz nomi")
    phone = models.CharField(max_length=20, validators=[phone_validator], verbose_name="Telefon")
    selected_plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demo_leads",
        verbose_name="Tanlangan tarif",
    )
    password = models.CharField(max_length=128, blank=True, verbose_name="Parol")
    consent = models.BooleanField(default=False, verbose_name="Rozilik")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    is_contacted = models.BooleanField(default=False, verbose_name="Bog'lanilgan")
    note = models.TextField(blank=True, verbose_name="Izoh")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demo so'rovi"
        verbose_name_plural = "Demo so'rovlari"

    def __str__(self):
        return f"{self.full_name} - {self.phone}"


class SupportCard(TimeStampedModel):
    title = models.CharField(max_length=150, verbose_name="Sarlavha")
    title_uz = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (UZ)")
    title_ru = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (RU)")
    title_en = models.CharField(max_length=150, blank=True, verbose_name="Sarlavha (EN)")

    description = models.TextField(verbose_name="Tavsif")
    description_uz = models.TextField(blank=True, verbose_name="Tavsif (UZ)")
    description_ru = models.TextField(blank=True, verbose_name="Tavsif (RU)")
    description_en = models.TextField(blank=True, verbose_name="Tavsif (EN)")

    button_text = models.CharField(max_length=60, default="Ko'rish", verbose_name="Tugma matni")
    button_text_uz = models.CharField(max_length=60, blank=True, verbose_name="Tugma matni (UZ)")
    button_text_ru = models.CharField(max_length=60, blank=True, verbose_name="Tugma matni (RU)")
    button_text_en = models.CharField(max_length=60, blank=True, verbose_name="Tugma matni (EN)")

    button_url = models.URLField(verbose_name="Tugma havolasi")
    icon = models.CharField(max_length=60, blank=True, verbose_name="Ikonka classi")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Yordam kartasi"
        verbose_name_plural = "Yordam kartalari"

    def __str__(self):
        return self.get_localized("title", "uz") or self.title


class Vacancy(TimeStampedModel):
    class EmploymentType(models.TextChoices):
        OFFLINE = "offline", "Oflayn"
        ONLINE = "online", "Onlayn"
        HYBRID = "hybrid", "Gibrid"

    title = models.CharField(max_length=150, verbose_name="Lavozim")
    title_uz = models.CharField(max_length=150, blank=True, verbose_name="Lavozim (UZ)")
    title_ru = models.CharField(max_length=150, blank=True, verbose_name="Lavozim (RU)")
    title_en = models.CharField(max_length=150, blank=True, verbose_name="Lavozim (EN)")

    city = models.CharField(max_length=120, blank=True, verbose_name="Shahar")
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.OFFLINE, verbose_name="Ish formati")
    employment_type_uz = models.CharField(max_length=60, blank=True, verbose_name="Ish formati (UZ)")
    employment_type_ru = models.CharField(max_length=60, blank=True, verbose_name="Ish formati (RU)")
    employment_type_en = models.CharField(max_length=60, blank=True, verbose_name="Ish formati (EN)")

    department = models.CharField(max_length=120, blank=True, verbose_name="Bo'lim")
    department_uz = models.CharField(max_length=120, blank=True, verbose_name="Bo'lim (UZ)")
    department_ru = models.CharField(max_length=120, blank=True, verbose_name="Bo'lim (RU)")
    department_en = models.CharField(max_length=120, blank=True, verbose_name="Bo'lim (EN)")

    description = models.TextField(verbose_name="Tavsif")
    description_uz = models.TextField(blank=True, verbose_name="Tavsif (UZ)")
    description_ru = models.TextField(blank=True, verbose_name="Tavsif (RU)")
    description_en = models.TextField(blank=True, verbose_name="Tavsif (EN)")

    requirements = models.TextField(verbose_name="Talablar")
    requirements_uz = models.TextField(blank=True, verbose_name="Talablar (UZ)")
    requirements_ru = models.TextField(blank=True, verbose_name="Talablar (RU)")
    requirements_en = models.TextField(blank=True, verbose_name="Talablar (EN)")

    responsibilities = models.TextField(verbose_name="Vazifalar")
    responsibilities_uz = models.TextField(blank=True, verbose_name="Vazifalar (UZ)")
    responsibilities_ru = models.TextField(blank=True, verbose_name="Vazifalar (RU)")
    responsibilities_en = models.TextField(blank=True, verbose_name="Vazifalar (EN)")

    apply_url = models.URLField(blank=True, verbose_name="Ariza URL")
    apply_button_text = models.CharField(max_length=60, default="Ariza topshirish", verbose_name="Ariza tugmasi")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Vakansiya"
        verbose_name_plural = "Vakansiyalar"

    def __str__(self):
        return self.get_localized("title", "uz") or self.title


class StaticPage(TimeStampedModel):
    class PageKey(models.TextChoices):
        PRIVACY = "privacy", "Maxfiylik siyosati"
        TERMS = "terms", "Foydalanish shartlari"
        ABOUT = "about", "Biz haqimizda"

    key = models.CharField(max_length=40, unique=True, choices=PageKey.choices, verbose_name="Sahifa kaliti")
    title = models.CharField(max_length=200, verbose_name="Sarlavha")
    title_uz = models.CharField(max_length=200, blank=True, verbose_name="Sarlavha (UZ)")
    title_ru = models.CharField(max_length=200, blank=True, verbose_name="Sarlavha (RU)")
    title_en = models.CharField(max_length=200, blank=True, verbose_name="Sarlavha (EN)")

    content = models.TextField(verbose_name="Kontent")
    content_uz = models.TextField(blank=True, verbose_name="Kontent (UZ)")
    content_ru = models.TextField(blank=True, verbose_name="Kontent (RU)")
    content_en = models.TextField(blank=True, verbose_name="Kontent (EN)")

    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        ordering = ["key"]
        verbose_name = "Statik sahifa"
        verbose_name_plural = "Statik sahifalar"

    def __str__(self):
        return self.get_localized("title", "uz") or self.title
