# accounts/forms.py
from django import forms
from django.contrib.auth import get_user_model
from accounts.models import Center
from django.apps import apps

User = get_user_model()
Group = apps.get_model('education', 'Group')

ROLE_CHOICES = (
    ("student", "O‘quvchi"),
    ("teacher", "O‘qituvchi"),
    ("manager", "Manager"),
    ("parent", "Ota-ona"),
)

class AddUserForm(forms.ModelForm):
    center = forms.ModelChoiceField(
        queryset=Center.objects.all(),
        empty_label="---------",
        required=False,
        label="Center"
    )
    group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        required=False,
        label="Guruhni tanlang"
    )
    kurs_narhi = forms.IntegerField(required=False, label="Kurs narxi")

    class Meta:
        model = User
        fields = [
            "ism", "familya", "otchestvo",
            "telefon1", "telefon2",
            "center", "role",
            "email", "password",
            "oqituvchi_foizi",
            "birth_date", "gender", "passport_id", "jshr", "address",
        ]
        widgets = {
            "ism": forms.TextInput(attrs={"placeholder": "Ism", "class": "form-control uniform-input", "id": "id_ism"}),
            "familya": forms.TextInput(attrs={"placeholder": "Familya", "class": "form-control uniform-input", "id": "id_familya"}),
            "otchestvo": forms.TextInput(attrs={"placeholder": "Otasining ismi (ixtiyoriy)", "class": "form-control uniform-input", "id": "id_otchestvo"}),
            "telefon1": forms.TextInput(attrs={"placeholder": "+998XXXXXXXXX", "class": "form-control uniform-input"}),
            "telefon2": forms.TextInput(attrs={"placeholder": "+998XXXXXXXXX", "class": "form-control uniform-input"}),
            "email": forms.TextInput(attrs={"placeholder": "Login (email)", "class": "form-control uniform-input", "id": "id_email"}),
            "password": forms.PasswordInput(attrs={"placeholder": "Parol", "class": "form-control uniform-input", "id": "id_password"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "form-control uniform-input"}),
            "gender": forms.RadioSelect(attrs={"class": "gender-radio"}), 
            "passport_id": forms.TextInput(attrs={"placeholder": "AB1234567", "class": "form-control uniform-input"}),
            "jshr": forms.TextInput(attrs={"placeholder": "14 ta raqam", "class": "form-control uniform-input", "maxlength": "14"}),
            "address": forms.Textarea(attrs={"placeholder": "Manzil...", "class": "form-control uniform-input", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        self.fields["oqituvchi_foizi"].required = False

        u = getattr(self.request, "user", None) if self.request else None

        # ✅ 1) Active center: request.center -> user.center -> POSTed center -> initial center
        active_center = None
        if self.request:
            active_center = getattr(self.request, "center", None)

        if not active_center and u and getattr(u, "center", None):
            active_center = u.center

        # ✅ POST/GET dan center tanlangan bo'lsa ham ishlasin
        center_id = (self.data.get("center") or self.initial.get("center"))
        if center_id:
            try:
                active_center = Center.objects.get(id=center_id)
            except Center.DoesNotExist:
                pass

        # ✅ 2) Center fieldni cheklash (superuser bo'lsa ham)
        if active_center and "center" in self.fields:
            self.fields["center"].queryset = Center.objects.filter(id=active_center.id)
            self.fields["center"].initial = active_center
            self.fields["center"].required = True
            self.fields["center"].empty_label = None

        # ✅ 3) Group field – faqat shu markaz guruhlari chiqsin
        if "group" in self.fields:
            if active_center:
                self.fields["group"].queryset = Group.objects.filter(
                    center=active_center,
                    is_archived=False
                ).order_by("nom")
            else:
                self.fields["group"].queryset = Group.objects.none()



    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        group = cleaned_data.get("group")
        center = cleaned_data.get("center")
        
        if role == "student":
            if not cleaned_data.get("birth_date"):
                self.add_error("birth_date", "O‘quvchi uchun tug‘ilgan sana majburiy!")
            if not cleaned_data.get("gender"):
                self.add_error("gender", "O‘quvchi uchun jins tanlanishi shart!")
            
            # Security: Verify group center matches user center
            if group and center and group.center_id != center.id:
                raise forms.ValidationError("Tanlangan guruh ushbu markazga tegishli emas!")
        
        return cleaned_data

    def save(self, commit=True):
        data = self.cleaned_data
        request = self.request
        req_user = getattr(request, "user", None) if request else None

        center_to_set = None
        if req_user and req_user.is_superuser:
            center_to_set = getattr(request, "center", None) or data.get("center")
        elif req_user and getattr(req_user, "role", None) in ("director", "manager"):
            center_to_set = getattr(req_user, "center", None)

        if not center_to_set and req_user and not req_user.is_superuser:
            raise forms.ValidationError("Active center topilmadi.")

        user = super().save(commit=False)
        user.center = center_to_set
        user.is_staff = (user.role in ("manager", "director"))
        
        if user.role == "teacher":
            user.oqituvchi_foizi = data.get("oqituvchi_foizi") or 40
        else:
            user.oqituvchi_foizi = 0

        user.set_password(data["password"])

        if commit:
            user.save()
            
            # Handle Enrollment
            group = data.get("group")
            if user.role == "student" and group:
                from education.models import Enrollment
                Enrollment.objects.get_or_create(
                    group=group,
                    student=user,
                    defaults={
                        'kurs_narhi': data.get("kurs_narhi") or group.kurs_narxi,
                        'oqituvchi_foiz': group.oqituvchi_foiz,
                        'center': group.center
                    }
                )

        return user


class TeacherForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['ism', 'familya', 'otchestvo', 'email', 'telefon1', 'center', 'oqituvchi_foizi', 'passport_id', 'jshr', 'birth_date', 'gender', 'telefon2']


class CenterAdminForm(forms.ModelForm):
    """Super Admin uchun markazni yaratish/tahrirlash formasi"""
    class Meta:
        model = Center
        fields = [
            "name", "address", "plan", 
            "max_users", "max_groups", "max_students", 
            "status", "features"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "plan": forms.Select(attrs={"class": "form-select"}),
            "features": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": '{"leads": true}'}),
        }
        labels = {
            "name": "Markaz Nomi",
            "address": "Manzil",
            "plan": "Tarif Rejasi",
            "features": "Qo‘shimcha Imkoniyatlar (JSON)",
        }


class DirectorCreationForm(forms.ModelForm):
    """Markaz bilan birga director yaratish formasi"""
    password = forms.CharField(label="Parol", widget=forms.PasswordInput(attrs={"class": "form-control"}))
    
    class Meta:
        model = User
        fields = ["ism", "familya", "email", "telefon1"]
        widgets = {
            "ism": forms.TextInput(attrs={"class": "form-control", "placeholder": "Director Ismi"}),
            "familya": forms.TextInput(attrs={"class": "form-control", "placeholder": "Familiyasi"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Login (Email)"}),
            "telefon1": forms.TextInput(attrs={"class": "form-control", "placeholder": "+998..."}),
        }

    def save(self, center, commit=True):
        user = super().save(commit=False)
        user.role = "director"
        user.center = center
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ParentForm(forms.ModelForm):
    # Field to select children (students) - reverted to multiple selection
    children_ids = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role="student"),
        widget=forms.SelectMultiple(attrs={"class": "form-control select2", "id": "id_children_ids"}),
        required=True,
        label="Farzandlarini tanlang"
    )

    class Meta:
        model = User
        fields = ["ism", "familya", "telefon1", "telefon2", "email", "password"]
        widgets = {
            "ism": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "Ism", "id": "id_ism"}),
            "familya": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "Familya", "id": "id_familya"}),
            "telefon1": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "+998...", "id": "id_telefon1"}),
            "telefon2": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "+998...", "id": "id_telefon2"}),
            "email": forms.EmailInput(attrs={"class": "form-control uniform-input", "placeholder": "Login (email)", "id": "id_email"}),
            "password": forms.PasswordInput(attrs={"class": "form-control uniform-input", "placeholder": "Parol", "id": "id_password"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if self.request:
            center = getattr(self.request, "center", None) or getattr(self.request.user, "center", None)
            if center:
                self.fields["children_ids"].queryset = User.objects.filter(role="student", center=center, is_archived=False)
        
        if self.instance and self.instance.pk:
            self.fields["children_ids"].initial = self.instance.children.all()
            self.fields["password"].required = False # Password not required on edit

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "parent"
        if self.request:
             user.center = getattr(self.request, "center", None) or getattr(self.request.user, "center", None)
        
        pw = self.cleaned_data.get("password")
        if pw:
            user.set_password(pw)
        
        if commit:
            user.save()
            # Set the multiple selected children
            user.children.set(self.cleaned_data.get("children_ids"))
        return user
