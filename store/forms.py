from datetime import timedelta

from django import forms
from .models import Product, ProductImage
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import Lead, LeadGroup, LeadStatus, TrialLesson, Yonalish
from .lead_services import (
    build_dynamic_lead_status_choices,
    get_or_create_custom_lead_status,
    get_or_create_lead_subject,
    get_or_create_pipeline_status,
    normalize_phone,
    resolve_dynamic_status_value,
)

User = get_user_model()

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nom', 'narx_chaqmoq', 'narx_som', 'izoh', 'allowed_categories']

    def __init__(self, *args, center=None, **kwargs):
        super().__init__(*args, **kwargs)
        from education.models import Category
        from accounts.models import Center as CenterModel
        if center:
            first_center = CenterModel.objects.order_by('id').first()
            if first_center and center.id == first_center.id:
                qs = Category.objects.filter(Q(center=center) | Q(center__isnull=True))
            else:
                qs = Category.objects.filter(center=center)
        else:
            qs = Category.objects.none()
        self.fields['allowed_categories'].queryset = qs
        self.fields['allowed_categories'].required = False
        self.fields['allowed_categories'].widget = forms.CheckboxSelectMultiple()
        self.fields['allowed_categories'].label = "Ko'rinadigan bo'limlar"
        self.fields['allowed_categories'].help_text = "Hech biri tanlanmasa — barcha o'quvchilarga ko'rinadi"

class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['rasm']



class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'ism',
            'familya',
            'otchestvo',
            'birth_date',
            'gender',
            'passport_id',
            'jshr',
            'telefon1',
            'telefon2',
            'parent_phone',
            'parent_name',
            'address',
            'bilim_darajasi',
            'manba',
            'yonalish',
            'assigned_manager',
            'status',
            'next_follow_up_date',
            'lost_reason',
            'comment',
        ]
        widgets = {
            'ism': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ism'}),
            'familya': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Familya'}),
            'otchestvo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Otasining ismi'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'passport_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport ID'}),
            'jshr': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'JSHR'}),
            'telefon1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon raqam 1'}),
            'telefon2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon raqam 2'}),
            'parent_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ota-ona telefoni'}),
            'parent_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ota-onasi ismi'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Yashash manzili'}),
            'bilim_darajasi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bilim darajasi / Sinfi'}),
            'manba': forms.Select(attrs={'class': 'form-select'}),
            'yonalish': forms.Select(attrs={'class': 'form-select'}),
            'assigned_manager': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'next_follow_up_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lost_reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lead yo‘qotilish sababi'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Masalan: O‘quvchi darsga kech kelgan, yoki rad etgan sababi...'}),
        }

    def __init__(self, *args, **kwargs):
        center = kwargs.pop('center', None)
        super().__init__(*args, **kwargs)
        self.center = center

        if center:
            from .models import Manba, Yonalish, LeadStatus
            self.fields['manba'].queryset = Manba.objects.filter(center=center).order_by("nom")
            self.fields['yonalish'].queryset = Yonalish.objects.filter(center=center).order_by("nom")
            self.fields['status'].queryset = LeadStatus.objects.filter(center=center, is_active=True).order_by("order", "nom")
            self.fields['assigned_manager'].queryset = User.objects.filter(center=center, role="manager", is_archived=False).order_by("ism", "familya")
        else:
            self.fields['manba'].queryset = self.fields['manba'].queryset.none()
            self.fields['yonalish'].queryset = self.fields['yonalish'].queryset.none()
            self.fields['status'].queryset = self.fields['status'].queryset.none()
            self.fields['assigned_manager'].queryset = User.objects.none()

        for field_name in ("manba", "yonalish", "status"):
            self.fields[field_name].empty_label = ""

    def _validate_center_owned_choice(self, cleaned_data, field_name):
        selected = cleaned_data.get(field_name)
        center = getattr(self, "center", None)
        if not selected or not center:
            return
        if getattr(selected, "center_id", None) != center.id:
            self.add_error(field_name, "Tanlangan qiymat shu o'quv markaziga tegishli emas.")

    @staticmethod
    def _resolve_status_code(status) -> str:
        if not status:
            return ""
        if getattr(status, "code", ""):
            return status.code
        name = (getattr(status, "nom", "") or "").strip().lower()
        if "yo'qot" in name or "lost" in name or "rad" in name:
            return "lost"
        if "tasdiq" in name or "registered" in name:
            return "registered"
        if "trial" in name and ("keldi" in name or "attended" in name):
            return "trial_attended"
        if "trial" in name:
            return "trial_scheduled"
        if "aloqa" in name or "contact" in name:
            return "contacted"
        return "new"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        status_code = self._resolve_status_code(status)
        lost_reason = (cleaned.get("lost_reason") or "").strip()

        self._validate_center_owned_choice(cleaned, "manba")
        self._validate_center_owned_choice(cleaned, "yonalish")
        self._validate_center_owned_choice(cleaned, "status")
        self._validate_center_owned_choice(cleaned, "assigned_manager")

        if status_code == "lost" and not lost_reason:
            self.add_error("lost_reason", "Lost status uchun sabab kiritish majburiy.")

        follow_up_date = cleaned.get("next_follow_up_date")
        if follow_up_date and follow_up_date < (timezone.localdate() - timedelta(days=365)):
            self.add_error("next_follow_up_date", "Follow-up sanasi juda eski bo‘lishi mumkin emas.")

        return cleaned


class TrialLessonForm(forms.ModelForm):
    class Meta:
        model = TrialLesson
        fields = [
            "lead",
            "group",
            "teacher",
            "scheduled_at",
            "attended",
            "result_status",
            "notes",
        ]
        widgets = {
            "lead": forms.Select(attrs={"class": "form-select"}),
            "group": forms.Select(attrs={"class": "form-select"}),
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "scheduled_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "attended": forms.Select(
                attrs={"class": "form-select"},
                choices=[("", "—"), ("True", "Keldi"), ("False", "Kelmadi")],
            ),
            "result_status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Trial bo‘yicha izoh"}),
        }

    def __init__(self, *args, **kwargs):
        center = kwargs.pop("center", None)
        super().__init__(*args, **kwargs)

        # ModelForm bool selectni oddiy selectga aylantirganda qo'lda normalize qilamiz.
        self.fields["attended"].required = False

        from education.models import Group

        if center:
            self.fields["lead"].queryset = Lead.objects.filter(center=center, is_archived=False).select_related("status", "manba").order_by("-qoshilgan_sana")
            self.fields["group"].queryset = Group.objects.filter(center=center, is_archived=False).select_related("oqituvchi").order_by("nom")
            self.fields["teacher"].queryset = User.objects.filter(center=center, role="teacher", is_archived=False).order_by("ism", "familya")
        else:
            self.fields["lead"].queryset = Lead.objects.none()
            self.fields["group"].queryset = Group.objects.none()
            self.fields["teacher"].queryset = User.objects.none()

    def clean_attended(self):
        value = self.cleaned_data.get("attended")
        if value in ("", None):
            return None
        if value in (True, "True", "true", "1", 1):
            return True
        if value in (False, "False", "false", "0", 0):
            return False
        return None

    def clean(self):
        cleaned = super().clean()
        lead = cleaned.get("lead")
        group = cleaned.get("group")
        teacher = cleaned.get("teacher")
        result_status = cleaned.get("result_status")
        attended = cleaned.get("attended")

        if lead and group and lead.center_id and group.center_id and lead.center_id != group.center_id:
            self.add_error("group", "Tanlangan guruh lead markazi bilan mos emas.")

        if teacher and group and teacher.center_id and group.center_id and teacher.center_id != group.center_id:
            self.add_error("teacher", "Tanlangan o‘qituvchi guruh markaziga mos emas.")

        if result_status == TrialLesson.ResultStatus.ABSENT and attended is True:
            self.add_error("attended", "Absent natija uchun attended=True bo‘lishi mumkin emas.")

        if result_status in (TrialLesson.ResultStatus.ATTENDED, TrialLesson.ResultStatus.CONVERTED) and attended is None:
            cleaned["attended"] = True

        if result_status == TrialLesson.ResultStatus.CONVERTED:
            cleaned["registered_after_trial"] = True

        return cleaned


class LeadApiFilterForm(forms.Form):
    DATE_PRESET_CHOICES = (
        ("", "Barchasi"),
        ("today", "Bugun"),
        ("7", "7 kun"),
        ("30", "30 kun"),
        ("custom", "Oraliq"),
    )
    VIEW_CHOICES = (
        ("table", "Jadval"),
        ("kanban", "Bosqichlar"),
    )

    subjects = forms.ModelMultipleChoiceField(queryset=Yonalish.objects.none(), required=False)
    statuses = forms.MultipleChoiceField(choices=(), required=False)
    date_preset = forms.ChoiceField(choices=DATE_PRESET_CHOICES, required=False)
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)
    q = forms.CharField(required=False, max_length=120)
    page = forms.IntegerField(required=False, min_value=1, initial=1)
    page_size = forms.IntegerField(required=False, min_value=1, max_value=100, initial=20)
    view = forms.ChoiceField(choices=VIEW_CHOICES, required=False, initial="table")

    def __init__(self, *args, **kwargs):
        center = kwargs.pop("center", None)
        super().__init__(*args, **kwargs)
        queryset = Yonalish.objects.filter(is_active=True)
        if center:
            queryset = queryset.filter(center=center)
        else:
            queryset = queryset.none()
        self.fields["subjects"].queryset = queryset.order_by("nom")
        self.fields["statuses"].choices = [
            (item["value"], item["label"])
            for item in build_dynamic_lead_status_choices(center)
        ]

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas.")
        return cleaned


class LeadApiForm(forms.Form):
    name = forms.CharField(max_length=220, required=True)
    phone = forms.CharField(max_length=20, required=True)
    parent_name = forms.CharField(max_length=150, required=False)
    bilim_darajasi = forms.CharField(max_length=100, required=False)
    subject = forms.ModelChoiceField(queryset=Yonalish.objects.none(), required=True)
    status = forms.ChoiceField(choices=(), required=False, initial=Lead.PipelineStatus.NEW)
    note = forms.CharField(required=False, widget=forms.Textarea)
    manager = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    lead_group = forms.ModelChoiceField(queryset=LeadGroup.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        self.center = kwargs.pop("center", None)
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        if self.center:
            subject_qs = Yonalish.objects.filter(center=self.center, is_active=True)
            if self.instance and getattr(self.instance, "yonalish_id", None):
                subject_qs = Yonalish.objects.filter(center=self.center).filter(
                    Q(is_active=True) | Q(id=self.instance.yonalish_id)
                )
            self.fields["subject"].queryset = subject_qs.order_by("nom")
            self.fields["manager"].queryset = User.objects.filter(
                center=self.center,
                role="manager",
                is_archived=False,
            ).order_by("ism", "familya")
            lead_group_qs = LeadGroup.objects.filter(center=self.center, is_archived=False)
            if self.instance and getattr(self.instance, "lead_group_id", None):
                lead_group_qs = lead_group_qs | LeadGroup.objects.filter(center=self.center, id=self.instance.lead_group_id)
            self.fields["lead_group"].queryset = lead_group_qs.order_by("name", "id")
        else:
            self.fields["subject"].queryset = Yonalish.objects.none()
            self.fields["manager"].queryset = User.objects.none()
            self.fields["lead_group"].queryset = LeadGroup.objects.none()

        status_choices = build_dynamic_lead_status_choices(self.center)
        status_values = {item["value"] for item in status_choices}
        if self.instance and getattr(self.instance, "status_id", None):
            current_status_value = resolve_dynamic_status_value(self.instance)
            if current_status_value.startswith("custom:") and current_status_value not in status_values:
                status_choices.append(
                    {
                        "value": current_status_value,
                        "label": getattr(self.instance.status, "nom", "Holat"),
                        "tone": "gray",
                        "kind": "custom",
                        "id": self.instance.status_id,
                    }
                )
        self.fields["status"].choices = [(item["value"], item["label"]) for item in status_choices]

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone") or "")

    def clean_status(self):
        value = (self.cleaned_data.get("status") or Lead.PipelineStatus.NEW).strip()
        if value.startswith("custom:"):
            raw_id = value.split(":", 1)[1].strip()
            if not raw_id.isdigit():
                raise forms.ValidationError("Tanlangan holat noto‘g‘ri.")
            from .models import LeadStatus

            status = LeadStatus.objects.filter(
                center=self.center,
                id=int(raw_id),
                is_active=True,
            ).first()
            if not status:
                raise forms.ValidationError("Tanlangan holat topilmadi.")
        return value

    def save(self, *, actor=None):
        if not self.is_valid():
            raise ValueError("LeadApiForm save() faqat valid form bilan ishlaydi.")

        lead = self.instance or Lead(center=self.center)
        raw_name = (self.cleaned_data["name"] or "").strip()
        name_parts = raw_name.split()
        lead.ism = name_parts[0] if name_parts else raw_name
        lead.familya = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        lead.telefon1 = self.cleaned_data["phone"]
        lead.parent_name = (self.cleaned_data.get("parent_name") or "").strip()
        lead.bilim_darajasi = (self.cleaned_data.get("bilim_darajasi") or "").strip()
        lead.yonalish = self.cleaned_data["subject"]
        lead.comment = (self.cleaned_data.get("note") or "").strip()
        lead.lead_group = self.cleaned_data.get("lead_group")
        lead.center = self.center or lead.center
        lead.yosh = int(getattr(lead, "yosh", 0) or 0)
        if actor and not lead.created_by_id:
            lead.created_by = actor

        selected_manager = self.cleaned_data.get("manager")
        if actor and getattr(actor, "role", "") == "manager":
            lead.assigned_manager = actor
        elif selected_manager:
            lead.assigned_manager = selected_manager
        elif lead.assigned_manager_id:
            pass
        else:
            fallback_manager = User.objects.filter(
                center=self.center,
                role="manager",
                is_archived=False,
            ).order_by("ism", "familya", "id").first()
            if fallback_manager:
                lead.assigned_manager = fallback_manager
            elif actor:
                lead.assigned_manager = actor

        status_value = self.cleaned_data.get("status") or Lead.PipelineStatus.NEW
        if status_value.startswith("custom:"):
            from .models import LeadStatus

            status_id = int(status_value.split(":", 1)[1])
            lead.status = LeadStatus.objects.filter(
                center=self.center,
                id=status_id,
                is_active=True,
            ).first()
        else:
            lead.status = get_or_create_pipeline_status(center=self.center, pipeline_status=status_value)
        lead.save()
        return lead


class LeadSubjectForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)

    def __init__(self, *args, **kwargs):
        self.center = kwargs.pop("center", None)
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        value = " ".join((self.cleaned_data.get("name") or "").strip().split())
        if not value:
            raise forms.ValidationError("Fan nomini kiriting.")
        if self.instance and Yonalish.objects.filter(center=self.center, nom__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bunday fan allaqachon mavjud.")
        return value

    def save(self):
        if not self.is_valid():
            raise ValueError("LeadSubjectForm save() faqat valid form bilan ishlaydi.")
        if self.instance:
            changed_fields = []
            if self.instance.nom != self.cleaned_data["name"]:
                self.instance.nom = self.cleaned_data["name"]
                changed_fields.append("nom")
            if not self.instance.is_active:
                self.instance.is_active = True
                changed_fields.append("is_active")
            if changed_fields:
                self.instance.save(update_fields=changed_fields)
            return self.instance
        return get_or_create_lead_subject(
            center=self.center,
            name=self.cleaned_data["name"],
        )


class LeadStatusForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)

    def __init__(self, *args, **kwargs):
        self.center = kwargs.pop("center", None)
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        value = " ".join((self.cleaned_data.get("name") or "").strip().split())
        if not value:
            raise forms.ValidationError("Holat nomini kiriting.")
        if self.instance and LeadStatus.objects.filter(center=self.center, nom__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bunday holat allaqachon mavjud.")
        return value

    def save(self):
        if not self.is_valid():
            raise ValueError("LeadStatusForm save() faqat valid form bilan ishlaydi.")
        if self.instance:
            changed_fields = []
            if self.instance.nom != self.cleaned_data["name"]:
                self.instance.nom = self.cleaned_data["name"]
                changed_fields.append("nom")
            if not self.instance.is_active:
                self.instance.is_active = True
                changed_fields.append("is_active")
            if changed_fields:
                self.instance.save(update_fields=changed_fields)
            return self.instance
        return get_or_create_custom_lead_status(
            center=self.center,
            name=self.cleaned_data["name"],
        )


class LeadAssignLeadGroupForm(forms.Form):
    lead_group = forms.ModelChoiceField(queryset=LeadGroup.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        center = kwargs.pop("center", None)
        super().__init__(*args, **kwargs)
        queryset = LeadGroup.objects.filter(is_archived=False)
        if center:
            queryset = queryset.filter(center=center)
        self.fields["lead_group"].queryset = queryset.order_by("name", "id")


class LeadConvertForm(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs.pop("center", None)
        super().__init__(*args, **kwargs)


class LeadGroupForm(forms.Form):
    name = forms.CharField(max_length=150, required=True)
    subject = forms.ModelChoiceField(queryset=Yonalish.objects.none(), required=False)
    department = forms.ModelChoiceField(queryset=Yonalish.objects.none(), required=False)
    min_students = forms.IntegerField(required=True, min_value=1, max_value=100)
    note = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        self.center = kwargs.pop("center", None)
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        from education.models import Category
        from accounts.models import Center

        if self.center:
            self.fields["subject"].queryset = Yonalish.objects.filter(center=self.center, is_active=True).order_by("nom")
            first_center = Center.objects.order_by("id").first()
            if first_center and self.center.id == first_center.id:
                self.fields["department"].queryset = Category.objects.filter(
                    Q(center=self.center) | Q(center__isnull=True)
                ).order_by("name")
            else:
                self.fields["department"].queryset = Category.objects.filter(center=self.center).order_by("name")
        else:
            self.fields["subject"].queryset = Yonalish.objects.none()
            self.fields["department"].queryset = Category.objects.none()

    def clean_name(self):
        value = " ".join((self.cleaned_data.get("name") or "").split()).strip()
        if not value:
            raise forms.ValidationError("Lead guruhi nomini kiriting.")
        qs = LeadGroup.objects.filter(center=self.center, name__iexact=value, is_archived=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Bunday lead guruhi allaqachon mavjud.")
        return value

    def save(self, *, actor=None):
        if not self.is_valid():
            raise ValueError("LeadGroupForm save() faqat valid form bilan ishlaydi.")

        lead_group = self.instance or LeadGroup(center=self.center)
        lead_group.name = self.cleaned_data["name"]
        if "subject" in self.data:
            lead_group.subject = self.cleaned_data.get("subject")
        lead_group.department = self.cleaned_data.get("department")
        lead_group.min_students = self.cleaned_data["min_students"]
        lead_group.note = (self.cleaned_data.get("note") or "").strip()
        if actor and not lead_group.created_by_id:
            lead_group.created_by = actor
        lead_group.save()
        return lead_group


class LeadGroupConvertForm(forms.Form):
    WEEKDAY_CHOICES = [
        ("1", "Du"),
        ("2", "Se"),
        ("3", "Cho"),
        ("4", "Pa"),
        ("5", "Ju"),
        ("6", "Sha"),
        ("7", "Yak"),
    ]

    name = forms.CharField(max_length=150, required=True)
    department = forms.ModelChoiceField(queryset=LeadGroup.objects.none(), required=False)
    teacher = forms.ModelChoiceField(queryset=User.objects.none(), required=True)
    lesson_days = forms.MultipleChoiceField(choices=WEEKDAY_CHOICES, required=False)
    lesson_time = forms.TimeField(required=True)
    lesson_end_time = forms.TimeField(required=False)
    start_date = forms.DateField(required=True)
    price = forms.IntegerField(required=True, min_value=0)
    teacher_share = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.center = kwargs.pop("center", None)
        super().__init__(*args, **kwargs)
        from education.models import Category
        from accounts.models import Center

        if self.center:
            first_center = Center.objects.order_by("id").first()
            if first_center and self.center.id == first_center.id:
                self.fields["department"].queryset = Category.objects.filter(
                    Q(center=self.center) | Q(center__isnull=True)
                ).order_by("name")
            else:
                self.fields["department"].queryset = Category.objects.filter(center=self.center).order_by("name")
            self.fields["teacher"].queryset = User.objects.filter(
                center=self.center,
                role="teacher",
                is_archived=False,
            ).order_by("ism", "familya")
        else:
            self.fields["department"].queryset = Category.objects.none()
            self.fields["teacher"].queryset = User.objects.none()

    def clean_lesson_days(self):
        values = self.cleaned_data.get("lesson_days") or []
        unique_values = []
        for value in values:
            cleaned = str(value).strip()
            if cleaned and cleaned not in unique_values:
                unique_values.append(cleaned)
        return unique_values

    def clean_teacher_share(self):
        return (self.cleaned_data.get("teacher_share") or "").strip()

    def clean(self):
        cleaned = super().clean()

        teacher = cleaned.get("teacher")
        lesson_days = cleaned.get("lesson_days") or []
        lesson_time = cleaned.get("lesson_time")
        lesson_end_time = cleaned.get("lesson_end_time")

        if lesson_end_time and lesson_time and lesson_end_time <= lesson_time:
            self.add_error("lesson_end_time", "Tugash vaqti boshlanishdan keyin bo'lishi kerak.")

        if teacher and lesson_time and lesson_days and self.center:
            from education.services.hr import teacher_is_available

            weekdays = [int(value) for value in lesson_days if str(value).isdigit()]
            if not teacher_is_available(
                teacher,
                center=self.center,
                weekdays=weekdays,
                start_time=lesson_time,
                end_time=lesson_end_time,
            ):
                self.add_error("teacher", "Tanlangan kun va vaqtlarda bu o'qituvchi band.")

        return cleaned
