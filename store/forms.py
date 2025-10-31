from django import forms
from .models import Product, ProductImage

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nom', 'narx_chaqmoq', 'izoh']

class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['rasm']
