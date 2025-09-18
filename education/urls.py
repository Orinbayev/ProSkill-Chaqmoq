from django.urls import path
from . import views

app_name = "education"

urlpatterns = [
    path("guruhlar/", views.guruhlar, name="guruhlar"),
    
    path("mening-guruhlarim/", views.my_groups, name="men_guruhlarim"),
    path("guruh/<int:pk>/", views.group_detail, name="group_detail"),

    # CRUD guruhlar
    path("guruhlar/yaratish/",            views.group_create, name="group_create"),
    path("guruh/<int:pk>/tahrirlash/",    views.group_edit,   name="group_edit"),
    path("guruh/<int:pk>/ochirish/",      views.group_delete, name="group_delete"),
    path("guruh/<int:pk>/points/", views.group_points, name="group_points"),
    path("mening-guruhlarim/", views.my_groups, name="mening_guruhlarim"),

    # Guruhdan chiqarish (Enrollment delete)
    path("enrollment/<int:pk>/remove/",   views.enrollment_remove, name="enrollment_remove"),

]
