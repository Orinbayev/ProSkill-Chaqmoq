from django import forms

from .models import (
    REGION_CHOICES,
    DemoLead,
    FAQ,
    FeatureBlock,
    PartnerLogo,
    PricingFeature,
    PricingPlan,
    ScreenshotSection,
    SiteSetting,
    StaticPage,
    SupportCard,
    Testimonial,
    Vacancy,
)
from .pricing_plan_io import (
    IMPORT_MODE_CREATE_ONLY,
    IMPORT_MODE_SKIP_DUPLICATES,
    IMPORT_MODE_UPDATE_EXISTING,
)


DEMO_FORM_I18N = {
    "uz": {
        "full_name": "Ism va familiya",
        "center_name": "O'quv markaz nomi",
        "phone": "Telefon raqam",
        "region": "Viloyatni tanlang",
        "students_count": "O'quvchilar soni (taxminan)",
        "comment": "Qo'shimcha izoh (ixtiyoriy)",
        "consent": "Ma'lumotlarimni qayta ishlashga roziman",
        "ph_full_name": "Masalan: Amirxon O'rinbayev",
        "ph_center_name": "Masalan: Yuksalish o'quv markazi",
        "ph_phone": "+998901234567",
        "ph_students_count": "Masalan: 50-100 ta, 200 dan ortiq",
        "ph_comment": "Savollaringiz yoki qo'shimcha ma'lumot...",
        "region_placeholder": "Viloyatni tanlang",
        "err_phone_prefix": "Telefon +998 bilan boshlanishi kerak.",
        "err_phone_length": "Telefon raqam 12 ta raqamdan iborat bo'lishi kerak.",
        "err_consent": "So'rov yuborish uchun rozilikni belgilang.",
        "err_region": "Iltimos, viloyatingizni tanlang.",
    },
    "ru": {
        "full_name": "Имя и фамилия",
        "center_name": "Название учебного центра",
        "phone": "Номер телефона",
        "region": "Выберите область",
        "students_count": "Количество учеников (примерно)",
        "comment": "Дополнительный комментарий (необязательно)",
        "consent": "Согласен на обработку данных",
        "ph_full_name": "Например: Амирхон Оринбаев",
        "ph_center_name": "Например: Учебный центр Yuksalish",
        "ph_phone": "+998901234567",
        "ph_students_count": "Например: 50-100, более 200",
        "ph_comment": "Вопросы или дополнительная информация...",
        "region_placeholder": "Выберите область",
        "err_phone_prefix": "Телефон должен начинаться с +998.",
        "err_phone_length": "Телефон должен содержать 12 цифр после +.",
        "err_consent": "Для отправки заявки нужно отметить согласие.",
        "err_region": "Пожалуйста, выберите область.",
    },
    "en": {
        "full_name": "Full name",
        "center_name": "Learning center name",
        "phone": "Phone number",
        "region": "Select region",
        "students_count": "Number of students (approx.)",
        "comment": "Additional comment (optional)",
        "consent": "I agree to personal data processing",
        "ph_full_name": "For example: Amirxon O'rinbayev",
        "ph_center_name": "For example: Yuksalish Learning Center",
        "ph_phone": "+998901234567",
        "ph_students_count": "For example: 50-100, more than 200",
        "ph_comment": "Questions or additional information...",
        "region_placeholder": "Select region",
        "err_phone_prefix": "Phone number must start with +998.",
        "err_phone_length": "Phone number must contain 12 digits after +.",
        "err_consent": "Consent is required to submit the request.",
        "err_region": "Please select your region.",
    },
}


class StyledModelForm(forms.ModelForm):
    """Custom superadmin form inputlari uchun umumiy CSS va til maydoni markerlari."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_i18n_fields = False
        for field_name, field in self.fields.items():
            widget = field.widget

            lang_suffix = None
            if field_name.endswith("_uz"):
                lang_suffix = "uz"
            elif field_name.endswith("_ru"):
                lang_suffix = "ru"
            elif field_name.endswith("_en"):
                lang_suffix = "en"

            if lang_suffix:
                self.has_i18n_fields = True
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} lang-field lang-{lang_suffix}".strip()
                widget.attrs["data-lang"] = lang_suffix

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", f"{widget.attrs.get('class', '')} sa-check".strip())
                continue
            if isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", f"{widget.attrs.get('class', '')} sa-file".strip())
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", f"{widget.attrs.get('class', '')} sa-textarea".strip())
                widget.attrs.setdefault("rows", 4)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", f"{widget.attrs.get('class', '')} sa-select".strip())
            else:
                widget.attrs.setdefault("class", f"{widget.attrs.get('class', '')} sa-input".strip())


class DemoLeadForm(forms.ModelForm):
    class Meta:
        model = DemoLead
        fields = ["full_name", "center_name", "phone", "region", "students_count", "comment", "consent"]
        widgets = {
            "full_name": forms.TextInput(),
            "center_name": forms.TextInput(),
            "phone": forms.TextInput(),
            "region": forms.Select(),
            "students_count": forms.TextInput(),
            "comment": forms.Textarea(attrs={"rows": 3}),
            "consent": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        lang_code = kwargs.pop("lang_code", "uz")
        super().__init__(*args, **kwargs)

        text_pack = DEMO_FORM_I18N.get(lang_code, DEMO_FORM_I18N["uz"])
        self.text_pack = text_pack

        # region: bo'sh tanlov variantini qo'shamiz
        self.fields["region"].required = True
        self.fields["region"].choices = [("", text_pack["region_placeholder"])] + list(REGION_CHOICES)
        self.fields["consent"].required = True
        self.fields["students_count"].required = False
        self.fields["comment"].required = False

        self.fields["full_name"].label = text_pack["full_name"]
        self.fields["center_name"].label = text_pack["center_name"]
        self.fields["phone"].label = text_pack["phone"]
        self.fields["region"].label = text_pack["region"]
        self.fields["students_count"].label = text_pack["students_count"]
        self.fields["comment"].label = text_pack["comment"]
        self.fields["consent"].label = text_pack["consent"]

        self.fields["full_name"].widget.attrs["placeholder"] = text_pack["ph_full_name"]
        self.fields["center_name"].widget.attrs["placeholder"] = text_pack["ph_center_name"]
        self.fields["phone"].widget.attrs["placeholder"] = text_pack["ph_phone"]
        self.fields["students_count"].widget.attrs["placeholder"] = text_pack["ph_students_count"]
        self.fields["comment"].widget.attrs["placeholder"] = text_pack["ph_comment"]

        for field_name, field in self.fields.items():
            if field_name != "consent":
                if isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.setdefault("class", "input input-textarea")
                else:
                    field.widget.attrs.setdefault("class", "input")

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        normalized = "+" + "".join(ch for ch in phone if ch.isdigit())
        if not normalized.startswith("+998"):
            raise forms.ValidationError(self.text_pack["err_phone_prefix"])
        if len(normalized) != 13:
            raise forms.ValidationError(self.text_pack["err_phone_length"])
        return normalized

    def clean_region(self):
        region = self.cleaned_data.get("region")
        if not region:
            raise forms.ValidationError(self.text_pack["err_region"])
        return region

    def clean_consent(self):
        consent = self.cleaned_data.get("consent")
        if not consent:
            raise forms.ValidationError(self.text_pack["err_consent"])
        return consent


class SiteSettingForm(StyledModelForm):
    class Meta:
        model = SiteSetting
        fields = [
            "site_name",
            "logo",
            "favicon",
            "phone",
            "telegram",
            "instagram",
            "youtube",
            "address",
            "meta_title",
            "meta_title_uz",
            "meta_title_ru",
            "meta_title_en",
            "meta_description",
            "meta_description_uz",
            "meta_description_ru",
            "meta_description_en",
            "hero_title",
            "hero_title_uz",
            "hero_title_ru",
            "hero_title_en",
            "hero_subtitle",
            "hero_subtitle_uz",
            "hero_subtitle_ru",
            "hero_subtitle_en",
            "hero_image",
            "primary_cta_text",
            "primary_cta_text_uz",
            "primary_cta_text_ru",
            "primary_cta_text_en",
            "primary_cta_url",
            "secondary_cta_text",
            "secondary_cta_text_uz",
            "secondary_cta_text_ru",
            "secondary_cta_text_en",
            "secondary_cta_url",
            "is_active",
        ]


class SiteSettingHeroImageForm(StyledModelForm):
    class Meta:
        model = SiteSetting
        fields = ["hero_image"]
        labels = {"hero_image": "Bosh sahifa hero rasmi"}
        help_texts = {
            "hero_image": "Landing boshidagi asosiy rasm. Tavsiya: keng formatdagi JPG/PNG (masalan, 1600x1100)."
        }


class PartnerLogoForm(StyledModelForm):
    class Meta:
        model = PartnerLogo
        fields = ["name", "image", "url", "order", "is_active"]


class FeatureBlockForm(StyledModelForm):
    class Meta:
        model = FeatureBlock
        fields = [
            "section",
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "subtitle",
            "subtitle_uz",
            "subtitle_ru",
            "subtitle_en",
            "icon",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
            "image",
            "order",
            "is_active",
        ]


class ScreenshotSectionForm(StyledModelForm):
    class Meta:
        model = ScreenshotSection
        fields = [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
            "image",
            "order",
            "is_active",
        ]


class PricingPlanForm(StyledModelForm):
    class Meta:
        model = PricingPlan
        fields = [
            "name",
            "name_uz",
            "name_ru",
            "name_en",
            "student_range",
            "student_range_uz",
            "student_range_ru",
            "student_range_en",
            "duration_months",
            "old_price",
            "current_price",
            "discount_label",
            "discount_label_uz",
            "discount_label_ru",
            "discount_label_en",
            "badge_text",
            "badge_text_uz",
            "badge_text_ru",
            "badge_text_en",
            "is_recommended",
            "is_active",
            "order",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        placeholders = {
            "name": "Masalan: Start",
            "name_uz": "Masalan: Boshlang'ich",
            "name_ru": "Например: Старт",
            "name_en": "For example: Starter",
            "student_range": "Masalan: 0-200 ta",
            "student_range_uz": "Masalan: 0-200 ta",
            "student_range_ru": "Например: 0-200 учеников",
            "student_range_en": "For example: 0-200 students",
            "duration_months": "Masalan: 1, 3, 6, 12",
            "current_price": "Masalan: 390000",
            "old_price": "Masalan: 490000",
            "discount_label": "Masalan: -20%",
            "discount_label_uz": "Masalan: 2 oyda tejamkor",
            "discount_label_ru": "Например: Выгоднее на 20%",
            "discount_label_en": "For example: Save 20%",
            "badge_text": "Masalan: Eng mashhur",
            "badge_text_uz": "Masalan: Tavsiya etiladi",
            "badge_text_ru": "Например: Популярный выбор",
            "badge_text_en": "For example: Most popular",
            "order": "Masalan: 1",
        }
        helper_texts = {
            "student_range": "Masalan: 0-200 ta",
            "duration_months": "Masalan: 1, 3, 6, 12 oy",
            "current_price": "Joriy to'lov qiymatini kiriting (so'm).",
            "old_price": "Aksiya bo'lsa eski narxni kiriting, bo'lmasa bo'sh qoldiring.",
            "discount_label": "Masalan: -20% yoki 'Chegirma'.",
            "badge_text": "Masalan: Eng mashhur, Tavsiya etiladi.",
            "order": "Kichik raqam yuqoriroq ko'rinadi.",
            "is_recommended": "Public pricing bo'limida tarifni ajratib ko'rsatadi.",
            "is_active": "Nofaol tarif public sahifada ko'rinmaydi.",
        }

        for field_name, placeholder in placeholders.items():
            if field_name in self.fields and not isinstance(self.fields[field_name].widget, forms.CheckboxInput):
                self.fields[field_name].widget.attrs.setdefault("placeholder", placeholder)

        for field_name, help_text in helper_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        if "duration_months" in self.fields:
            self.fields["duration_months"].widget.attrs.setdefault("min", "1")
            self.fields["duration_months"].widget.attrs.setdefault("step", "1")
            self.fields["duration_months"].widget.attrs.setdefault("inputmode", "numeric")
        if "order" in self.fields:
            self.fields["order"].widget.attrs.setdefault("min", "1")
            self.fields["order"].widget.attrs.setdefault("step", "1")
            self.fields["order"].widget.attrs.setdefault("inputmode", "numeric")
        if "current_price" in self.fields:
            self.fields["current_price"].widget.attrs.setdefault("min", "0")
            self.fields["current_price"].widget.attrs.setdefault("step", "0.01")
            self.fields["current_price"].widget.attrs.setdefault("inputmode", "decimal")
        if "old_price" in self.fields:
            self.fields["old_price"].widget.attrs.setdefault("min", "0")
            self.fields["old_price"].widget.attrs.setdefault("step", "0.01")
            self.fields["old_price"].widget.attrs.setdefault("inputmode", "decimal")

    def clean_duration_months(self):
        duration = self.cleaned_data.get("duration_months")
        if duration is None or duration <= 0:
            raise forms.ValidationError("Davomiylik oylari musbat son bo'lishi kerak.")
        return duration

    def clean(self):
        cleaned_data = super().clean()
        old_price = cleaned_data.get("old_price")
        current_price = cleaned_data.get("current_price")
        if current_price is not None and current_price <= 0:
            self.add_error("current_price", "Joriy narx 0 dan katta bo'lishi kerak.")
        if old_price is not None and old_price < 0:
            self.add_error("old_price", "Eski narx manfiy bo'lmasligi kerak.")
        return cleaned_data


class PricingFeatureForm(StyledModelForm):
    class Meta:
        model = PricingFeature
        fields = ["pricing_plan", "text", "text_uz", "text_ru", "text_en", "order"]


class PricingPlanImportForm(forms.Form):
    file = forms.FileField(label="Import fayli")
    file_format = forms.ChoiceField(
        label="Fayl formati",
        choices=[
            ("auto", "Auto aniqlash"),
            ("xlsx", "Excel (.xlsx)"),
            ("json", "JSON (.json)"),
        ],
        initial="auto",
    )
    import_mode = forms.ChoiceField(
        label="Import strategiyasi",
        choices=[
            (IMPORT_MODE_UPDATE_EXISTING, "Mavjudlarini yangilash (replace mode)"),
            (IMPORT_MODE_SKIP_DUPLICATES, "Dublikatlarni o'tkazib yuborish"),
            (IMPORT_MODE_CREATE_ONLY, "Hammasini yangi qo'shish"),
        ],
        initial=IMPORT_MODE_UPDATE_EXISTING,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.setdefault("class", "sa-file")
        self.fields["file_format"].widget.attrs.setdefault("class", "sa-select")
        self.fields["import_mode"].widget.attrs.setdefault("class", "mkt-radio-grid")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        filename = (uploaded_file.name or "").lower()
        if not (filename.endswith(".xlsx") or filename.endswith(".json")):
            raise forms.ValidationError("Faqat .xlsx yoki .json fayl yuklash mumkin.")
        return uploaded_file


class TestimonialForm(StyledModelForm):
    class Meta:
        model = Testimonial
        fields = [
            "full_name",
            "center_name",
            "role",
            "role_uz",
            "role_ru",
            "role_en",
            "text",
            "text_uz",
            "text_ru",
            "text_en",
            "avatar",
            "rating",
            "is_active",
            "order",
        ]


class FAQForm(StyledModelForm):
    class Meta:
        model = FAQ
        fields = [
            "question",
            "question_uz",
            "question_ru",
            "question_en",
            "answer",
            "answer_uz",
            "answer_ru",
            "answer_en",
            "order",
            "is_active",
        ]


class SupportCardForm(StyledModelForm):
    class Meta:
        model = SupportCard
        fields = [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
            "button_text",
            "button_text_uz",
            "button_text_ru",
            "button_text_en",
            "button_url",
            "icon",
            "order",
            "is_active",
        ]


class VacancyForm(StyledModelForm):
    class Meta:
        model = Vacancy
        fields = [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "city",
            "employment_type",
            "employment_type_uz",
            "employment_type_ru",
            "employment_type_en",
            "department",
            "department_uz",
            "department_ru",
            "department_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
            "requirements",
            "requirements_uz",
            "requirements_ru",
            "requirements_en",
            "responsibilities",
            "responsibilities_uz",
            "responsibilities_ru",
            "responsibilities_en",
            "apply_url",
            "apply_button_text",
            "is_active",
            "order",
        ]


class StaticPageForm(StyledModelForm):
    class Meta:
        model = StaticPage
        fields = [
            "key",
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "content",
            "content_uz",
            "content_ru",
            "content_en",
            "is_active",
        ]


class DemoLeadUpdateForm(StyledModelForm):
    class Meta:
        model = DemoLead
        fields = ["is_contacted", "note", "students_count"]


# === Tarif v2 — Bosqich 4: PlanFeature CRUD form ===

class PlanFeatureForm(StyledModelForm):
    """SuperAdmin uchun PlanFeature (billing.PlanFeature) yaratish/tahrirlash formasi.
    Qo'shimcha: feature'ni START / PRO / PREMIUM tariflariga bog'lash uchun 3 ta checkbox."""

    included_in_start = forms.BooleanField(required=False, label="START tarifda mavjud")
    included_in_pro = forms.BooleanField(required=False, label="PRO tarifda mavjud")
    included_in_premium = forms.BooleanField(required=False, label="PREMIUM tarifda mavjud")

    class Meta:
        # Lazy import — billing'ni modul yuklanishida import qilmaslik uchun.
        from billing.models import PlanFeature as _PlanFeature
        model = _PlanFeature
        fields = [
            "code",
            "name",
            "name_uz",
            "name_ru",
            "name_en",
            "description_uz",
            "category",
            "icon",
            "is_core",
            "order",
            "is_active",
        ]
        widgets = {
            "description_uz": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            from billing.models import SubscriptionPlan
            for code in ["START", "PRO", "PREMIUM"]:
                plan = SubscriptionPlan.objects.filter(code=code).first()
                if plan and plan.plan_features.filter(pk=self.instance.pk).exists():
                    self.fields[f"included_in_{code.lower()}"].initial = True

    def save_plan_memberships(self, instance):
        """View tomonidan chaqiriladi — tarif M2M aloqalarini sinxronlaydi."""
        from billing.models import SubscriptionPlan
        for code in ["START", "PRO", "PREMIUM"]:
            plan = SubscriptionPlan.objects.filter(code=code).first()
            if not plan:
                continue
            checked = bool(self.cleaned_data.get(f"included_in_{code.lower()}"))
            if checked:
                plan.plan_features.add(instance)
            else:
                plan.plan_features.remove(instance)
