from django.urls import path
from . import views

app_name = 'chaqmoq'

urlpatterns = [
    path('reyting/', views.reyting, name='reyting'),
    path('student/<int:pk>/', views.student_detail, name='student_detail'),

    # AJAX endpointlar:
    path('api/group/<int:group_id>/students/', views.api_group_students, name='api_group_students'),
    path('api/students/', views.students_json, name='students_json'),

    # Chaqmoq berish sahifasi
    path('berish/', views.berish, name='berish'),
    path('mening/', views.my_chaqmoq, name='my'),

]
