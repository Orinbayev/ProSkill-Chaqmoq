from django import forms
from django.contrib.auth import get_user_model
from .models import Enrollment, Group

User = get_user_model()

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
