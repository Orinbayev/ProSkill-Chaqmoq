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
    email = forms.CharField(label="Login")
    telefon1 = forms.CharField(label="Telefon nomer", required=False)
    telefon2 = forms.CharField(label="Uyida telefon nomeri", required=False)
    center = forms.ModelChoiceField(
        queryset=Center.objects.all(),
        empty_label="---------",
        required=False,
        label="Center"
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Roli")
    password = forms.CharField(label="Parol", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = [
            "ism", "familya",
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
            "telefon1": forms.TextInput(attrs={
                "placeholder": "+998XXXXXXXXX",
                "class": "form-control uniform-input",
                "id": "id_telefon1",
                "oninput": "validatePhone(this)",
                "maxlength": "13"
            }),
            "telefon2": forms.TextInput(attrs={
                "placeholder": "+998XXXXXXXXX",
                "class": "form-control uniform-input",
                "id": "id_telefon2",
                "oninput": "validatePhone(this)",
                "maxlength": "13"
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
        for name in ["center", "role"]:
            self.fields[name].widget.attrs.setdefault("class", "form-select uniform-input")

    def clean_email(self):
        login = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=login).exists():
            raise forms.ValidationError("Bu login allaqachon mavjud.")
        return login

    def save(self, commit=True):
        data = self.cleaned_data
        user = User(
            ism=data.get("ism"),
            familya=data.get("familya"),
            email=data.get("email"),
            telefon1=data.get("telefon1"),
            telefon2=data.get("telefon2"),
            center=data.get("center"),
            role=data.get("role"),
            oqituvchi_foizi=data.get("oqituvchi_foizi") or 40
        )
        if user.role == "manager":
            user.is_staff = True
        user.set_password(data.get("password"))
        if commit:
            user.save()
        return user

class TeacherForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['ism', 'familya', 'email', 'telefon1', 'center', 'oqituvchi_foizi']
