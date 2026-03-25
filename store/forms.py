from datetime import timedelta

from django import forms
from .models import Product, ProductImage
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Lead, TrialLesson

User = get_user_model()

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nom', 'narx_chaqmoq', 'narx_som', 'izoh']

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
            'address',
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
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Yashash manzili'}),
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
        if center:
            from django.db.models import Q
            from .models import Manba, Yonalish, LeadStatus
            self.fields['manba'].queryset = Manba.objects.filter(Q(center=center) | Q(center__isnull=True))
            self.fields['yonalish'].queryset = Yonalish.objects.filter(Q(center=center) | Q(center__isnull=True))
            self.fields['status'].queryset = LeadStatus.objects.filter(Q(center=center) | Q(center__isnull=True), is_active=True).order_by("order", "nom")
            self.fields['assigned_manager'].queryset = User.objects.filter(center=center, role="manager", is_archived=False).order_by("ism", "familya")
        else:
            self.fields['assigned_manager'].queryset = User.objects.none()

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
