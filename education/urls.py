# education/urls.py
from django.urls import path
from . import views

app_name = "education"

urlpatterns = [
    # HUB (ikki xil nom bilan: yangi va eski)
    path("guruhlar/", views.groups_hub, name="groups_hub"),
    path("guruhlar/", views.groups_hub, name="guruhlar"),              # <-- eski nomga alias
    path("guruhlar/umumiy/", views.groups_hub, name="guruhlar_umumiy"),

    # Ro‘yxatlar (kategoriya bo‘yicha)
    path("guruhlar/tillar/", views.groups_by_category, {"category": "lang"}, name="groups_lang"),
    path("guruhlar/it/",     views.groups_by_category, {"category": "it"},   name="groups_it"),

    # Yaratish
    path("guruh/yaratish/tillar/", views.group_create_lang, name="group_create_lang"),
    path("guruh/yaratish/it/",     views.group_create_it,   name="group_create_it"),

    # Qolganlari
    path("guruh/<int:pk>/", views.group_detail, name="group_detail"),
    path("guruh/<int:pk>/tahrirlash/", views.group_edit, name="group_edit"),
    path("guruh/<int:pk>/ochirish/", views.group_delete, name="group_delete"),
    path("guruh/<int:pk>/points/", views.group_points, name="group_points"),
    path("mening-guruhlarim/", views.my_groups, name="my_groups"),
    path("kiritish/<int:pk>/olib-tashlash/", views.enrollment_remove, name="enrollment_remove"),
]
