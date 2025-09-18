from django import forms
from django.contrib.auth import get_user_model
from accounts.models import Center

User = get_user_model()

ROLE_CHOICES = (
    ("teacher", "O‘qituvchi"),
    ("student", "O‘quvchi"),
    ("manager", "Manager"),
)

class AddUserForm(forms.ModelForm):
    # LOGIN: tizimga kirish uchun ishlatiladi (User.email ga yoziladi)
    email = forms.CharField(label="Login")
    # “Gmail” ni olib tashladik
    telefon1 = forms.CharField(label="Telefon1", required=False)
    telefon2 = forms.CharField(label="Telefon2", required=False)
    center = forms.ModelChoiceField(
        queryset=Center.objects.all(), empty_label="---------", required=False, label="Center"
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Roli")
    password = forms.CharField(label="Parol", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = [
            "ism", "familya",
            "telefon1", "telefon2",
            "center", "role",
            "email", "password",   # Login va Parol oxirida
        ]
        widgets = {
            "ism": forms.TextInput(attrs={"placeholder": "Ism"}),
            "familya": forms.TextInput(attrs={"placeholder": "Familya"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap klasslari
        for name in ["ism", "familya", "telefon1", "telefon2", "email", "password"]:
            self.fields[name].widget.attrs.setdefault("class", "form-control")
        for name in ["center", "role"]:
            self.fields[name].widget.attrs.setdefault("class", "form-select")

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
            email=data.get("email"),       # LOGIN shu yerga yoziladi
            telefon1=data.get("telefon1"),
            telefon2=data.get("telefon2"),
            center=data.get("center"),
            role=data.get("role"),
        )
        if user.role == "manager":
            user.is_staff = True
        user.set_password(data.get("password"))
        if commit:
            user.save()
        return user
