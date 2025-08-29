from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    u = request.user
    # Superuserni avtomatik direktor deb ko‘ramiz:
    role = getattr(u, 'role', None)
    if (not role) and u.is_superuser:
        role = 'director'

    if role == 'director':
        return render(request, 'core/dashboard_director.html')
    if role == 'manager':
        return render(request, 'core/dashboard_manager.html')
    if role == 'teacher':
        return render(request, 'core/dashboard_teacher.html')
    if role == 'student':
        return render(request, 'core/dashboard_student.html')

    # Rol yo‘q bo‘lsa, admin orqali sozlashga yo‘naltiramiz
    return redirect('/admin/auth/user/')  # foydalanuvchini tahrirlab role qo‘yib qo‘y

