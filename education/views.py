from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.timezone import localdate
from django.db import transaction
from .models import Group, Enrollment, Attendance
from .forms import EnrollmentCreateForm, GroupCreateForm
from chaqmoq.models import Ledger, Rule

@login_required
def guruhlar(request):
    items = Group.objects.select_related('center','oqituvchi').order_by('-tuzilgan')
    return render(request, "education/guruhlar.html", {"items": items})

@login_required
def men_guruhlarim(request):
    items = Group.objects.filter(oqituvchi=request.user).select_related('center').order_by('-tuzilgan')
    return render(request, "education/men_guruhlarim.html", {"items": items})


@login_required
def group_create(request):
    if request.user.role not in ('manager','director') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('education:guruhlar')
    form = GroupCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Guruh yaratildi.')
        return redirect('education:guruhlar')
    return render(request, "education/group_create.html", {"form": form})

@login_required
def enroll_add(request):
    if request.user.role not in ('manager','director','teacher') and not request.user.is_superuser:
        messages.error(request,'Ruxsat yo‘q')
        return redirect('education:guruhlar')
    form = EnrollmentCreateForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Talaba guruhga qo‘shildi.')
            return redirect('education:guruhlar')
        except Exception as e:
            messages.error(request, f'Xatolik: {e}')
    return render(request, "education/enroll_add.html", {"form": form})

@login_required
def group_students(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if request.user.role == 'teacher' and group.oqituvchi_id != request.user.id and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('education:men_guruhlarim')
    rows = (Enrollment.objects
            .select_related('student')
            .filter(group=group)
            .order_by('student__ism','student__familya'))
    return render(request, "education/group_students.html", {"group": group, "rows": rows})



@login_required
@transaction.atomic
def group_rollcall(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if request.user.role == 'teacher' and group.oqituvchi_id != request.user.id and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q'); return redirect('education:men_guruhlarim')

    rows = (Enrollment.objects
            .select_related('student')
            .filter(group=group)
            .order_by('student__ism','student__familya'))
    day = request.POST.get('date') or request.GET.get('date') or str(localdate())

    # sabablarga ko‘rinadigan ro‘yxat
    plus_rules  = Rule.objects.filter(tur=Rule.PLUS).order_by('nom')
    minus_rules = Rule.objects.filter(tur=Rule.MINUS).order_by('nom')

    if request.method == 'POST':
        for e in rows:
            present = request.POST.get(f'present_{e.student_id}') == 'on'
            Attendance.objects.update_or_create(
                group=group, student=e.student, date=day,
                defaults={'present': present}
            )

            # PLUS
            prule_id = request.POST.get(f'plus_rule_{e.student_id}')
            pval = int(request.POST.get(f'plus_val_{e.student_id}', 0) or 0)
            if prule_id and pval:
                prule = plus_rules.get(pk=prule_id)
                pval = max(prule.min_baho, min(pval, prule.max_baho))
                if pval:
                    Ledger.objects.create(student=e.student, beruvchi=request.user, group=group, rule=prule, ball=pval)

            # MINUS
            mrule_id = request.POST.get(f'minus_rule_{e.student_id}')
            mval = int(request.POST.get(f'minus_val_{e.student_id}', 0) or 0)
            if mrule_id and mval:
                mrule = minus_rules.get(pk=mrule_id)
                mval = max(mrule.min_baho, min(mval, mrule.max_baho))
                if mval:
                    Ledger.objects.create(student=e.student, beruvchi=request.user, group=group, rule=mrule, ball=-mval)

        messages.success(request, 'Davomat va chaqmoq mezonlari saqlandi.')
        return redirect('education:group_rollcall', group_id=group.id)

    att = {a.student_id: a for a in Attendance.objects.filter(group=group, date=day)}
    return render(request, "education/group_rollcall.html", {
        "group": group, "rows": rows, "day": day, "att": att,
        "plus_rules": plus_rules, "minus_rules": minus_rules
    })