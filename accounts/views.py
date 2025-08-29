from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from core.mixins import RoleRequiredMixin
from django.utils.decorators import method_decorator
from .forms import ManagerCreateTeacherForm, ManagerCreateStudentForm
from django.contrib.auth import logout

@login_required
def manager_add_teacher(request):
    if request.user.role not in ('manager','director'):
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
    if request.user.role not in ('manager','director'):
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