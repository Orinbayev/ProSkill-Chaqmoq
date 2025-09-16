from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('stat/managers/',  views.stat_managers,  name='stat_managers'),
    path('stat/teachers/',  views.stat_teachers,  name='stat_teachers'),
    path('stat/students/',  views.stat_students,  name='stat_students'),
    path('stat/products/',  views.stat_products,  name='stat_products'),
    path('stat/requests/',  views.stat_requests,  name='stat_requests'),
    path('stat/ledger/',    views.stat_ledger,    name='stat_ledger'),
]
