from django.contrib import admin
from .models import (
    Comment,
    Expense,
    Lead,
    LeadActivity,
    LeadStatus,
    Manba,
    Product,
    ProductImage,
    PurchaseRequest,
    Sale,
    TrialLesson,
    TrialLessonActivity,
    Yonalish,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nom', 'narx_chaqmoq', 'narx_som', 'sotilgan_soni', 'yaratilgan')
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
    list_display = ('student', 'product', 'qty', 'narx_chaqmoq', 'narx_som', 'manager', 'sana')
    list_filter = ('manager', 'sana')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'text', 'created_at')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ism",
        "familya",
        "telefon1",
        "status",
        "assigned_manager",
        "next_follow_up_date",
        "converted_to_student",
        "is_archived",
        "qoshilgan_sana",
    )
    list_filter = ("status", "manba", "assigned_manager", "converted_to_student", "is_archived", "qoshilgan_sana")
    search_fields = ("ism", "familya", "telefon1", "parent_phone", "comment", "lost_reason")
    readonly_fields = ("qoshilgan_sana", "updated_at", "converted_at")
    raw_id_fields = ("assigned_manager", "manba", "yonalish", "status", "converted_user")


@admin.register(TrialLesson)
class TrialLessonAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "group", "teacher", "scheduled_at", "result_status", "registered_after_trial")
    list_filter = ("result_status", "teacher", "scheduled_at")
    search_fields = ("lead__ism", "lead__familya", "group__nom", "teacher__ism", "teacher__familya")
    raw_id_fields = ("lead", "group", "teacher", "created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("lead__ism", "lead__familya", "from_value", "to_value", "note")
    raw_id_fields = ("lead", "actor")
    readonly_fields = ("created_at",)


@admin.register(TrialLessonActivity)
class TrialLessonActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "trial_lesson", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("trial_lesson__lead__ism", "trial_lesson__lead__familya", "note")
    raw_id_fields = ("trial_lesson", "actor")
    readonly_fields = ("created_at",)


@admin.register(Yonalish)
class YonalishAdmin(admin.ModelAdmin):
    list_display = ("nom", "center")
    search_fields = ("nom",)


@admin.register(Manba)
class ManbaAdmin(admin.ModelAdmin):
    list_display = ("nom", "center")
    search_fields = ("nom",)


@admin.register(LeadStatus)
class LeadStatusAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "order", "center", "is_active")
    list_filter = ("code", "is_active")
    search_fields = ("nom", "code")
    list_editable = ("order", "is_active")

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('summa', 'izoh', 'sana', 'product', 'center')
    list_filter = ('sana', 'center')
    search_fields = ('izoh',)
