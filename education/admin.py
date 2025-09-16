from django.contrib import admin
from .models import Group, Enrollment, Payment


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('nom','center','oqituvchi','tuzilgan')
    search_fields = ('nom','oqituvchi__ism','oqituvchi__familya')
    list_filter = ('center',)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student_fullname','group','kurs_narhi','jami_tolangan','qoldiq')
    search_fields = ('student__ism','student__familya','group__nom')
    list_filter = ('group__center','group',)
    def student_fullname(self, obj):
        full = getattr(obj.student, "full_name", None)
        return full() if callable(full) else f"{obj.student.ism} {obj.student.familya}"
    student_fullname.short_description = "Talaba"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('enrollment','summa','sana')
    list_filter = ('sana',)