from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from core.mixins import RoleRequiredMixin
from django.utils.decorators import method_decorator
from .forms import ManagerCreateTeacherForm, ManagerCreateStudentForm
from django.contrib.auth import logout
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from .forms import (ManagerCreateTeacherForm, ManagerCreateStudentForm,
                    ManagerCreateManagerForm, UserUpdateForm)

User = get_user_model()

@login_required
def manager_add_teacher(request):
    if not (request.user.is_superuser or request.user.role in ('manager','director')):
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('core:home')
    if request.method == 'POST':
        form = ManagerCreateTeacherForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'O‘qituvchi yaratildi')
            return redirect('core:home')
    else:
        form = ManagerCreateTeacherForm()
    return render(request, 'accounts/add_teacher.html', {'form': form})

@login_required
def manager_add_student(request):
    if not (request.user.is_superuser or request.user.role in ('manager','director')):
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('core:home')
    if request.method == 'POST':
        form = ManagerCreateStudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'O‘quvchi yaratildi')
            return redirect('core:home')
    else:
        form = ManagerCreateStudentForm()
    return render(request, 'accounts/add_student.html', {'form': form})

@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'Tizimdan chiqildi.')
        return redirect('accounts:login')
    # GET bo'lsa, tasdiqlash sahifasi ko'rsatiladi:
    return render(request, 'accounts/logout_confirm.html')


@login_required
def manager_add_manager(request):
    if request.user.role not in ('director',) and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q'); return redirect('core:home')
    form = ManagerCreateManagerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request, 'Manager yaratildi'); return redirect('core:stat_managers')
    return render(request, 'accounts/add_teacher.html', {'form': form})  # tayyor form page’ni ishlatamiz

@login_required
def user_edit(request, pk):
    if request.user.role not in ('director','manager') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q'); return redirect('core:home')
    u = get_object_or_404(User, pk=pk)
    form = UserUpdateForm(request.POST or None, instance=u)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request,'Saqlandi'); 
        return redirect('core:stat_managers' if u.role=='manager' else
                        'core:stat_teachers' if u.role=='teacher' else
                        'core:stat_students')
    return render(request, 'accounts/add_teacher.html', {'form': form})  # minimalizm

@login_required
def user_delete(request, pk):
    if request.user.role not in ('director',) and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q'); return redirect('core:home')
    u = get_object_or_404(User, pk=pk)
    role = u.role
    if request.method == 'POST':
        u.delete(); messages.success(request, 'O‘chirildi')
        return redirect('core:stat_managers' if role=='manager' else
                        'core:stat_teachers' if role=='teacher' else
                        'core:stat_students')
    return render(request, 'accounts/logout_confirm.html', {})  # “tasdiq” shablonidan foydalanamiz