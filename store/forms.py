from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nom','narx_chaqmoq','qoldiq','izoh']
