from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("features/", views.features, name="features"),
    path("pricing/", views.pricing, name="pricing"),
    path("demo/", views.demo, name="demo"),
    path("resources/", views.resources, name="resources"),
    path("support/", views.support, name="support"),
    path("vacancies/", views.vacancies, name="vacancies"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
]
