from django.urls import path
from . import views

app_name = 'education'

urlpatterns = [
    path("guruhlar/", views.guruhlar, name="guruhlar"),
    path("guruhlar/meniki/", views.men_guruhlarim, name="men_guruhlarim"),
    path("guruhlar/yangi/", views.group_create, name="group_create"),
    path("guruhlar/enroll/add/", views.enroll_add, name="enroll_add"),
    path("guruhlar/<int:group_id>/talabalar/", views.group_students, name="group_students"),
    path("guruhlar/<int:group_id>/davomat/", views.group_rollcall, name="group_rollcall"),
]
