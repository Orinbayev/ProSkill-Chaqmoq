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
from django.core.paginator import Paginator
from django.db.models import Sum, Case, When, IntegerField, Value, F, Q
from django.db.models.functions import Coalesce, Abs


User = get_user_model()
from .forms import RuleForm


def get_active_center(request):
    """Helper: active center ni topish"""
    if hasattr(request, "center") and request.center:
        return request.center
    if hasattr(request.user, "center") and request.user.center:
        return request.user.center
    return None


def reyting(request):
    q = (request.GET.get("q") or "").strip()
    per_page = request.GET.get("per_page", "10")
    page = request.GET.get("page", "1")

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 50
    if per_page not in (10, 20, 50, 100):
        per_page = 50

    # ✅ Tenant isolation
    center = get_active_center(request)
    base = Ledger.objects.filter(student__role="student")
    if center:
        base = base.filter(student__center=center)

    # ✅ Umumiy leaderboard (hamma o‘quvchi)
    leaderboard_all = (
        base.values("student__id", "student__ism", "student__familya")
        .annotate(jami=Coalesce(Sum("ball"), 0))
        .order_by("-jami", "student__ism", "student__id")
    )

    is_search = bool(q)
    rank_map = None

    # ✅ Agar qidiruv bo‘lsa: hamma ro‘yxatdan REAL rank chiqarib olamiz
    if is_search:
        rank_map = {}
        for idx, sid in enumerate(leaderboard_all.values_list("student__id", flat=True), start=1):
            rank_map[sid] = idx

        leaderboard_qs = leaderboard_all.filter(
            Q(student__ism__icontains=q) | Q(student__familya__icontains=q)
        )
    else:
        leaderboard_qs = leaderboard_all

    paginator = Paginator(leaderboard_qs, per_page)
    page_obj = paginator.get_page(page)

    # ✅ Page ichidagi dictlarga rank qo‘shib yuboramiz (faqat qidiruvda)
    if rank_map is not None:
        for row in page_obj.object_list:
            row["rank"] = rank_map.get(row["student__id"])

    # Pagination window
    cur = page_obj.number
    total = paginator.num_pages
    start = max(1, cur - 3)
    end = min(total, cur + 3)
    page_window = range(start, end + 1)

    ctx = {
        "page_obj": page_obj,
        "q": q,
        "per_page": per_page,
        "page_window": page_window,
        "is_search": is_search,   # ✅ template uchun
    }
    return render(request, "chaqmoq/reyting.html", ctx)


@login_required
def student_detail(request, pk):
    student = get_object_or_404(User, pk=pk, role='student')

    # ✅ per_page (10/20/50/100/all) va page
    per_page_raw = request.GET.get("per_page", "10")
    page_number = request.GET.get("page", "1")

    per_page = per_page_raw if per_page_raw == "all" else int(per_page_raw)

    # ✅ Tenant Isolation (Data Isolation)
    center = get_active_center(request)
    
    enrolls = Enrollment.objects.filter(student=student).select_related('group')
    if center:
        enrolls = enrolls.filter(group__center=center)

    led_qs = (
        Ledger.objects
        .filter(student=student)
    )
    if center:
        led_qs = led_qs.filter(Q(group__center=center) | Q(rule__center=center))

    led_qs = (
        led_qs
        .select_related('group', 'rule', 'beruvchi')
        .order_by('-created_at')
    )

    # ✅ Umumiy totals (plus/minus/balance)
    totals = led_qs.aggregate(
        total_plus=Coalesce(Sum(Case(
            When(ball__gt=0, then=F("ball")),
            default=Value(0),
            output_field=IntegerField()
        )), 0),
        total_minus=Coalesce(Sum(Case(
            When(ball__lt=0, then=Abs(F("ball"))),
            default=Value(0),
            output_field=IntegerField()
        )), 0),
        balance=Coalesce(Sum("ball"), 0)
    )

    # ✅ Teacher/Manager/Director bo‘yicha statistika (role bilan)
    teacher_stats = (
        led_qs
        .values("beruvchi__id", "beruvchi__ism", "beruvchi__familya", "beruvchi__role")
        .annotate(
            coin_plus=Coalesce(Sum(Case(
                When(ball__gt=0, then=F("ball")),
                default=Value(0),
                output_field=IntegerField()
            )), 0),
            coin_minus=Coalesce(Sum(Case(
                When(ball__lt=0, then=Abs(F("ball"))),
                default=Value(0),
                output_field=IntegerField()
            )), 0),
        )
        .order_by("-coin_plus", "-coin_minus", "beruvchi__ism")
    )

    # ✅ Pagination
    page_obj = None
    page_window = []

    if per_page != "all":
        paginator = Paginator(led_qs, per_page)
        page_obj = paginator.get_page(page_number)
        ledger = page_obj.object_list

        # chiroyli page window (1..N ichidan keraklisini ko‘rsatish)
        current = page_obj.number
        last = paginator.num_pages
        start = max(1, current - 3)
        end = min(last, current + 3)
        page_window = list(range(start, end + 1))
    else:
        ledger = led_qs

    ctx = {
        "student": student,
        "enrolls": enrolls,
        "ledger": ledger,
        "totals": totals,
        "teacher_stats": teacher_stats,

        "per_page": per_page,          # template’dagi select ishlaydi
        "page_obj": page_obj,
        "page_window": page_window,
    }
    return render(request, "chaqmoq/student_detail.html", ctx)


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
from datetime import date

@login_required
def berish(request):
    # ✅ Tenant isolation
    center = get_active_center(request)
    groups = Group.objects.select_related('oqituvchi', 'center').order_by('nom')
    if center:
        groups = groups.filter(center=center)
    
    rules = Rule.objects.filter(Q(center=center) | Q(center__isnull=True))
    if request.user.role == 'teacher':
        rules = rules.filter(can_teacher=True)
    elif request.user.role == 'manager':
        rules = rules.filter(can_manager=True)
    elif request.user.role == 'director':
        rules = rules.filter(can_director=True)
    rules = rules.order_by('nom')

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
        # davomat_sana_str = request.POST.get('davomat_sana')
# 🔹 Tanlangan sanani olish
        davomat_sana_str = request.POST.get('davomat_sana')

        if davomat_sana_str:
            try:
                # user tanlagan KUN
                d = datetime.strptime(davomat_sana_str, "%Y-%m-%d").date()

                # hozirgi real vaqt (soat/minut)
                now_local = timezone.localtime(timezone.now()).time().replace(second=0, microsecond=0)

                # sana + real vaqt birlashtiramiz
                tanlangan_sana = timezone.make_aware(
                    datetime.combine(d, now_local),
                    timezone.get_current_timezone()
                )
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
        "today": date.today(),
    })


@login_required
def my_chaqmoq(request):
    if getattr(request.user, "role", None) != "student":
        return redirect("core:home")

    student = request.user

    per_page = request.GET.get("per_page") or request.GET.get("n") or "20"
    page = request.GET.get("page", "1")

    if per_page == "all":
        per_page_int = None
    else:
        try:
            per_page_int = int(per_page)
        except ValueError:
            per_page_int = 20
        if per_page_int not in (10, 20, 50, 100):
            per_page_int = 20

    center = get_active_center(request)
    enrolls = Enrollment.objects.filter(student=student).select_related("group")
    if center:
        enrolls = enrolls.filter(group__center=center)

    teacher_stats_qs = Ledger.objects.filter(student=student)
    if center:
        teacher_stats_qs = teacher_stats_qs.filter(Q(group__center=center) | Q(rule__center=center))

    teacher_stats = (
        teacher_stats_qs
        .values("beruvchi__id", "beruvchi__ism", "beruvchi__familya")
        .annotate(
            coin_plus=Coalesce(Sum(
                Case(When(ball__gt=0, then=F("ball")), default=Value(0), output_field=IntegerField())
            ), 0),
            coin_minus=Coalesce(Sum(
                Case(When(ball__lt=0, then=Abs(F("ball"))), default=Value(0), output_field=IntegerField())
            ), 0),
        )
        .order_by("-coin_plus", "beruvchi__ism")
    )

    totals_qs = Ledger.objects.filter(student=student)
    if center:
        totals_qs = totals_qs.filter(Q(group__center=center) | Q(rule__center=center))

    totals = totals_qs.aggregate(
        total_plus=Coalesce(Sum(
            Case(When(ball__gt=0, then=F("ball")), default=Value(0), output_field=IntegerField())
        ), 0),
        total_minus=Coalesce(Sum(
            Case(When(ball__lt=0, then=Abs(F("ball"))), default=Value(0), output_field=IntegerField())
        ), 0),
        balance=Coalesce(Sum("ball"), 0),
    )

    led_qs = (
        Ledger.objects
        .filter(student=student)
    )
    if center:
        led_qs = led_qs.filter(Q(group__center=center) | Q(rule__center=center))

    led_qs = (
        led_qs
        .select_related("group", "rule", "beruvchi")
        .order_by("-sana")
    )

    if per_page_int is None:
        ledger_page = led_qs
        page_obj = None
        page_window = []
    else:
        paginator = Paginator(led_qs, per_page_int)
        page_obj = paginator.get_page(page)
        ledger_page = page_obj

        cur = page_obj.number
        total = paginator.num_pages
        start = max(1, cur - 3)
        end = min(total, cur + 3)
        page_window = range(start, end + 1)

    ctx = {
        "student": student,
        "enrolls": enrolls,
        "teacher_stats": teacher_stats,
        "totals": totals,

        "ledger": ledger_page,
        "page_obj": page_obj,
        "page_window": page_window,

        "per_page": "all" if per_page_int is None else per_page_int,
    }
    return render(request, "chaqmoq/student_detail.html", ctx)
@login_required
def rule_list(request):
    center = get_active_center(request)
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo'q")
        return redirect("education:groups_home")
    
    rules = Rule.objects.all()
    if center:
        rules = rules.filter(center=center)
    else:
        # Superadmin center tanlamagan bo'lsa global qoidalarni ko'radi
        rules = rules.filter(center__isnull=True)
    
    return render(request, "chaqmoq/rule_settings.html", {
        "rules": rules,
        "center_limit": center.max_daily_lightning if center else 0,
        "center_deduction_limit": center.max_daily_deduction if center else 0,
    })

@login_required
def rule_settings_update(request):
    center = get_active_center(request)
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)
    
    if request.method == "POST":
        try:
            limit_plus = int(request.POST.get("max_daily_lightning", 0))
            limit_minus = int(request.POST.get("max_daily_deduction", 0))
            if center:
                center.max_daily_lightning = limit_plus
                center.max_daily_deduction = limit_minus
                center.save()
                messages.success(request, "Sozlamalar yangilandi ✅")
        except ValueError:
            messages.error(request, "Noto'g'ri qiymat kiritildi")
            
    return redirect("chaqmoq:rule_list")

@login_required
def rule_add(request):
    center = get_active_center(request)
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo'q")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = RuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.center = center
            rule.save()
            messages.success(request, "Qoida saqlandi ✅")
            return redirect("chaqmoq:rule_list")
    else:
        form = RuleForm()
    
    return render(request, "chaqmoq/rule_form.html", {"form": form, "title": "Yangi qoida qo'shish"})

@login_required
def rule_edit(request, pk):
    center = get_active_center(request)
    rule = get_object_or_404(Rule, pk=pk)
    
    # Isolation check
    if center and rule.center != center and not request.user.is_superuser:
        messages.error(request, "Ruxsat yo'q")
        return redirect("chaqmoq:rule_list")

    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo'q")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = RuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, "Qoida yangilandi ✅")
            return redirect("chaqmoq:rule_list")
    else:
        form = RuleForm(instance=rule)
    
    return render(request, "chaqmoq/rule_form.html", {"form": form, "title": "Qoidani tahrirlash"})

@login_required
def rule_delete(request, pk):
    center = get_active_center(request)
    rule = get_object_or_404(Rule, pk=pk)
    
    # Isolation check
    if center and rule.center != center and not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    rule.delete()
    messages.success(request, "Qoida o'chirildi 🗑️")
    return redirect("chaqmoq:rule_list")
