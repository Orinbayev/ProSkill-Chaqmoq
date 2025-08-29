from django.urls import path
from . import views

app_name = 'chaqmoq'

urlpatterns = [
    path('reyting/', views.reyting, name='reyting'),
]
