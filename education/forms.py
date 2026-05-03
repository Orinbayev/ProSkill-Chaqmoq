from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import CenterExpense, CertificateTemplate, CenterExamSetting, Enrollment, ExamResult, Group

User = get_user_model()

class GroupForm(forms.ModelForm):
    SCHEDULE_MODE_CHOICES = (
        ("", "Keyin kiritaman"),
        ("odd", "Toq kunlari"),
        ("even", "Juft kunlari"),
    )

    schedule_mode = forms.ChoiceField(
        choices=SCHEDULE_MODE_CHOICES,
        required=False,
        label="Dars kunlari",
    )
    schedule_start_time = forms.TimeField(
        required=False,
        label="Boshlanish vaqti",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    schedule_end_time = forms.TimeField(
        required=False,
        label="Tugash vaqti",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    schedule_room = forms.CharField(
        required=False,
        label="Xona",
        max_length=60,
    )

    # ── Support teacher (markaz darajasida feature flag bilan yoqiladi) ──
    use_support = forms.BooleanField(
        required=False,
        label="Support qo'shish",
        help_text="Yoqsangiz, ushbu guruhga yordamchi xodim biriktiriladi va davomatdan foiz oladi.",
    )

    class Meta:
        model = Group
        fields = [
            "nom",
            "oqituvchi",
            "kurs_narxi",
            "max_students",
            "course_start_date",
            "duration_months",
            "estimated_end_date",
            "support_teacher",
            "support_foiz",
        ]
        labels = {
            "nom": "Guruh nomi",
            "oqituvchi": "O‘qituvchi",
            "kurs_narxi": "Kurs narxi (so‘m)",
            "max_students": "Maksimal o'quvchi soni",
            "course_start_date": "Boshlanish sanasi",
            "duration_months": "Davomiyligi (oy)",
            "estimated_end_date": "Tugash sanasi",
            "support_teacher": "Support xodimi",
            "support_foiz": "Support foizi (%)",
        }
        widgets = {
            "max_students": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "course_start_date": forms.DateInput(attrs={"type": "date"}),
            "duration_months": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "estimated_end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "readonly": "readonly",
                }
            ),
            "support_foiz": forms.NumberInput(attrs={"min": "0", "max": "100", "step": "1"}),
        }

    def __init__(self, *args, **kwargs):
        center = kwargs.pop("center", None)
        self.center = center
        super().__init__(*args, **kwargs)

        # Filter teachers by center
        if "oqituvchi" in self.fields:
            teach_qs = User.objects.filter(role="teacher")
            if center:
                teach_qs = teach_qs.filter(center=center)
            self.fields["oqituvchi"].queryset = teach_qs.order_by("ism", "familya")
            self.fields["oqituvchi"].empty_label = "O'qituvchini tanlang"
            self.fields["oqituvchi"].label_from_instance = lambda obj: f"{obj.ism or ''} {obj.familya or ''}".strip() or obj.email

        # ── Support teacher field'larini sozlash ──
        # Faqat markazda feature yoqilgan bo'lsa ko'rinadi.
        from education.services.support_teacher import (
            is_support_enabled,
            staff_queryset_for_support_dropdown,
        )

        self.support_enabled_for_center = is_support_enabled(center)

        if self.support_enabled_for_center:
            # Support dropdown — barcha xodimlar (teacher, manager, admin, ...).
            qs = staff_queryset_for_support_dropdown(center)
            self.fields["support_teacher"].queryset = qs
            self.fields["support_teacher"].required = False
            self.fields["support_teacher"].empty_label = "Support tanlang (ixtiyoriy)"
            self.fields["support_teacher"].label_from_instance = (
                lambda obj: (
                    f"{(obj.ism or '').strip()} {(obj.familya or '').strip()}".strip()
                    or obj.email
                )
                + f" ({obj.get_role_display() if hasattr(obj, 'get_role_display') else obj.role})"
            )
            self.fields["support_foiz"].required = False

            # Mavjud guruhda support biriktirilgan bo'lsa, checkbox yoqilgan
            instance = getattr(self, "instance", None)
            has_support_already = bool(
                instance and instance.pk and instance.support_teacher_id
                and (instance.support_foiz or 0) > 0
            )
            self.fields["use_support"].initial = has_support_already
        else:
            # Feature yo'q — formdan butunlay o'chiramiz.
            self.fields.pop("support_teacher", None)
            self.fields.pop("support_foiz", None)
            self.fields.pop("use_support", None)

        for f in [
            "kurs_narxi",
            "max_students",
            "course_start_date",
            "duration_months",
            "estimated_end_date",
        ]:
            if f in self.fields:
                self.fields[f].required = False

        # Default qiymatlar
        if "kurs_narxi" in self.fields: self.fields["kurs_narxi"].initial = 500000
        if "max_students" in self.fields:
            self.fields["max_students"].initial = self.initial.get("max_students") or getattr(self.instance, "max_students", None) or 15
        if (
            "course_start_date" in self.fields
            and not self.is_bound
            and not self.initial.get("course_start_date")
        ):
            self.fields["course_start_date"].initial = timezone.localdate()
        if "kurs_narxi" in self.fields:
            self.fields["kurs_narxi"].widget = forms.HiddenInput()
        if "duration_months" in self.fields:
            self.fields["duration_months"].widget.attrs.update(
                {"placeholder": "Masalan: 2"}
            )
        if "max_students" in self.fields:
            self.fields["max_students"].widget.attrs.update(
                {"placeholder": "Masalan: 15"}
            )
        if "estimated_end_date" in self.fields:
            self.fields["estimated_end_date"].widget.attrs.update(
                {
                    "tabindex": "-1",
                    "data-autocalculated": "true",
                }
            )

        self.fields["schedule_mode"].widget.attrs.update({"class": "schedule-mode-select"})
        self.fields["schedule_start_time"].widget.attrs.update({"placeholder": "10:00"})
        self.fields["schedule_end_time"].widget.attrs.update({"placeholder": "12:00"})
        self.fields["schedule_room"].widget.attrs.update({"placeholder": "Masalan: 2-kabinet"})

        if getattr(self.instance, "pk", None):
            from education.services.group_schedule_service import infer_simple_schedule

            schedule_info = infer_simple_schedule(self.instance)
            self.fields["schedule_mode"].initial = schedule_info["mode"] if schedule_info["mode"] in {"odd", "even"} else ""
            self.fields["schedule_start_time"].initial = schedule_info["start_time"]
            self.fields["schedule_end_time"].initial = schedule_info["end_time"]
            self.fields["schedule_room"].initial = schedule_info["room"]

    def clean(self):
        cleaned = super().clean()

        teacher = cleaned.get("oqituvchi")
        schedule_mode = cleaned.get("schedule_mode")
        schedule_start_time = cleaned.get("schedule_start_time")
        schedule_end_time = cleaned.get("schedule_end_time")
        course_start_date = cleaned.get("course_start_date")
        duration_months = cleaned.get("duration_months")

        from education.services.group_schedule_service import calculate_estimated_end_date

        if schedule_mode in {"odd", "even"} and not schedule_start_time:
            self.add_error("schedule_start_time", "Boshlanish vaqti majburiy.")
        if schedule_end_time and schedule_start_time and schedule_end_time <= schedule_start_time:
            self.add_error("schedule_end_time", "Tugash vaqti boshlanishdan keyin bo'lishi kerak.")

        cleaned["estimated_end_date"] = calculate_estimated_end_date(
            course_start_date=course_start_date,
            duration_months=duration_months,
            lessons_per_week=3,
        )

        if teacher and schedule_mode in {"odd", "even"} and schedule_start_time and self.center:
            from education.services.group_schedule_service import EVEN_WEEKDAYS, ODD_WEEKDAYS
            from education.services.hr import teacher_is_available

            weekdays = ODD_WEEKDAYS if schedule_mode == "odd" else EVEN_WEEKDAYS
            if not teacher_is_available(
                teacher,
                center=self.center,
                weekdays=weekdays,
                start_time=schedule_start_time,
                end_time=schedule_end_time,
                exclude_group_id=getattr(self.instance, "pk", None),
            ):
                self.add_error("oqituvchi", "Tanlangan kun va vaqtda bu o'qituvchi band.")

        # ── Support teacher validatsiyasi ──
        if getattr(self, "support_enabled_for_center", False):
            use_support = cleaned.get("use_support")
            support_teacher = cleaned.get("support_teacher")
            support_foiz = cleaned.get("support_foiz") or 0

            if use_support:
                if not support_teacher:
                    self.add_error("support_teacher", "Support xodimini tanlang yoki 'Support qo'shish' belgisini olib tashlang.")
                if support_foiz <= 0:
                    self.add_error("support_foiz", "Support foizi 0 dan katta bo'lsin.")
                if support_foiz > 100:
                    self.add_error("support_foiz", "Support foizi 100 dan oshmasin.")
                if support_teacher and teacher and support_teacher.id == teacher.id:
                    self.add_error("support_teacher", "Support va asosiy o'qituvchi bir kishi bo'la olmaydi.")

                # Asosiy o'qituvchi foizi + support foizi <= 100 bo'lishi kerak.
                main_foiz = 0
                if teacher:
                    main_foiz = int(getattr(teacher, "oqituvchi_foizi", 0) or 0)
                if main_foiz + support_foiz > 100:
                    self.add_error(
                        "support_foiz",
                        f"O'qituvchi ({main_foiz}%) + Support ({support_foiz}%) = {main_foiz + support_foiz}% — 100% dan oshmasin."
                    )
            else:
                # Use support yoqilmagan — bo'sh qoldiramiz.
                cleaned["support_teacher"] = None
                cleaned["support_foiz"] = 0

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.estimated_end_date_manual = False
        obj.kurs_narxi = obj.kurs_narxi or 500000
        obj.max_students = obj.max_students or 15

        # Support teacher: feature yoqilgan markazlarda — clean'dan kelgan qiymat
        if getattr(self, "support_enabled_for_center", False):
            use_support = self.cleaned_data.get("use_support")
            if use_support:
                obj.support_teacher = self.cleaned_data.get("support_teacher")
                obj.support_foiz = int(self.cleaned_data.get("support_foiz") or 0)
            else:
                obj.support_teacher = None
                obj.support_foiz = 0
        # Aks holda: support_teacher / support_foiz formada yo'q,
        # ModelForm o'zgartirmaydi — eski qiymat saqlanadi.

        if commit:
            obj.save()
        return obj


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


class CenterExpenseForm(forms.ModelForm):
    class Meta:
        model = CenterExpense
        fields = ["category", "amount", "description", "date"]
        labels = {
            "category": "Kategoriya",
            "amount": "Summa (so'm)",
            "description": "Izoh",
            "date": "Sana",
        }
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1000"}),
            "description": forms.TextInput(attrs={"class": "form-control", "maxlength": "255"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and "date" in self.fields:
            self.fields["date"].initial = timezone.localdate()



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


class StudentGroupTransferForm(forms.Form):
    new_group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        label="Yangi guruh",
        empty_label="Yangi guruhni tanlang",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    transfer_date = forms.DateField(
        label="Ko'chirish sanasi",
        required=False,
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    reason = forms.CharField(
        label="Ko'chirish sababi (ixtiyoriy)",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Masalan: jadval mos kelmadi"}),
    )

    def __init__(self, *args, **kwargs):
        self.old_group = kwargs.pop("old_group")
        self.center = kwargs.pop("center", None) or self.old_group.center
        super().__init__(*args, **kwargs)
        self.fields["new_group"].queryset = (
            Group.objects
            .filter(center=self.center, is_archived=False)
            .exclude(pk=self.old_group.pk)
            .order_by("nom")
        )

    def clean_new_group(self):
        new_group = self.cleaned_data["new_group"]
        if new_group.pk == self.old_group.pk:
            raise forms.ValidationError("Yangi guruh eski guruh bilan bir xil bo'lishi mumkin emas.")
        if new_group.center_id != self.old_group.center_id:
            raise forms.ValidationError("Boshqa o'quv markaz guruhiga ko'chirish mumkin emas.")
        return new_group

    def clean_transfer_date(self):
        return self.cleaned_data.get("transfer_date") or timezone.localdate()


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
        fields = ('group', 'student', 'kurs_narhi', 'student_payable_amount', 'joined_at', 'lesson_pattern')
        widgets = {
            "joined_at": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "lesson_pattern": forms.RadioSelect(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = User.objects.filter(role='student').order_by('ism','familya')
        if user and getattr(user, 'role', None) == 'teacher':
            self.fields['group'].queryset = Group.objects.filter(oqituvchi=user)
        else:
            self.fields['group'].queryset = Group.objects.all().order_by('nom')

    def clean(self):
        cleaned_data = super().clean()
        kurs_narhi = int(cleaned_data.get("kurs_narhi") or 0)
        student_payable_amount = cleaned_data.get("student_payable_amount")
        if student_payable_amount is not None and student_payable_amount > kurs_narhi:
            self.add_error("student_payable_amount", "O'quvchidan olinadigan summa kurs narxidan katta bo'lishi mumkin emas.")
        return cleaned_data



class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'kurs_narhi', 'student_payable_amount', 'oqituvchi_foiz', 'joined_at', 'lesson_pattern']
        labels = {
            'student': "O‘quvchini tanlang",
            'kurs_narhi': "Kurs narxi (so‘mda)",
            'student_payable_amount': "O‘quvchidan olinadigan summa",
            'oqituvchi_foiz': "O‘qituvchining ulushi (%)",
            'joined_at': "Boshlanish sanasi",
            'lesson_pattern': "Dars patterni",
        }
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'kurs_narhi': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 600000'}),
            'student_payable_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Bo‘sh qoldirilsa to‘liq kurs narxi ishlatiladi'}),
            'oqituvchi_foiz': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 40'}),
            'joined_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lesson_pattern': forms.RadioSelect(),
        }

    def clean(self):
        cleaned_data = super().clean()
        kurs_narhi = int(cleaned_data.get("kurs_narhi") or 0)
        student_payable_amount = cleaned_data.get("student_payable_amount")
        if student_payable_amount is not None and student_payable_amount > kurs_narhi:
            self.add_error("student_payable_amount", "O'quvchidan olinadigan summa kurs narxidan katta bo'lishi mumkin emas.")
        return cleaned_data


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
