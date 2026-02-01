from django import forms
from .models import Product, ProductImage
from .models import Lead

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nom', 'narx_chaqmoq', 'izoh']

class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['rasm']



class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['ism', 'familya', 'otchestvo', 'birth_date', 'gender', 'passport_id', 'jshr', 'telefon1', 'telefon2', 'address', 'manba', 'yonalish', 'status', 'comment']
        widgets = {
            'ism': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ism'}),
            'familya': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Familya'}),
            'otchestvo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Otasining ismi'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'passport_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport ID'}),
            'jshr': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'JSHR'}),
            'telefon1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon raqam 1'}),
            'telefon2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon raqam 2'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Yashash manzili'}),
            'manba': forms.Select(attrs={'class': 'form-select'}),
            'yonalish': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Masalan: O‘quvchi darsga kech kelgan, yoki rad etgan sababi...'}),
        }

    def __init__(self, *args, **kwargs):
        center = kwargs.pop('center', None)
        super().__init__(*args, **kwargs)
        if center:
            from .models import Manba, Yonalish, LeadStatus
            self.fields['manba'].queryset = Manba.objects.filter(center=center)
            self.fields['yonalish'].queryset = Yonalish.objects.filter(center=center)
            self.fields['status'].queryset = LeadStatus.objects.filter(center=center)
