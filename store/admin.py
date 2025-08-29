from django.contrib import admin
from .models import Product, ProductImage, PurchaseRequest, Sale

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nom','narx_chaqmoq','qoldiq')
    inlines = [ProductImageInline]

admin.site.register(PurchaseRequest)
admin.site.register(Sale)
