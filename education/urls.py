# education/urls.py
from django.urls import path
from . import views

app_name = "education"

urlpatterns = [
    # HUB
    path("guruhlar/", views.groups_hub, name="groups_hub"),
    path("guruhlar/", views.groups_hub, name="guruhlar"),  # alias

    # ro‘yxatlar
    path("guruhlar/tillar/", views.groups_by_category, {"category": "lang"}, name="groups_lang"),
    path("guruhlar/it/",     views.groups_by_category, {"category": "it"},   name="groups_it"),

    # yaratish
    path("guruh/yaratish/tillar/", views.group_create_lang, name="group_create_lang"),
    path("guruh/yaratish/it/",     views.group_create_it,   name="group_create_it"),

    # bitta guruh
    path("guruh/<int:pk>/",            views.group_detail,   name="group_detail"),
    path("guruh/<int:pk>/tahrirlash/", views.group_edit,     name="group_edit"),
    path("guruh/<int:pk>/ochirish/",   views.group_delete,   name="group_delete"),

    # AJAX
    path("guruh/<int:pk>/attendance_today/", views.attendance_today, name="attendance_today"),
    path("guruh/<int:pk>/points/",           views.group_points,     name="group_points"),

    # (ixtiyoriy) alohida sahifa
    path("guruh/<int:pk>/davomat/",    views.group_rollcall, name="group_rollcall"),

    # o‘qituvchining guruhlari
    path("mening-guruhlarim/", views.my_groups, name="my_groups"),
    path("guruhlar/meniki/",   views.my_groups, name="men_guruhlarim"),
    path("mening_guruhlarim/", views.my_groups, name="mening_guruhlarim"),

    # a’zolikni olib tashlash
    path("kiritish/<int:pk>/olib-tashlash/", views.enrollment_remove, name="enrollment_remove"),
]
