from django.urls import path
from . import views

app_name = 'chaqmoq'

urlpatterns = [
    path('reyting/', views.reyting, name='reyting'),
    path('berish/', views.berish, name='berish'),
    path('student/<int:pk>/', views.student_detail, name='student_detail'),
]
