from django.contrib import admin
from .models import Product, ProductImage, PurchaseRequest, Sale

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nom','narx_chaqmoq','qoldiq')
    list_filter = ('yaratilgan',)
    search_fields = ('nom',)
    inlines = [ProductImageInline]

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('sana','student','product','qty','status','manager')
    list_filter = ('status','sana','product')
    search_fields = ('student__ism','student__familya','product__nom')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sana','student','product','qty','narx_chaqmoq','manager')
    list_filter = ('sana','product')
    search_fields = ('student__ism','student__familya','product__nom')
