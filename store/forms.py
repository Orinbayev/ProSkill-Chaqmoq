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
        fields = ['ism', 'familya', 'telefon1', 'telefon2', 'yosh', 'address', 'manba', 'yonalish', 'status', 'comment']
        widgets = {
            'ism': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ism'}),
            'familya': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Familya'}),
            'telefon1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon raqam 1'}),
            'telefon2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon raqam 2'}),
            'yosh': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Yosh'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Yashash manzili'}),
            'manba': forms.Select(attrs={'class': 'form-select'}),
            'yonalish': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            # 🟢 Yangi maydon: izoh
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Masalan: O‘quvchi darsga kech kelgan, yoki rad etgan sababi...'}),
        }
