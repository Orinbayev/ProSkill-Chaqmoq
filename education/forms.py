from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import CertificateTemplate, CenterExamSetting, Enrollment, ExamResult, Group

User = get_user_model()

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = [
            "category_obj", "center", "nom", "izoh", "oqituvchi",
            "kurs_narxi", "oqituvchi_foiz", "oy_dars_soni",
            "course_start_date", "duration_months", "lessons_per_week",
            "estimated_end_date", "estimated_end_date_manual", "schedule_estimation_note",
        ]
        labels = {
            "nom": "Guruh nomi",
            "oqituvchi": "O‘qituvchi",
            "kurs_narxi": "Kurs narxi (so‘m)",
            "oqituvchi_foiz": "O‘qituvchi foizi (%)",
            "oy_dars_soni": "Bir oyda darslar soni",
            "course_start_date": "Boshlanish sanasi",
            "duration_months": "Davomiyligi (oy)",
            "lessons_per_week": "Haftasiga darslar soni",
            "estimated_end_date": "Taxminiy tugash sanasi",
            "estimated_end_date_manual": "Taxminiy sanani qo‘lda kiritish",
            "schedule_estimation_note": "Tahmin izohi",
            "izoh": "Izoh",
            "center": "Markaz",
            "category_obj": "Bo‘lim",
        }
        widgets = {
            "course_start_date": forms.DateInput(attrs={"type": "date"}),
            "estimated_end_date": forms.DateInput(attrs={"type": "date"}),
            "schedule_estimation_note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        center = kwargs.pop("center", None)
        super().__init__(*args, **kwargs)

        # UX/flow safety: bu forma endi bo'lim ichidan ochiladi va
        # o'qituvchi foizi teacher profilidan olinadi.
        for field_name in [
            "category_obj",
            "oqituvchi_foiz",
            "estimated_end_date_manual",
            "schedule_estimation_note",
            "izoh",
        ]:
            self.fields.pop(field_name, None)
        
        # Filter teachers by center
        if "oqituvchi" in self.fields:
            teach_qs = User.objects.filter(role="teacher")
            if center:
                teach_qs = teach_qs.filter(center=center)
            self.fields["oqituvchi"].queryset = teach_qs.order_by("ism", "familya")
            self.fields["oqituvchi"].label_from_instance = lambda obj: f"{obj.ism or ''} {obj.familya or ''}".strip() or obj.email

        # Filter categories by center
        if "category_obj" in self.fields:
            from .models import Category
            cat_qs = Category.objects.all()
            if center:
                from django.db.models import Q
                cat_qs = cat_qs.filter(Q(center=center) | Q(center__isnull=True))
            self.fields["category_obj"].queryset = cat_qs.order_by("name")

        # Restrict center choice
        if center and "center" in self.fields:
            from accounts.models import Center
            self.fields["center"].queryset = Center.objects.filter(id=center.id)
            self.fields["center"].initial = center

        # Bu maydonlar agar kiritilmasa ham xato bermaydi
        for f in [
            "kurs_narxi", "oqituvchi_foiz", "oy_dars_soni",
            "course_start_date", "duration_months", "lessons_per_week",
            "estimated_end_date", "estimated_end_date_manual", "schedule_estimation_note",
            "category_obj", "center",
        ]:
            if f in self.fields:
                self.fields[f].required = False

        # Default qiymatlar
        if "kurs_narxi" in self.fields: self.fields["kurs_narxi"].initial = 500000
        if "oqituvchi_foiz" in self.fields: self.fields["oqituvchi_foiz"].initial = 40
        if "oy_dars_soni" in self.fields: self.fields["oy_dars_soni"].initial = 12
        if "lessons_per_week" in self.fields: self.fields["lessons_per_week"].initial = 3
        if "duration_months" in self.fields: self.fields["duration_months"].initial = 0
        if "schedule_estimation_note" in self.fields:
            self.fields["schedule_estimation_note"].initial = (
                "Bu sana taxminiy hisob bo‘lib, bayramlar, tadbirlar yoki dars ko‘chirilishlari sabab o‘zgarishi mumkin"
            )
        if (
            "course_start_date" in self.fields
            and not self.is_bound
            and not getattr(self.instance, "pk", None)
        ):
            self.fields["course_start_date"].initial = timezone.localdate()
        if "estimated_end_date" in self.fields:
            self.fields["estimated_end_date"].widget.attrs["readonly"] = "readonly"

    def clean_lessons_per_week(self):
        value = self.cleaned_data.get("lessons_per_week")
        if value in (None, "", 0):
            return 3
        if value < 1:
            raise forms.ValidationError("Haftalik darslar soni kamida 1 bo‘lishi kerak.")
        return value

    def clean(self):
        cleaned = super().clean()
        from education.services.group_schedule_service import calculate_estimated_end_date

        start_date = cleaned.get("course_start_date")
        duration_months = cleaned.get("duration_months") or 0
        lessons_per_week = cleaned.get("lessons_per_week") or 3

        # Safe auto-calc: faqat start + duration mavjud bo'lsa qayta hisoblaymiz.
        if start_date and int(duration_months) > 0:
            cleaned["estimated_end_date"] = calculate_estimated_end_date(
                course_start_date=start_date,
                duration_months=duration_months,
                lessons_per_week=lessons_per_week,
            )
        elif getattr(self.instance, "pk", None):
            # Eski datani tasodifan o'chirib yubormaslik uchun.
            cleaned["estimated_end_date"] = self.instance.estimated_end_date

        return cleaned


class LangGroupForm(GroupForm):
    category = forms.ChoiceField(choices=Group.CATEGORY_CHOICES, widget=forms.HiddenInput(), initial=Group.LANG, required=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.category = Group.LANG  # <— Eng muhim qator
        obj.kurs_narxi = obj.kurs_narxi or 500000
        obj.oqituvchi_foiz = obj.oqituvchi_foiz or 40
        obj.oy_dars_soni = obj.oy_dars_soni or 12
        if commit:
            obj.save()
        return obj

class ITGroupForm(GroupForm):
    category = forms.ChoiceField(choices=Group.CATEGORY_CHOICES, widget=forms.HiddenInput(), initial=Group.IT, required=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.category = Group.IT  # <— Eng muhim qator
        obj.kurs_narxi = obj.kurs_narxi or 500000
        obj.oqituvchi_foiz = obj.oqituvchi_foiz or 40
        obj.oy_dars_soni = obj.oy_dars_soni or 12
        if commit:
            obj.save()
        return obj



class AddExistingStudentForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=User.objects.filter(role="student").order_by("ism", "familya"),
        label="Mavjud o‘quvchi",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class AddNewStudentForm(forms.ModelForm):
    # Login — bizda User.email (login) sifatida saqlanadi
    email = forms.CharField(label="Login", widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(label="Parol", widget=forms.PasswordInput(attrs={"class": "form-control"}))

    class Meta:
        model = User
        fields = ["ism", "familya", "telefon1", "telefon2", "email", "password"]
        labels = {
            "ism": "Ism",
            "familya": "Familya",
            "telefon1": "Telefon1",
            "telefon2": "Telefon2",
        }
        widgets = {
            "ism": forms.TextInput(attrs={"class": "form-control"}),
            "familya": forms.TextInput(attrs={"class": "form-control"}),
            "telefon1": forms.TextInput(attrs={"class": "form-control"}),
            "telefon2": forms.TextInput(attrs={"class": "form-control"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "student"
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
    

    
class EnrollmentExistingForm(forms.Form):
    """
    Mavjud o‘quvchini tanlab guruhga qo‘shish.
    """
    student = forms.ModelChoiceField(
        label="O‘quvchi", queryset=User.objects.none()
    )

    def __init__(self, *args, **kwargs):
        group: Group = kwargs.pop("group")
        super().__init__(*args, **kwargs)
        in_group_ids = group.enrollments.values_list("student_id", flat=True)
        self.fields["student"].queryset = (
            User.objects.filter(role="student")
            .exclude(id__in=list(in_group_ids))
            .order_by("ism", "familya")
        )
        self.group = group

    def save(self):
        # Use all_objects to handle soft-deleted enrollments
        enr, created = Enrollment.all_objects.get_or_create(
            group=self.group, student=self.cleaned_data["student"]
        )
        if not created and enr.is_deleted:
            enr.restore()
        enr.is_active = True
        enr.save()
        return enr


class EnrollmentCreateStudentForm(forms.Form):
    """
    Yangi o‘quvchini yaratib shu zahoti guruhga qo‘shish.
    """
    ism = forms.CharField(label="Ism", max_length=150)
    familya = forms.CharField(label="Familya", max_length=150, required=False)
    telefon1 = forms.CharField(label="Telefon1", required=False)
    telefon2 = forms.CharField(label="Telefon2", required=False)
    email = forms.CharField(
        label="Login (email/username)",
        help_text="Masalan: you@example.com yoki amirxon2005",
    )
    gmail = forms.EmailField(label="Gmail", required=False)
    password1 = forms.CharField(
        label="Parol", widget=forms.PasswordInput, help_text="Kamida 6 ta belgi"
    )
    password2 = forms.CharField(
        label="Parol (tasdiqlash)", widget=forms.PasswordInput
    )

    def __init__(self, *args, **kwargs):
        self.group: Group = kwargs.pop("group")
        super().__init__(*args, **kwargs)

    def clean_email(self):
        login = self.cleaned_data["email"].strip()
        User = get_user_model()
        if User.objects.filter(email__iexact=login).exists():
            raise forms.ValidationError("Bu login allaqachon mavjud.")
        return login

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and len(p1) < 6:
            self.add_error("password1", "Parol uzunligi kamida 6 bo‘lsin.")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Parollar mos kelmadi.")
        return data

    def save(self):
        User = get_user_model()
        u = User(
            ism=self.cleaned_data["ism"],
            familya=self.cleaned_data.get("familya"),
            telefon1=self.cleaned_data.get("telefon1"),
            telefon2=self.cleaned_data.get("telefon2"),
            email=self.cleaned_data["email"],
            gmail=self.cleaned_data.get("gmail"),
            role="student",
        )
        u.set_password(self.cleaned_data["password1"])
        u.save()
        # Use all_objects to handle soft-deleted enrollments
        enr, created = Enrollment.all_objects.get_or_create(
            group=self.group, student=u
        )
        if not created and enr.is_deleted:
            enr.restore()
        enr.is_active = True
        enr.save()
        return u, enr

class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ('center','nom','izoh','oqituvchi')

class EnrollmentCreateForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ('group','student','kurs_narhi')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = User.objects.filter(role='student').order_by('ism','familya')
        if user and getattr(user, 'role', None) == 'teacher':
            self.fields['group'].queryset = Group.objects.filter(oqituvchi=user)
        else:
            self.fields['group'].queryset = Group.objects.all().order_by('nom')



class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'kurs_narhi', 'oqituvchi_foiz']
        labels = {
            'student': "O‘quvchini tanlang",
            'kurs_narhi': "Kurs narxi (so‘mda)",
            'oqituvchi_foiz': "O‘qituvchining ulushi (%)",
        }
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'kurs_narhi': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 600000'}),
            'oqituvchi_foiz': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 40'}),
        }


class CenterExamSettingForm(forms.ModelForm):
    class Meta:
        model = CenterExamSetting
        fields = [
            "exam_system_enabled",
            "exam_every_n_lessons",
            "passing_score_percent",
            "exam_file_upload_enabled",
            "exam_result_required",
            "optional_task_upload_prompt_enabled",
        ]
        labels = {
            "exam_system_enabled": "Imtihon tizimi yoqilgan",
            "exam_every_n_lessons": "Har N-darsda imtihon",
            "passing_score_percent": "O‘tish foizi (%)",
            "exam_file_upload_enabled": "Fayl yuklashga ruxsat",
            "exam_result_required": "Imtihon natijasi majburiy",
            "optional_task_upload_prompt_enabled": "Ixtiyoriy topshiriq prompt yoqilgan",
        }

    def clean_exam_every_n_lessons(self):
        val = self.cleaned_data.get("exam_every_n_lessons") or 0
        if val < 1:
            raise forms.ValidationError("N dars qiymati 1 dan kichik bo‘lishi mumkin emas.")
        return val

    def clean_passing_score_percent(self):
        val = self.cleaned_data.get("passing_score_percent") or 0
        if val < 1 or val > 100:
            raise forms.ValidationError("O‘tish foizi 1-100 oralig‘ida bo‘lishi kerak.")
        return val

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

class ExamResultRowForm(forms.Form):
    score = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=7)
    percent = forms.DecimalField(required=False, min_value=0, max_value=100, decimal_places=2, max_digits=5)
    teacher_comment = forms.CharField(required=False, widget=forms.Textarea)
    assignment_description = forms.CharField(required=False, widget=forms.Textarea)
    absent_in_exam = forms.BooleanField(required=False)
    retake_recommended = forms.BooleanField(required=False)

    def __init__(self, *args, require_result=False, **kwargs):
        self.require_result = bool(require_result)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        score = cleaned.get("score")
        percent = cleaned.get("percent")
        absent = bool(cleaned.get("absent_in_exam"))

        if self.require_result and not absent and score is None and percent is None:
            raise forms.ValidationError(
                "Ball yoki foiz kiriting, yoki o‘quvchi imtihonda qatnashmaganini belgilang."
            )
        return cleaned


class ExamResultFollowUpForm(forms.ModelForm):
    class Meta:
        model = ExamResult
        fields = ["follow_up_status", "follow_up_note"]
        labels = {
            "follow_up_status": "Nazorat holati",
            "follow_up_note": "Izoh",
        }
        widgets = {
            "follow_up_status": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "follow_up_note": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "placeholder": "Izoh"}
            ),
        }


class CertificateTemplateForm(forms.ModelForm):
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    MAX_SIZE_BYTES = 10 * 1024 * 1024

    class Meta:
        model = CertificateTemplate
        fields = ["name", "template_type", "template_file", "is_active", "note"]
        labels = {
            "name": "Shablon nomi",
            "template_type": "Shablon turi",
            "template_file": "Shablon fayli",
            "is_active": "Faol shablon",
            "note": "Izoh",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "template_type": forms.Select(attrs={"class": "form-select"}),
            "template_file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ixtiyoriy izoh"}),
        }

    def clean_template_file(self):
        f = self.cleaned_data.get("template_file")
        if not f:
            return f
        ext = Path(getattr(f, "name", "")).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Faqat rasm formatlari ruxsat etiladi: png, jpg, jpeg, webp.")
        if getattr(f, "size", 0) > self.MAX_SIZE_BYTES:
            raise forms.ValidationError("Shablon fayli 10MB dan katta bo‘lishi mumkin emas.")
        return f


class CertificateIssueForm(forms.Form):
    certificate_type = forms.ChoiceField(
        choices=CertificateTemplate.TYPE_CHOICES,
        initial=CertificateTemplate.TYPE_CERTIFICATE,
    )
    note = forms.CharField(required=False, widget=forms.TextInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificate_type"].widget.attrs.update({"class": "form-select form-select-sm"})
        self.fields["note"].widget.attrs.update(
            {"class": "form-control form-control-sm", "placeholder": "Ixtiyoriy izoh"}
        )
