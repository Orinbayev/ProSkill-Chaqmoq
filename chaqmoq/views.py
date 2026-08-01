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
from django.urls import reverse


User = get_user_model()
from .forms import RuleForm


def get_active_center(request):
    """Helper: active center ni topish"""
    if hasattr(request, "center") and request.center:
        return request.center
    if hasattr(request.user, "center") and request.user.center:
        return request.user.center
    return None


def _is_staff_role(user) -> bool:
    role = getattr(user, "role", None)
    return bool(user and (user.is_superuser or role in {"director", "manager", "teacher"}))


def _student_scope(center):
    qs = User.objects.filter(role="student")
    if center:
        qs = qs.filter(center=center)
    return qs


def _rule_scope_for_user(user, center):
    if center:
        rules = Rule.objects.filter(Q(center=center) | Q(center__isnull=True))
    else:
        rules = Rule.objects.filter(center__isnull=True)

    role = getattr(user, "role", None)
    if role == "teacher":
        rules = rules.filter(can_teacher=True)
    elif role == "manager":
        rules = rules.filter(can_manager=True)
    elif role == "director":
        rules = rules.filter(can_director=True)
    return rules


def _group_scope_for_user(user, center):
    groups = Group.objects.select_related("oqituvchi", "center").order_by("nom")
    if center:
        groups = groups.filter(center=center)
    elif not user.is_superuser:
        groups = groups.none()

    if getattr(user, "role", None) == "teacher" and not user.is_superuser:
        groups = groups.filter(oqituvchi=user)
    return groups


def _can_view_student(request, student) -> bool:
    if request.user.is_superuser:
        return True

    center = get_active_center(request)
    if center:
        return student.center_id == center.id

    if student.center_id and student.center_id != getattr(request.user, "center_id", None):
        return False

    role = getattr(request.user, "role", None)
    return role in {"director", "manager", "teacher", "student", "parent"}


def _student_detail_access_ids(request):
    if request.user.is_superuser:
        return None

    center = get_active_center(request)
    if center:
        return None

    role = getattr(request.user, "role", None)
    if role in {"director", "manager", "teacher"}:
        return None
    if role == "student":
        return {request.user.id}
    if role == "parent":
        return set(request.user.children.values_list("id", flat=True))
    return set()


def _can_filter_rating_by_rule(user) -> bool:
    """
    Qoida bo'yicha filtrlash faqat xodimlar uchun.

    O'quvchi va ota-ona reytingni ko'radi, lekin qaysi qoidadan qancha
    chaqmoq berilganini ajratib ko'ra olmaydi.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "role", None) in {"teacher", "manager", "director"}


def _rating_rules_for_center(center):
    """Markazning qoidalari (+ barcha markazlar uchun umumiy qoidalar)."""
    qs = Rule.objects.all()
    if center:
        qs = qs.filter(Q(center=center) | Q(center__isnull=True))
    return list(qs.order_by("nom"))


def _balances_for_rule(student_ids, rule_id, center=None):
    """
    FAQAT tanlangan qoida bo'yicha berilgan chaqmoqlar yig'indisi.

    MUHIM: bu yerda LightningHistory fallback ISHLATILMAYDI — eski
    LightningHistory yozuvlarida qoida bog'lanishi yo'q, ularni qo'shsak
    "shu qoida bo'yicha" degan raqam yolg'on chiqardi.
    """
    if not student_ids:
        return {}

    qs = Ledger.objects.filter(student_id__in=student_ids, rule_id=rule_id)
    if center:
        qs = qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))
    return {
        row["student_id"]: int(row["total"] or 0)
        for row in qs.values("student_id").annotate(total=Coalesce(Sum("ball"), 0))
    }


def _get_balances_with_legacy_fallback(student_ids, center=None):
    """
    Balans manbasi: avval Ledger, agar umuman ledger yozuvi bo'lmasa LightningHistory fallback.
    """
    if not student_ids:
        return {}

    from chaqmoq.models import LightningHistory

    ledger_qs = Ledger.objects.filter(student_id__in=student_ids)
    if center:
        ledger_qs = ledger_qs.filter(
            Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True)
        )
    ledger_map = {
        row["student_id"]: int(row["total"] or 0)
        for row in (
            ledger_qs.values("student_id").annotate(total=Coalesce(Sum("ball"), 0))
        )
    }

    missing_ids = [sid for sid in student_ids if sid not in ledger_map]
    history_map = {}
    if missing_ids:
        history_qs = LightningHistory.objects.filter(student__user_id__in=missing_ids)
        if center:
            history_qs = history_qs.filter(student__user__center=center)
        history_map = {
            row["student__user_id"]: int(row["total"] or 0)
            for row in (
                history_qs.values("student__user_id").annotate(total=Coalesce(Sum("points"), 0))
            )
        }

    return {sid: ledger_map.get(sid, history_map.get(sid, 0)) for sid in student_ids}


@login_required
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

    center = get_active_center(request)
    students_qs = User.objects.filter(role="student")
    if center:
        students_qs = students_qs.filter(center=center)

    students = list(students_qs.values("id", "ism", "familya"))
    student_ids = [row["id"] for row in students]

    # ── QOIDA BO'YICHA FILTR (faqat teacher / manager / director) ──────────
    can_filter_by_rule = _can_filter_rating_by_rule(request.user)
    rating_rules = _rating_rules_for_center(center) if can_filter_by_rule else []
    allowed_rule_ids = {r.id for r in rating_rules}

    selected_rule_id = None
    if can_filter_by_rule:
        raw_rule = (request.GET.get("rule") or "").strip()
        if raw_rule.isdigit() and int(raw_rule) in allowed_rule_ids:
            selected_rule_id = int(raw_rule)
    selected_rule = next((r for r in rating_rules if r.id == selected_rule_id), None)

    if selected_rule_id:
        # Faqat shu qoida bo'yicha chaqmoq olganlar reytingga kiradi.
        balance_map = _balances_for_rule(student_ids, selected_rule_id, center=center)
        students = [row for row in students if row["id"] in balance_map]
    else:
        balance_map = _get_balances_with_legacy_fallback(student_ids, center=center)

    leaderboard_all = [
        {
            "student__id": row["id"],
            "student__ism": row["ism"],
            "student__familya": row["familya"],
            "jami": int(balance_map.get(row["id"], 0)),
        }
        for row in students
    ]
    leaderboard_all.sort(key=lambda r: (-int(r["jami"]), r["student__ism"] or "", r["student__id"]))

    is_search = bool(q)
    rank_map = None

    if is_search:
        rank_map = {}
        for idx, row in enumerate(leaderboard_all, start=1):
            rank_map[row["student__id"]] = idx

        ql = q.lower()
        leaderboard_qs = [
            row for row in leaderboard_all
            if ql in (row["student__ism"] or "").lower() or ql in (row["student__familya"] or "").lower()
        ]
    else:
        leaderboard_qs = leaderboard_all

    paginator = Paginator(leaderboard_qs, per_page)
    page_obj = paginator.get_page(page)

    if rank_map is not None:
        for row in page_obj.object_list:
            row["rank"] = rank_map.get(row["student__id"])

    allowed_detail_ids = _student_detail_access_ids(request)
    for row in page_obj.object_list:
        student_id = row["student__id"]
        can_open_detail = allowed_detail_ids is None or student_id in allowed_detail_ids
        row["detail_url"] = reverse("chaqmoq:student_detail", args=[student_id]) if can_open_detail else ""

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
        "can_filter_by_rule": can_filter_by_rule,
        "rating_rules": rating_rules,
        "selected_rule_id": selected_rule_id,
        "selected_rule": selected_rule,
    }
    return render(request, "chaqmoq/reyting.html", ctx)


@login_required
def student_detail(request, pk):
    center = get_active_center(request)
    students_qs = User.objects.filter(role="student")
    if center and not request.user.is_superuser:
        students_qs = students_qs.filter(center=center)
    student = get_object_or_404(students_qs, pk=pk)
    if not _can_view_student(request, student):
        messages.error(request, "Siz faqat o'zingizga tegishli reyting tafsilotlarini ko'ra olasiz.")
        return redirect("chaqmoq:reyting")

    # ✅ per_page (10/20/50/100/all) va page
    per_page_raw = request.GET.get("per_page", "10")
    page_number = request.GET.get("page", "1")

    per_page = per_page_raw if per_page_raw == "all" else int(per_page_raw)

    # ✅ Tenant Isolation (Data Isolation)
    enrolls = Enrollment.objects.filter(student=student).select_related('group')
    if center:
        enrolls = enrolls.filter(group__center=center)

    led_qs = (
        Ledger.objects
        .filter(student=student)
    )
    if center:
        led_qs = led_qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))

    led_qs = (
        led_qs
        .select_related('group', 'rule', 'beruvchi')
        .order_by('-created_at')
    )

    # ✅ Umumiy totals
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
    if not _is_staff_role(request.user):
        return HttpResponse("Ruxsat yo'q", status=403)

    center = get_active_center(request)
    group_qs = Group.objects.all()
    if center and not request.user.is_superuser:
        group_qs = group_qs.filter(center=center)
    if getattr(request.user, "role", None) == "teacher" and not request.user.is_superuser:
        group_qs = group_qs.filter(oqituvchi=request.user)
    group = get_object_or_404(group_qs, pk=group_id)

    enrolls = (
        Enrollment.objects
        .filter(group=group)
        .select_related('student')
        .order_by('student__ism', 'student__familya')
    )
    options = ['<option value="">---------</option>']
    for e in enrolls:
        options.append(f'<option value="{e.student_id}">{e.student.ism} {e.student.familya}</option>')
    return HttpResponse("".join(options))

@login_required
def students_json(request):
    if not _is_staff_role(request.user):
        return JsonResponse({"students": []}, status=403)

    center = get_active_center(request)
    gid = request.GET.get('group')
    qs = _student_scope(center)

    if gid:
        group_qs = Group.objects.all()
        if center and not request.user.is_superuser:
            group_qs = group_qs.filter(center=center)
        if getattr(request.user, "role", None) == "teacher" and not request.user.is_superuser:
            group_qs = group_qs.filter(oqituvchi=request.user)
        group = group_qs.filter(pk=gid).first()
        if not group:
            return JsonResponse({"students": []})
        qs = qs.filter(id__in=Enrollment.objects.filter(group=group).values_list("student_id", flat=True))

    data = [{'id': u.id, 'name': f"{u.ism} {u.familya}"} for u in qs.order_by('ism','familya').distinct()]
    return JsonResponse({'students': data})
from datetime import date

@login_required
def berish(request):
    if not _is_staff_role(request.user):
        messages.error(request, "Sizda chaqmoq berish ruxsati yo'q.")
        return redirect("core:home")

    # ✅ Tenant isolation
    center = get_active_center(request)
    groups = _group_scope_for_user(request.user, center)
    rules = _rule_scope_for_user(request.user, center).order_by("nom")

    selected_gid = request.GET.get('group') or request.POST.get('group')
    selected_group = None
    if selected_gid:
        selected_group = groups.filter(pk=selected_gid).first()
        if not selected_group:
            messages.error(request, "Tanlangan guruhga ruxsat yo'q.")
            selected_gid = ""

    # Faqat studentlarni chiqaramiz
    students = _student_scope(center).none()
    if selected_group:
        students = _student_scope(center).filter(
            id__in=Enrollment.objects.filter(group=selected_group).values_list("student_id", flat=True)
        )
    elif getattr(request.user, "role", None) == "teacher" and not request.user.is_superuser:
        students = _student_scope(center).filter(
            id__in=Enrollment.objects.filter(group__oqituvchi=request.user).values_list("student_id", flat=True)
        )
    else:
        students = _student_scope(center)
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
        student_qs = _student_scope(center)
        if selected_group:
            student_qs = student_qs.filter(
                id__in=Enrollment.objects.filter(group=selected_group).values_list("student_id", flat=True)
            )
        elif getattr(request.user, "role", None) == "teacher" and not request.user.is_superuser:
            student_qs = student_qs.filter(
                id__in=Enrollment.objects.filter(group__oqituvchi=request.user).values_list("student_id", flat=True)
            )
        student = get_object_or_404(student_qs, pk=student_id)
        rule = get_object_or_404(_rule_scope_for_user(request.user, center), pk=rule_id)

        abs_ball = abs(raw_ball)
        if abs_ball < rule.min_baho or abs_ball > rule.max_baho:
            messages.error(
                request, f"Ball {rule.min_baho}..{rule.max_baho} oralig‘ida bo‘lishi kerak."
            )
            return redirect(f"{request.path}?group={selected_gid or ''}")

        # Ballni belgilang (+ yoki -)
        signed = abs_ball if rule.tur == Rule.PLUS else -abs_ball
        group = selected_group

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


        # 🔹 Kunlik limit tekshiruvi (tanlangan sana bo'yicha, har o'quvchi uchun)
        _allowed, _remaining, _limit = Ledger.daily_limit_check(
            student.id, center, signed, on_date=tanlangan_sana.date()
        )
        if not _allowed:
            _act = "olishi" if signed > 0 else "yo'qotishi"
            messages.error(
                request,
                f"Kunlik limit: {student.ism} {tanlangan_sana.date()} kuni ko'pi bilan "
                f"{_limit} chaqmoq {_act} mumkin. Qolgan: {_remaining}.",
            )
            return redirect(f"{request.path}?group={selected_gid or ''}")

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
        teacher_stats_qs = teacher_stats_qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))
    
    teacher_stats = (
        teacher_stats_qs
        .values("beruvchi__id", "beruvchi__ism", "beruvchi__familya", "beruvchi__role")
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
        totals_qs = totals_qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))

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
        led_qs = led_qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))

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

    all_rules = Rule.objects.all()
    if center:
        all_rules = all_rules.filter(center=center)
    else:
        all_rules = all_rules.filter(center__isnull=True)

    # Regular rules (plus / minus only)
    rules = all_rules.filter(tur__in=[Rule.PLUS, Rule.MINUS]).order_by('tur') # simple order

    # Attendance Penalty & Bonus rules separately
    penalty_rules = all_rules.filter(tur=Rule.ATTENDANCE_PENALTY)
    bonus_rules   = all_rules.filter(tur=Rule.ATTENDANCE_BONUS)
    
    # Payment Discipline rule (only one should be active/main)
    discipline_rule = all_rules.filter(tur=Rule.PAYMENT_DISCIPLINE).first()

    context = {
        'center': center,
        'rules': rules,
        'penalty_rules': penalty_rules,
        'bonus_rules': bonus_rules,
        'discipline_rule': discipline_rule,
        'Rule': Rule,
        "center_limit": center.max_daily_lightning if center else 0,
        "center_deduction_limit": center.max_daily_deduction if center else 0,
    }
    return render(request, "chaqmoq/rule_settings.html", context)


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
def penalty_rule_save(request):
    """Davomat jarimasi qoidasini inline saqlash yoki yangilash."""
    center = get_active_center(request)
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo'q")
        return redirect("chaqmoq:rule_list")

    if request.method != "POST":
        return redirect("chaqmoq:rule_list")

    try:
        rule_id  = request.POST.get("rule_id") or None
        tur      = request.POST.get("tur") or Rule.ATTENDANCE_PENALTY
        nom      = request.POST.get("nom", "").strip() or ("Davomat jarimasi" if tur == Rule.ATTENDANCE_PENALTY else "Davomat bonusi")
        
        # Limit va Qiymat turga qarab olinadi
        if tur == Rule.ATTENDANCE_BONUS:
            limit    = int(request.POST.get("presence_limit", 12))
            points   = int(request.POST.get("lightning_bonus", 10))
            if points < 0: points = abs(points) # bonus doim musbat
        else:
            limit    = int(request.POST.get("absence_limit", 3))
            points   = int(request.POST.get("lightning_penalty", -5))
            if points > 0: points = -points # jarima doim manfiy

        if rule_id:
            ruleobj = Rule.objects.get(id=rule_id, center=center)
        else:
            ruleobj = Rule(center=center, tur=tur)

        ruleobj.nom = nom
        if tur == Rule.ATTENDANCE_BONUS:
            ruleobj.presence_limit = limit
            ruleobj.lightning_bonus = points
        else:
            ruleobj.absence_limit = limit
            ruleobj.lightning_penalty = points
        
        ruleobj.period = 'monthly'
        ruleobj.save()
        messages.success(request, f"Davomat qoidasi saqlandi ✅")
    except Exception as e:
        messages.error(request, f"Xato: {str(e)}")

    return redirect("chaqmoq:rule_list")


@login_required
def penalty_rule_delete(request, pk):
    """Davomat jarimasi qoidasini o'chirish."""
    center = get_active_center(request)
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo'q")
        return redirect("chaqmoq:rule_list")

    try:
        rule = Rule.objects.get(pk=pk, center=center, tur=Rule.ATTENDANCE_PENALTY)
        rule.delete()
        messages.success(request, "Qoida o'chirildi")
    except Rule.DoesNotExist:
        messages.error(request, "Qoida topilmadi")

    return redirect("chaqmoq:rule_list")


@login_required
def discipline_rule_save(request):
    """To'lov intizomi qoidasini saqlash."""
    center = get_active_center(request)
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo'q")
        return redirect("chaqmoq:rule_list")

    if request.method != "POST":
        return redirect("chaqmoq:rule_list")

    try:
        rule_id = request.POST.get("rule_id") or None
        nom = request.POST.get("nom", "").strip() or "To‘lov intizomi"
        deadline_day = int(request.POST.get("discipline_deadline_day", 10))
        bonus = int(request.POST.get("discipline_bonus_score", 5))
        penalty = int(request.POST.get("discipline_penalty_score", -10))
        is_active = request.POST.get("discipline_active") == "on"

        if rule_id:
            ruleobj = Rule.objects.get(id=rule_id, center=center, tur=Rule.PAYMENT_DISCIPLINE)
        else:
            # Markazda faqat bitta payment_discipline qoidasi bo'lishi kerak
            ruleobj = Rule.objects.filter(center=center, tur=Rule.PAYMENT_DISCIPLINE).first()
            if not ruleobj:
                ruleobj = Rule(center=center, tur=Rule.PAYMENT_DISCIPLINE)

        ruleobj.nom = nom
        ruleobj.discipline_deadline_day = deadline_day
        ruleobj.discipline_bonus_score = abs(bonus)
        ruleobj.discipline_penalty_score = -abs(penalty) # har doim manfiy
        ruleobj.discipline_active = is_active
        ruleobj.save()
        
        messages.success(request, f"To'lov intizomi qoidasi yangilandi ✅")
    except Exception as e:
        messages.error(request, f"Xato: {str(e)}")

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
