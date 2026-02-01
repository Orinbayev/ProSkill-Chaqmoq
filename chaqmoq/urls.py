from django.urls import path
from . import views

app_name = 'chaqmoq'

urlpatterns = [
    path('reyting/', views.reyting, name='reyting'),
    path('student/<int:pk>/', views.student_detail, name='student_detail'),
    path("my/", views.my_chaqmoq, name="my_chaqmoq"),

    # AJAX endpointlar:
    path('api/group/<int:group_id>/students/', views.api_group_students, name='api_group_students'),
    path('api/students/', views.students_json, name='students_json'),

    # Chaqmoq berish sahifasi
    path('berish/', views.berish, name='berish'),
    path('mening/', views.my_chaqmoq, name='my'),

    # Qoidalarni boshqarish (Settings)
    path('rules/', views.rule_list, name='rule_list'),
    path('rules/settings/update/', views.rule_settings_update, name='rule_settings_update'),
    path('rules/add/', views.rule_add, name='rule_add'),
    path('rules/<int:pk>/edit/', views.rule_edit, name='rule_edit'),
    path('rules/<int:pk>/delete/', views.rule_delete, name='rule_delete'),

]
