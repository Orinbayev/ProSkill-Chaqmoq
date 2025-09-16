from django import forms
from django.contrib.auth import get_user_model
from .models import Ledger, Rule
from education.models import Group

User = get_user_model()

class ChaqmoqForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False, label='Guruh (ixtiyoriy)')
    student = forms.ModelChoiceField(queryset=User.objects.filter(role='student').order_by('ism','familya'))
    rule = forms.ModelChoiceField(queryset=Rule.objects.all().order_by('nom'))
    ball = forms.IntegerField(min_value=-100000, max_value=100000)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and getattr(user,'role',None) == 'teacher':
            self.fields['group'].queryset = Group.objects.filter(oqituvchi=user)
