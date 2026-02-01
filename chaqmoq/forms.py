from django import forms
from .models import Rule

class RuleForm(forms.ModelForm):
    class Meta:
        model = Rule
        fields = ['nom', 'tur', 'min_baho', 'max_baho', 'can_director', 'can_manager', 'can_teacher']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: Darsda faollik'}),
            'tur': forms.Select(attrs={'class': 'form-select'}),
            'min_baho': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_baho': forms.NumberInput(attrs={'class': 'form-control'}),
            'can_director': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manager': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_teacher': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
