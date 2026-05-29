from django.urls import path
from . import views

app_name = "accounts"

# --- Tenant URLs (Center Specific) ---
# Copied from accounts/urls.py to separate tenant access from platform admin
urlpatterns = [
    path("profil/", views.user_edit, name="profile"), 
    path("qoshish/", views.add_user, name="add_user"),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("user/<int:pk>/edit/ajax/", views.student_edit_ajax, name="student_edit_ajax"),
    path("oqtuvchi/<int:user_id>/", views.teacher_detail, name="teacher_detail"),
    path("talaba/<int:user_id>/", views.student_detail, name="student_detail"),
    path("logout/", views.logout_now, name="logout"),
    path("my-centers/", views.director_my_centers, name="my_centers"),
    path("switch-center/", views.director_switch_center, name="director_switch_center"),
    path("branch-request/", views.director_branch_request, name="branch_request"),
    path("branch/<int:center_id>/edit/", views.director_branch_edit, name="director_branch_edit"),
    path("branch/<int:center_id>/deactivate/", views.director_branch_deactivate, name="director_branch_deactivate"),
]
