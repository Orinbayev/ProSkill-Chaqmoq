from django import forms
from django.contrib.auth import get_user_model
from accounts.models import Center

User = get_user_model()

ROLE_CHOICES = (
    ("student", "O‘quvchi"),
    ("teacher", "O‘qituvchi"),
    ("manager", "Manager"),
)

class AddUserForm(forms.ModelForm):

    center = forms.ModelChoiceField(
        queryset=Center.objects.all(),
        empty_label="---------",
        required=False,
        label="Center"
    )

    class Meta:
        model = User
        fields = [
            "ism", "familya", "otchestvo",
            "telefon1", "telefon2",
            "center", "role",
            "email", "password",
            "oqituvchi_foizi",
        ]

        widgets = {
            "ism": forms.TextInput(attrs={
                "placeholder": "Ism",
                "class": "form-control uniform-input",
                "id": "id_ism"
            }),
            "familya": forms.TextInput(attrs={
                "placeholder": "Familya",
                "class": "form-control uniform-input",
                "id": "id_familya"
            }),
            "otchestvo": forms.TextInput(attrs={
                "placeholder": "Otasining ismi (ixtiyoriy)",
                "class": "form-control uniform-input",
                "id": "id_otchestvo"
            }),
            "telefon1": forms.TextInput(attrs={
                "placeholder": "+998XXXXXXXXX",
                "class": "form-control uniform-input"
            }),
            "telefon2": forms.TextInput(attrs={
                "placeholder": "+998XXXXXXXXX",
                "class": "form-control uniform-input"
            }),
            "email": forms.TextInput(attrs={
                "placeholder": "Login (email)",
                "class": "form-control uniform-input",
                "id": "id_email"
            }),
            "password": forms.PasswordInput(attrs={
                "placeholder": "Parol",
                "class": "form-control uniform-input",
                "id": "id_password"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 🔥 O‘QITUVCHI FOIZI → MAJBURIY EMAS
        self.fields["oqituvchi_foizi"].required = False

    def save(self, commit=True):
        data = self.cleaned_data

        user = User(
            ism=data["ism"],
            familya=data["familya"],
            otchestvo=data.get("otchestvo"),
            email=data["email"],
            telefon1=data["telefon1"],
            telefon2=data.get("telefon2"),
            center=data.get("center"),
            role=data["role"],
        )

        # 🔥 Agar teacher bo‘lsa → foiz bo‘lsin
        if user.role == "teacher":
            user.oqituvchi_foizi = data.get("oqituvchi_foizi") or 40

        # 🔥 Student bo‘lsa → FORMADAN FOIZ KELMASIN
        else:
            user.oqituvchi_foizi = 0

        # manager → admin huquq
        if user.role == "manager":
            user.is_staff = True

        # Parol
        user.set_password(data["password"])

        if commit:
            user.save()

        return user


class TeacherForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['ism', 'familya', 'otchestvo', 'email', 'telefon1', 'center', 'oqituvchi_foizi']
