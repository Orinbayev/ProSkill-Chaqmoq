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
        self.fields['role'].initial = 'teacher'

class ManagerCreateStudentForm(BaseUserCreateForm):
    auto_email_domain = '@proskillcoin.com'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].initial = 'student'
        self.fields['email'].required = False

    def clean(self):
        data = super().clean()
        email = data.get('email')
        ism = data.get('ism','').strip().lower().replace(' ','')
        familya = data.get('familya','').strip().lower().replace(' ','')
        if not email:
            data['email'] = f"{ism}{familya}{self.auto_email_domain}"
            self.cleaned_data['email'] = data['email']
        return data
