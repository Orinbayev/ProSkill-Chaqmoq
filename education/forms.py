from django import forms
from django.contrib.auth import get_user_model
from .models import Enrollment, Group

User = get_user_model()

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = [
            "category_obj", "center", "nom", "izoh", "oqituvchi",
            "kurs_narxi", "oqituvchi_foiz", "oy_dars_soni"
        ]
        labels = {
            "nom": "Guruh nomi",
            "oqituvchi": "O‘qituvchi",
            "kurs_narxi": "Kurs narxi (so‘m)",
            "oqituvchi_foiz": "O‘qituvchi foizi (%)",
            "oy_dars_soni": "Bir oyda darslar soni",
            "izoh": "Izoh",
            "center": "Markaz",
            "category_obj": "Bo‘lim",
        }

    def __init__(self, *args, **kwargs):
        center = kwargs.pop("center", None)
        super().__init__(*args, **kwargs)
        
        # Filter teachers by center
        if "oqituvchi" in self.fields:
            teach_qs = User.objects.filter(role="teacher")
            if center:
                teach_qs = teach_qs.filter(center=center)
            self.fields["oqituvchi"].queryset = teach_qs.order_by("ism", "familya")

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
        for f in ["kurs_narxi", "oqituvchi_foiz", "oy_dars_soni", "category_obj", "center"]:
            if f in self.fields:
                self.fields[f].required = False

        # Default qiymatlar
        if "kurs_narxi" in self.fields: self.fields["kurs_narxi"].initial = 500000
        if "oqituvchi_foiz" in self.fields: self.fields["oqituvchi_foiz"].initial = 40
        if "oy_dars_soni" in self.fields: self.fields["oy_dars_soni"].initial = 12


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
