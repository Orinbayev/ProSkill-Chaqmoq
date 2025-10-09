# education/urls.py
from django.urls import path
from . import views

app_name = "education"

urlpatterns = [
    # === 📚 HUB / RO‘YXATLAR ===
    path("guruhlar/", views.groups_hub, name="groups_hub"),
    path("guruhlar/ro‘yxat/", views.group_list, name="group_list"),
    path("guruhlar/tillar/", views.groups_by_category, {"category": "lang"}, name="groups_lang"),
    path("guruhlar/it/", views.groups_by_category, {"category": "it"}, name="groups_it"),

    # === ➕ YARATISH / TAHRIRLASH / O‘CHIRISH ===
    path("guruh/yaratish/tillar/", views.group_create_lang, name="group_create_lang"),
    path("guruh/yaratish/it/", views.group_create_it, name="group_create_it"),
    path("guruh/<int:pk>/tahrirlash/", views.group_edit, name="group_edit"),
    path("guruh/<int:pk>/o‘chirish/", views.group_delete, name="group_delete"),

    # === 👥 GURUHLAR ===
    path("guruh/<int:pk>/", views.group_detail, name="group_detail"),
    path("guruh/<int:pk>/add-student/", views.add_student_to_group, name="add_student_to_group"),
    path("guruh/<int:pk>/davomat/", views.group_rollcall, name="group_rollcall"),

    # === 📅 DAVOMAT va BALLAR ===
    path("guruh/<int:pk>/attendance_today/", views.attendance_today, name="attendance_today"),
    path("guruh/<int:pk>/points/", views.group_points, name="group_points"),
    path("attendance/toggle/", views.toggle_attendance, name="toggle_attendance"),

    # === 👨‍🏫 O‘QITUVCHI UCHUN ===
    path("mening-guruhlarim/", views.my_groups, name="my_groups"),
    path("guruhlar/meniki/", views.my_groups, name="men_guruhlarim"),
    path("mening_guruhlarim/", views.my_groups, name="mening_guruhlarim"),

    # === 🧍‍♂️ O‘QUVCHILAR ===
    path("student/<int:student_id>/", views.student_detail, name="student_detail"),
    path("kiritish/<int:pk>/olib-tashlash/", views.enrollment_remove, name="enrollment_remove"),
]
