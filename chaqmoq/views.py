from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse

from django.contrib.auth import get_user_model
from .models import Ledger, Rule
from education.models import Group, Enrollment, Attendance
from django.utils import timezone
from datetime import datetime

User = get_user_model()

def reyting(request):
    leaderboard = (
        Ledger.objects
        .filter(student__role="student")   # faqat studentlar!
        .values("student__ism", "student__familya")
        .annotate(jami=Sum("ball"))
        .order_by("-jami")
    )
    return render(request, "chaqmoq/reyting.html", {"leaderboard": leaderboard})

@login_required
def student_detail(request, pk):
    student = get_object_or_404(User, pk=pk, role='student')
    n = request.GET.get('n', '15')

    enrolls = Enrollment.objects.filter(student=student).select_related('group')

    att_qs = (
        Attendance.objects
        .filter(student=student)
        .select_related('group')
        .order_by('-date')
    )
    led_qs = (
        Ledger.objects
        .filter(student=student)
        .select_related('group', 'rule', 'beruvchi')
        .order_by('-sana')
    )

    if n != 'all':
        limit = 50 if n == '50' else 15
        att_qs = att_qs[:limit]
        led_qs = led_qs[:limit]

    balance = Ledger.objects.filter(student=student).aggregate(total=Sum('ball'))['total'] or 0

    ctx = {
        'student': student,
        'enrolls': enrolls,
        'attendance': att_qs,
        'ledger': led_qs,
        'balance': balance,
        'n': n,
    }
    return render(request, 'chaqmoq/student_detail.html', ctx)

@login_required
def api_group_students(request, group_id: int):
    enrolls = (
        Enrollment.objects
        .filter(group_id=group_id)
        .select_related('student')
        .order_by('student__ism', 'student__familya')
    )
    options = ['<option value="">---------</option>']
    for e in enrolls:
        options.append(f'<option value="{e.student_id}">{e.student.ism} {e.student.familya}</option>')
    return HttpResponse("".join(options))

@login_required
def students_json(request):
    gid = request.GET.get('group')
    qs = User.objects.filter(role='student')
    if gid:
        qs = qs.filter(enrollment__group_id=gid)
    data = [{'id': u.id, 'name': f"{u.ism} {u.familya}"} for u in qs.order_by('ism','familya').distinct()]
    return JsonResponse({'students': data})

@login_required
def berish(request):
    groups = Group.objects.select_related('oqituvchi', 'center').order_by('nom')
    rules = Rule.objects.order_by('nom')

    # O‘qituvchi faqat o‘z guruhlarini ko‘radi
    if request.user.role == 'teacher':
        groups = groups.filter(oqituvchi=request.user)

    selected_gid = request.GET.get('group') or request.POST.get('group')

    # Faqat studentlarni chiqaramiz
    students = User.objects.filter(role='student')
    if selected_gid:
        students = students.filter(enrollment__group_id=selected_gid)
    students = students.order_by('ism', 'familya').distinct()

    # POST so‘rov (ball berish/ayirish)
    if request.method == 'POST':
        try:
            student_id = int(request.POST.get('student') or 0)
            rule_id = int(request.POST.get('rule') or 0)
            raw_ball = int(request.POST.get('ball') or 0)
        except ValueError:
            messages.error(request, 'Noto‘g‘ri maʼlumot.')
            return redirect('chaqmoq:berish')

        if not student_id or not rule_id:
            messages.error(request, 'Student va qoida majburiy.')
            return redirect(f"{request.path}?group={selected_gid or ''}")

        # Student va qoida obyektlari
        student = get_object_or_404(User, pk=student_id, role='student')
        rule = get_object_or_404(Rule, pk=rule_id)

        abs_ball = abs(raw_ball)
        if abs_ball < rule.min_baho or abs_ball > rule.max_baho:
            messages.error(
                request, f"Ball {rule.min_baho}..{rule.max_baho} oralig‘ida bo‘lishi kerak."
            )
            return redirect(f"{request.path}?group={selected_gid or ''}")

        # Ballni belgilang (+ yoki -)
        signed = abs_ball if rule.tur == Rule.PLUS else -abs_ball
        group = Group.objects.filter(pk=selected_gid).first() if selected_gid else None

        # 🔹 Tanlangan sanani olish
        davomat_sana_str = request.POST.get('davomat_sana')
        if davomat_sana_str:
            try:
                tanlangan_sana = datetime.strptime(davomat_sana_str, '%Y-%m-%d')
                tanlangan_sana = timezone.make_aware(tanlangan_sana)
            except ValueError:
                tanlangan_sana = timezone.now()
        else:
            tanlangan_sana = timezone.now()

        # 🔹 Yangi chaqmoq yozuvi
        Ledger.objects.create(
            student=student,
            beruvchi=request.user,
            group=group,
            rule=rule,
            ball=signed,
            sana=tanlangan_sana
        )

        messages.success(request, f"{student.ism} uchun {signed} chaqmoq yozildi ({tanlangan_sana.date()}).")
        return redirect(f"{request.path}?group={selected_gid or ''}")

    return render(request, 'chaqmoq/berish.html', {
        'groups': groups,
        'rules': rules,
        'students': students,
        'selected_gid': selected_gid,
    })


@login_required
def my_chaqmoq(request):
    """O‘quvchi o‘zining davomatini va chaqmoqlarini ko‘radi."""
    if getattr(request.user, 'role', None) != 'student':
        # Student bo‘lmasa bosh sahifaga
        return redirect('core:home')

    student = request.user
    n = request.GET.get("n", "15")

    enrolls = Enrollment.objects.filter(student=student).select_related("group")
    att_qs = Attendance.objects.filter(student=student).select_related("group").order_by("-date")
    led_qs = Ledger.objects.filter(student=student).select_related("group", "rule").order_by("-sana")

    if n != "all":
        limit = 50 if n == "50" else 15
        att_qs = att_qs[:limit]
        led_qs = led_qs[:limit]

    balance = Ledger.student_balansi(student.id)

    ctx = {
        "student": student,
        "enrolls": enrolls,
        "attendance": att_qs,
        "ledger": led_qs,
        "balance": balance,
        "n": n,
    }
    # Mavjud templatedan foydalanamiz
    return render(request, "chaqmoq/student_detail.html", ctx)