from django.contrib import admin
from .models import Product, ProductImage, PurchaseRequest, Sale, Comment, Lead, Yonalish, Manba, LeadStatus


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nom', 'narx_chaqmoq', 'sotilgan_soni', 'yaratilgan')
    search_fields = ('nom',)
    list_filter = ('yaratilgan',)
    readonly_fields = ('sotilgan_soni',)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'rasm')


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'product', 'qty', 'status', 'sana')
    list_filter = ('status', 'sana')
    search_fields = ('student__first_name', 'student__last_name', 'product__nom')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('student', 'product', 'qty', 'narx_chaqmoq', 'manager', 'sana')
    list_filter = ('manager', 'sana')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'text', 'created_at')


admin.site.register(Lead)
admin.site.register(Yonalish)
admin.site.register(Manba)
admin.site.register(LeadStatus)
