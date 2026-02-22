from django.urls import path
from . import views

app_name = "accounts"

# --- Tenant URLs (Center Specific) ---
# Copied from accounts/urls.py to separate tenant access from platform admin
urlpatterns = [
    path("profil/", views.user_edit, name="profile"), 
    path("qoshish/", views.add_user, name="add_user"),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("oqtuvchi/<int:user_id>/", views.teacher_detail, name="teacher_detail"),
    path("talaba/<int:user_id>/", views.student_detail, name="student_detail"),
    path("logout/", views.logout_now, name="logout"),
]
