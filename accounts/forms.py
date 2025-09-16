from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class BaseUserCreateForm(forms.ModelForm):
    parol = forms.CharField(label='Parol', widget=forms.PasswordInput, required=True)

    class Meta:
        model = User
        fields = ['email','ism','familya','telefon1','telefon2','gmail','role','center']

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data['parol']
        user.set_password(password)
        if commit:
            user.save()
        return user

class ManagerCreateTeacherForm(BaseUserCreateForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].widget = forms.HiddenInput()
        self.fields['role'].initial = 'teacher'
    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.role = 'teacher'
        if commit: obj.save()
        return obj

class ManagerCreateStudentForm(BaseUserCreateForm):
    auto_email_domain = '@proskillcoin.com'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].widget = forms.HiddenInput()
        self.fields['role'].initial = 'student'
        self.fields['email'].required = False

    def _gen_unique_email(self, base):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        email = base
        i = 1
        while U.objects.filter(email=email).exists():
            local, dom = base.split('@', 1)
            email = f"{local}{i}@{dom}"
            i += 1
        return email

    def clean(self):
        data = super().clean()
        email = data.get('email')
        ism = data.get('ism','').strip().lower().replace(' ','')
        familya = data.get('familya','').strip().lower().replace(' ','')
        if not email:
            base = f"{ism}{familya}{self.auto_email_domain}"
            data['email'] = self._gen_unique_email(base)
            self.cleaned_data['email'] = data['email']
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.role = 'student'
        if commit: obj.save()
        return obj
    

class ManagerCreateManagerForm(BaseUserCreateForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].initial = 'manager'

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email','ism','familya','telefon1','telefon2','gmail','role','center','is_active']
