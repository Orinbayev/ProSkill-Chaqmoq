from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import Ledger, Rule
from .forms import ChaqmoqForm
from django.db.models import Sum, OuterRef, Subquery
from django.shortcuts import render, get_object_or_404
from education.models import Enrollment, Attendance, Group

User = get_user_model()

@login_required
def reyting(request):
    first_group_name = Enrollment.objects.filter(
        student_id=OuterRef('student__id')
    ).order_by('id').values('group__nom')[:1]
    q = (Ledger.objects
         .values('student__id','student__ism','student__familya')
         .annotate(jami=Sum('ball'), group_nom=Subquery(first_group_name))
         .order_by('-jami', 'student__ism'))
    return render(request, 'chaqmoq/reyting.html', {'rows': q})


@login_required
def student_detail(request, pk):
    student = get_object_or_404(User, pk=pk, role='student')
    n = request.GET.get('n','15')
    limit = None if n == 'all' else int(n or 15)

    enrolls = Enrollment.objects.filter(student=student).select_related('group')
    attendance_qs = Attendance.objects.filter(student=student).select_related('group').order_by('-date')
    ledger_qs = Ledger.objects.filter(student=student).select_related('rule','group','beruvchi').order_by('-sana')

    attendance = list(attendance_qs[:limit]) if limit else list(attendance_qs)
    ledger = list(ledger_qs[:limit]) if limit else list(ledger_qs)
    balance = Ledger.student_balansi(student.id)
    return render(request, 'chaqmoq/student_detail.html', {
        'student': student, 'enrolls': enrolls, 'attendance': attendance,
        'ledger': ledger, 'balance': balance, 'n': n
    })

@login_required
def berish(request):
    if request.user.role not in ('teacher','manager','director') and not request.user.is_superuser:
        messages.error(request,'Ruxsat yo‘q')
        return redirect('core:home')
    if request.method == 'POST':
        form = ChaqmoqForm(request.POST, user=request.user)
        if form.is_valid():
            d = form.cleaned_data
            # ballni qoida diapazonida ushla: min..max => sign bo‘yicha
            rule: Rule = d['rule']
            ball = d['ball']
            if rule.tur == Rule.PLUS:
                ball = max(rule.min_baho, min(ball, rule.max_baho))
            else:
                ball = -abs(max(rule.min_baho, min(abs(ball), rule.max_baho)))
            Ledger.objects.create(
                student=d['student'],
                beruvchi=request.user,
                group=d['group'],
                rule=rule,
                ball=ball
            )
            messages.success(request, f"Chaqmoq yozildi: {ball}")
            return redirect('chaqmoq:reyting')
    else:
        form = ChaqmoqForm(user=request.user)
    return render(request, 'chaqmoq/berish.html', {'form': form})
