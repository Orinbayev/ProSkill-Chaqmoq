from django.urls import path
from . import views

app_name = 'education'

urlpatterns = [
    path("guruhlar/", views.guruhlar, name="guruhlar"),
    path("guruhlar/meniki/", views.men_guruhlarim, name="men_guruhlarim"),
]
