"""
Auto-split from education/views.py (phase 7 god-file reduction).
Public API re-exported via education.views package.
"""
from __future__ import annotations

from .common import *  # noqa: F403


@login_required
def attendance_groups(request):
    q = (request.GET.get("q") or "").strip()
    
    # If the user is a teacher, force them to only see their own groups
    is_teacher = getattr(request.user, 'role', '') == 'teacher'
    if is_teacher:
        teacher_id = request.user.id
    else:
        teacher_id = _get_int(request.GET, "teacher", 0)


    # ✅ Teacher dropdown uchun
    teacher_qs = User.objects.filter(role="teacher").order_by("ism", "familya")
    
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        teacher_qs = teacher_qs.filter(center=center)
        
    teachers = teacher_qs

    # ✅ Base queryset — attendance_count limited to last 90 days for speed
    _att_since = date.today() - timedelta(days=90)
    groups = (
        Group.objects.filter(is_archived=False)
        .select_related("center", "oqituvchi")
        .annotate(
            attendance_count=Count(
                "attendances",
                filter=Q(attendances__date__gte=_att_since),
                distinct=True,
            ),
            last_attendance=Max("attendances__date"),
        )
        .annotate(
            has_attendance=Case(
                When(attendance_count__gt=0, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )
    
    if center:
        groups = groups.filter(center=center)

    # ✅ Filter: teacher
    if teacher_id:
        if is_teacher:
            # Support teacher ham o'z guruhlarini ko'rsin:
            # asosiy o'qituvchi (oqituvchi_id) yoki support sifatida biriktirilgan (support_teacher_id).
            # is_support_enabled tekshiruvi keraksiz — biriktirilgan bo'lsa ko'rishi kerak.
            groups = groups.filter(
                Q(oqituvchi_id=teacher_id) | Q(support_teacher_id=teacher_id)
            )
        else:
            groups = groups.filter(oqituvchi_id=teacher_id)

    # ✅ Search
    if q:
        groups = groups.filter(
            Q(nom__icontains=q) |
            Q(center__name__icontains=q) |
            Q(oqituvchi__ism__icontains=q) |
            Q(oqituvchi__familya__icontains=q)
        )

    # ✅ Davomat qilinganlar tepada, qilinmaganlar pastda
    # -has_attendance: bor guruhlar birinchi
    # last_attendance: oxirgi davomat sanasi eng yangi birinchi
    # nom: qolganlari nom bo'yicha
    groups = groups.order_by(
        "-has_attendance",
        F("last_attendance").desc(nulls_last=True),
        "nom"
    )

    # ✅ Statistikalar (tepada ko'rsatish uchun)
    total = groups.count()
    active_count = groups.filter(attendance_count__gt=0).count()
    inactive_count = total - active_count

    return render(request, "education/attendance_groups.html", {
        "groups": groups,
        "teachers": teachers,
        "selected_teacher": teacher_id,
        "q": q,
        "total": total,
        "active_count": active_count,
        "inactive_count": inactive_count,
    })



@login_required
def group_month_attendance(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    day_list = [first_day + timedelta(days=i) for i in range(days_in_month)]

    from django.db.models import Exists, OuterRef, Q

    has_attendance = Attendance.objects.filter(
        group=group,
        student=OuterRef('student'),
        date__year=year,
        date__month=month
    )

    # all_objects — is_deleted=True (guruhdan o'chirilgan) enrollment'larni ham oladi.
    # Shu oy davomati bo'lgan o'chirilgan o'quvchilar ham ko'rinib turadi.
    enrollments = (
        Enrollment.all_objects
        .filter(group=group)
        .annotate(has_att=Exists(has_attendance))
        .filter(
            Q(is_deleted=False, is_active=True)
            | Q(is_deleted=False, is_active=False, has_att=True)
            | Q(is_deleted=True, has_att=True)
        )
        .select_related("student", "group")
        .order_by("student__ism", "student__familya")
    )
    students = [e.student for e in enrollments]

    qs = Attendance.objects.filter(group=group).select_related("student")

    agg = qs.aggregate(min_date=Min("date"), max_date=Max("date"))
    if agg["min_date"] and agg["max_date"]:
        start_year = agg["min_date"].year
        end_year = agg["max_date"].year
    else:
        start_year = year - 1
        end_year = year + 1
    years = list(range(start_year, end_year + 1))


    month_qs = qs.filter(date__year=year, date__month=month)

    att_map = {(a.student_id, a.date): a for a in month_qs}

    rows = []
    for student in students:
        cells = []
        present_count = 0
        absent_count = 0
        forced_count = 0

        for d in day_list:
            a = att_map.get((student.id, d))
            if not a:
                status = "none"
            elif getattr(a, "present", False):
                status = "present"
                present_count += 1
            elif getattr(a, "status", None) == "absent_excused":
                # Sababli kelmagan — pul yozilmaydi
                status = "absent_excused"
                forced_count += 1
            elif getattr(a, "forced", False):
                # Eski "forced" yozuvlar — ko'rsatish uchun saqlanadi
                status = "forced"
                forced_count += 1
            else:
                # Sababsiz kelmagan — pul yoziladi
                status = "absent"
                absent_count += 1

            cells.append({"date": d, "status": status})

        rows.append({
            "student": student,
            "cells": cells,
            "present_count": present_count,
            "absent_count": absent_count,
            "forced_count": forced_count,
        })

    months = [(i, calendar.month_name[i]) for i in range(1, 13)]

    # Ruxsat tekshiruvi: director, manager, teacher — barchasi tahrirlashi mumkin
    user = request.user
    can_edit = (
        user.is_superuser
        or getattr(user, "role", None) in ("director", "manager", "teacher")
    )

    return render(request, "education/group_month_attendance.html", {
        "group": group,
        "rows": rows,
        "days": day_list,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "years": years,
        "months": months,
        "can_edit": can_edit,
    })



@login_required
def group_month_attendance_export(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    day_list = [first_day + timedelta(days=i) for i in range(days_in_month)]

    from django.db.models import Exists, OuterRef, Q

    has_attendance = Attendance.objects.filter(
        group=group,
        student=OuterRef('student'),
        date__year=year,
        date__month=month
    )

    enrollments = (
        Enrollment.all_objects
        .filter(group=group)
        .annotate(has_att=Exists(has_attendance))
        .filter(
            Q(is_deleted=False, is_active=True)
            | Q(is_deleted=False, is_active=False, has_att=True)
            | Q(is_deleted=True, has_att=True)
        )
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    students = [e.student for e in enrollments]

    month_qs = (Attendance.objects
                .filter(group=group, date__year=year, date__month=month)
                .select_related("student"))

    att_map = {(a.student_id, a.date): a for a in month_qs}

    # ✅ Excel uchun UTF-8 BOM
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    safe_group_name = "".join(ch for ch in (group.nom or "") if ch.isalnum() or ch in ("-", "_", " "))
    safe_group_name = safe_group_name.strip() or f"group-{group.id}"
    filename = f"{safe_group_name}_{year}-{month:02d}_attendance.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    # ✅ MUHIM: delimiter=';' (Excel RU/UZ)
    writer = csv.writer(response, delimiter=';', lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

    def _csv_safe(value):
        text = "" if value is None else str(value)
        if text.startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text

    header = ["O'quvchi"] + [d.strftime("%d-%m-%Y") for d in day_list]
    writer.writerow(header)

    for s in students:
        row = [_csv_safe(s.get_full_name())]
        for d in day_list:
            a = att_map.get((s.id, d))
            if not a:
                row.append("")  # belgilanmagan
            elif getattr(a, "present", False):
                row.append("KELDI")
            elif getattr(a, "forced", False):
                row.append("KELMADI (PUL)")
            else:
                row.append("KELMADI")
        writer.writerow(row)

    return response



@require_POST
@login_required
def attendance_toggle_cell(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    # Ruxsat tekshiruvi: director, manager, teacher — barchasi tahrirlashi mumkin
    user = request.user
    is_allowed = (
        user.is_superuser
        or getattr(user, "role", None) in ("director", "manager", "teacher")
    )
    if not is_allowed:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    student_id = request.POST.get("student_id")
    date_str = request.POST.get("date")
    target_status = request.POST.get("target_status")   # new: direct set from popover
    current_status = request.POST.get("status", "none")  # legacy cycle fallback

    d = parse_date(date_str)
    if not d or not student_id:
        return JsonResponse({"ok": False, "error": "Bad data"}, status=400)

    user_qs = User.objects.filter(role="student")
    if center:
        user_qs = user_qs.filter(center=center)

    student = get_object_or_404(user_qs, pk=student_id)

    att = Attendance.objects.filter(group=group, student=student, date=d).first()

    def _prepare_att():
        nonlocal att
        if not att:
            att = Attendance(group=group, student=student, date=d)
            if hasattr(att, "center"):
                att.center = group.center
        if not getattr(att, "teacher_id", None) and getattr(group, "oqituvchi_id", None):
            att.teacher = group.oqituvchi
        return att

    # --- Direct set mode (from popover) ---
    if target_status in ("present", "absent", "excused", "none"):
        if target_status == "none":
            if att:
                att.delete()
            return JsonResponse({"ok": True, "status": "none"})

        att = _prepare_att()
        if target_status == "present":
            att.present = True
            att.forced = False
            if hasattr(att, "status"):
                att.status = "present"
        elif target_status == "absent":
            # Sababsiz kelmagan — pul yoziladi
            att.present = False
            att.forced = False
            if hasattr(att, "status"):
                att.status = "absent_unexcused"
        elif target_status == "excused":
            # Sababli kelmagan — pul yozilmaydi
            att.present = False
            att.forced = False
            if hasattr(att, "status"):
                att.status = "absent_excused"
        att.save()
        # excused → display status is "absent_excused"
        display = "absent_excused" if target_status == "excused" else target_status
        return JsonResponse({"ok": True, "status": display})

    # --- Legacy cycle mode (backward compat) ---
    if current_status == "none":
        att = _prepare_att()
        att.present = True
        att.forced = False
        att.save()
        new_status = "present"

    elif current_status == "present":
        att = _prepare_att()
        att.present = False
        att.forced = False
        att.save()
        new_status = "absent"

    elif current_status == "absent":
        if att:
            att.delete()
        new_status = "none"

    elif current_status == "forced":
        if att:
            att.delete()
        new_status = "none"

    else:
        new_status = current_status or "none"

    return JsonResponse({"ok": True, "status": new_status})



@login_required
def points_details(request):
    student_id = request.GET.get("student")
    date_str = request.GET.get("date")
    type_ = request.GET.get("type", "plus")

    if not student_id or not date_str:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()), tz)
    end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()), tz)

    qs = Ledger.objects.filter(student_id=student_id, sana__range=(start, end))
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        qs = qs.filter(student__center=center)

    if type_ == "plus":
        qs = qs.filter(ball__gt=0)
    elif type_ == "minus":
        qs = qs.filter(ball__lt=0)

    details = []
    for l in qs.order_by("-sana"):
        show_dt = getattr(l, "created_at", None) or l.sana
        local_dt = timezone.localtime(show_dt, tz)
        tm = local_dt.strftime("%H:%M | %d-%b-%Y")

        details.append({
            "amount": l.ball,
            "rule": str(l.rule) if l.rule else "",
            "reason": getattr(l.rule, "izoh", "") if hasattr(l.rule, "izoh") else "",
            "teacher": str(l.beruvchi) if l.beruvchi else "",
            "group": str(l.group) if l.group else "",
            "time": tm,
        })

    return JsonResponse({"details": details})



@login_required
@require_POST
def attendance_force(request):
    """
    Tanlangan guruh va sana bo'yicha:
    ✅ kelmagan (present=False) o'quvchilar uchun
    forced=True qilib, o'qituvchiga pul yoziladigan dars sifatida belgilaydi.

    Frontend POST yuboradi:
      - group_id
      - date (YYYY-MM-DD)
    """
    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    # 🔴 JS dagi xabardagi "Ma'lumot yetarli emas" — mana shu joydan keladi
    if not group_id or not date_str:
        return JsonResponse({"ok": False, "error": "Maʼlumot yetarli emas"})

    date_obj = parse_date(date_str)
    if not date_obj:
        return JsonResponse({"ok": False, "error": "Sana noto'g'ri formatda"})

    # Guruhni olamiz
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=group_id)

    # Shu guruhdagi barcha faol enrollments (arxivlanganlar istisno)
    enrollments = Enrollment.objects.filter(group=g, is_active=True).select_related("student")

    # Shu sana uchun mavjud attendance yozuvlari
    att_qs = Attendance.objects.filter(group=g, date=date_obj)
    att_by_student = {a.student_id: a for a in att_qs}

    forced_count = 0

    for enr in enrollments:
        att = att_by_student.get(enr.student_id)

        if att:
            # Agar allaqachon present=True bo'lsa, buni majburan "kelmadi" qilishni xohlamaymiz
            # (agar kerak bo'lsa, bu qismni o'zing o'zgartirasan)
            if att.present:
                continue

            if not att.forced:
                att.forced = True
                att.present = False  # forced bo'lsa ham uni "kelmadi" deb saqlab qo'yamiz
                att.save()
                forced_count += 1
        else:
            # Hech qanday attendance yo'q bo'lsa, yangi "kelmadi, forced" yozuvi yaratamiz
            Attendance.objects.create(
                group=g,
                student=enr.student,
                teacher=g.oqituvchi,
                date=date_obj,
                present=False,
                forced=True,
                center=g.center if hasattr(Attendance, 'center') else None
            )
            forced_count += 1

    return JsonResponse({
        "ok": True,
        "count": forced_count,
    })



@login_required
def attend_all(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"})

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # faqat direktor/manager/teacher yoki support teacher
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        if g.support_teacher_id != request.user.id:
            return JsonResponse({"ok": False, "error": "ruxsat yo'q"})

    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    students = Enrollment.objects.filter(group=g, is_active=True).select_related("student")
    count = 0

    for e in students:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True, "forced": False, "status": "present", "teacher": request.user}
        )
        count += 1

    return JsonResponse({"ok": True, "count": count})



@require_POST
@login_required
def attend_all_students(request, g_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=g_id)

    if request.user.role == "teacher" and g.oqituvchi != request.user:
        if g.support_teacher_id != request.user.id:
            return JsonResponse({"ok": False, "error": "ruxsat yo'q"})

    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    enrollments = Enrollment.objects.filter(group=g, is_active=True).select_related("student")

    items = []
    count = 0

    for e in enrollments:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True, "forced": False, "status": "present", "teacher": request.user, "center": g.center, "created_by": request.user},
        )
        balance = Ledger.student_balansi(e.student.id, center=g.center)

        items.append({"student_id": e.student.id, "balance": balance, "restored_sum": 0})
        count += 1

    return JsonResponse({"ok": True, "count": count, "items": items})



# ---------- AJAX: Davomatni saqlash ----------
@require_POST
@login_required
def attendance_today(request, pk: int):
    """
    status:
      - 'present'          -> present=True,  forced=False, status='present'
      - 'absent_excused'   -> present=False, forced=False, status='absent_excused'   (sababli)
      - 'absent_unexcused' -> present=False, forced=False, status='absent_unexcused' (sababsiz) + Rule Engine
      - 'forced'           -> present=False, forced=True,  status='absent_unexcused' (eski logika saqlanadi)
      - 'none'             -> attendance yozuvi o'chiriladi
    Backward compatible: present=1/0 yuborilsa ham ishlaydi.
    """
    from core.tenant import get_request_center, get_tenant_object_or_404

    # Tenant-scoped: boshqa markaz guruhiga 404 (IDOR / center mismatch).
    g = get_tenant_object_or_404(Group, request, pk=pk)
    center = get_request_center(request)

    # faqat direktor/manager/teacher yoki support teacher
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        if g.support_teacher_id != request.user.id:
            return JsonResponse({"ok": False, "error": "ruxsat yo'q"}, status=403)

    enr_id = request.POST.get("enr_id")
    if not enr_id:
        return JsonResponse({"ok": False, "error": "enr_id required"}, status=400)

    # sana
    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    # status (yangi: 5 ta holat)
    status = (request.POST.get("status") or "").strip().lower()

    VALID_STATUSES = ("present", "absent_excused", "absent_unexcused", "forced", "late", "none")

    # backward compatibility (eski front bo'lsa)
    if status not in VALID_STATUSES:
        pv = request.POST.get("present")
        if pv is None:
            return JsonResponse({"ok": False, "error": "status/present required"}, status=400)
        status = "present" if str(pv).lower() in ("1", "true", "yes", "on") else "none"

    e = get_object_or_404(Enrollment, id=enr_id, group=g)
    student = e.student

    removed_sum = 0
    removed_count = 0
    penalized = False
    bonused = False

    # ── Attendance ni yaratish/yangilash/o'chirish ──
    present = False
    forced = False

    if status == "none":
        Attendance.objects.filter(group=g, student=student, date=selected_date).delete()
    else:
        # qolgan statuslar uchun update_or_create
        present = (status == "present")
        forced = (status == "forced")
        Attendance.objects.update_or_create(
            group=g, student=student, date=selected_date,
            defaults={
                "teacher": request.user,
                "present": present,
                "forced": forced,
                "status": status,
                "center": g.center,
                "created_by": request.user,
            }
        )

    # yangi balans
    bal = Ledger.student_balansi(student.id, center=g.center)

    return JsonResponse({
        "ok": True,
        "status": status,
        "present": present,
        "forced": forced,
        "removed_sum": removed_sum,
        "removed_count": removed_count,
        "balance": bal,
        "penalty_applied": penalized,
        "bonus_applied": bonused,
    })



# ---------- AJAX: Chaqmoq yozish/ayirish ----------
@login_required
def group_points(request, pk: int):
    """
    Apply rules to students (points system) with proper Student-User link handling.
    """
    try:
        from django.db import transaction
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        from education.models import Enrollment, Group
        from chaqmoq.models import Ledger, Rule
        from accounts.models import User

        if request.method != "POST":
            return JsonResponse({"status": "error", "message": "Method not allowed"}, status=200)

        # 1. Parse Data
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        student_id = data.get("student_id")
        rule_id = data.get("rule_id")
        amount = int(data.get("amount", 0))
        date_str = data.get("date")

        if not student_id:
            return JsonResponse({"status": "error", "message": "O'quvchi tanlanmagan"}, status=200)

        # 2. Student & Group Lookup (Safe search)
        # Guruhni topish
        g = Group.objects.filter(pk=pk).first()
        if not g:
            return JsonResponse({"status": "error", "message": "Guruh topilmadi"}, status=200)

        # O'quvchini bevosita User modeli orqali topamiz.
        # Agar bu yerda Enrollment bo'yicha qidirsak, bir xil ID ga ega boshqa o'quvchi
        # tanlanib qolishi va "refresh davomida points yo'qolish" muammosi yuzaga keladi.
        student_user = User.objects.filter(pk=student_id, role='student').first()

        if not student_user:
             # Senior Senior Senior logic: Agar o'quvchi topilmasa, qizil xato chiqarmaslik uchun
             # status: success qaytaramiz, lekin message bermaymiz.
             return JsonResponse({"status": "success", "message": "", "ok": True}, status=200)

        # 3. Rule Handling
        if rule_id and str(rule_id).isdigit():
            rule = Rule.objects.filter(pk=rule_id).first()
        else:
            rule = None
            
        if not rule:
            rule = Rule.objects.filter(nom="Erkin ball", center=g.center).first()
            if not rule:
                rule = Rule.objects.create(
                    nom="Erkin ball", tur=Rule.PLUS, min_baho=1, max_baho=1000000, center=g.center
                )

        # 4. Date processing
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()
        now_time = timezone.localtime(timezone.now()).time()
        sana = timezone.make_aware(datetime.combine(parsed_date, now_time))

        request_id = data.get("request_id", "")
        from django.core.cache import cache
        cache_key = f"ledger_req_{request_id}" if request_id else None

        # ✅ DATABASE-LEVEL LOCK bilan idempotency
        # select_for_update() - parallel workerlar (gunicorn) bir vaqtda create qilishini oldini oladi
        with transaction.atomic():
            # Lock: bir vaqtda faqat bitta worker shu student uchun ishlay oladi
            # Render.com dagi parallel workerlar yaratishda "phantom read" muammosini oldini olish
            # uchun Ledger ni emas (u hali yo'q bo'lishi mumkin), aynan User ni qulflaymiz
            _lock_student = User.objects.select_for_update().get(id=student_user.id)

            # ✅ 1-HIMOYA: Lock olingach yana Cache ni tekshirish.
            if cache_key:
                cached = cache.get(cache_key)
                if cached:
                    return JsonResponse(cached)



            # Yangi yozuv yaratish
            record = Ledger.objects.create(
                student=student_user,
                beruvchi=request.user,
                group=g,
                rule=rule,
                ball=amount,
                sana=sana,
            )

            from chaqmoq.models import LightningHistory
            from education.models import Student as EdStudent
            st_model, _ = EdStudent.objects.get_or_create(user=student_user)
            LightningHistory.objects.create(
                student=st_model,
                points=amount,
                reason=rule.nom if rule else "Erkin ball",
                source="manual",
                teacher=request.user
            )
            _accumulate_daily_lightning(
                group=g,
                student=student_user,
                date_value=parsed_date,
                points_delta=amount,
            )

            # Yangi balansni hisoblash
            balance = Ledger.student_balansi(student_user.id, center=g.center)

        response_data = {
            "status": "success",
            "message": "Ball saqlandi",
            "balance": int(balance),
            "amount": amount,
            "id": record.id,
            "ok": True
        }

        # ✅ Muvaffaqiyatli response ni cache ga yozamiz (60 soniya)
        # Xuddi shu request_id qayta kelsa - yangi yozuv yaratilmaydi
        if request_id:
            from django.core.cache import cache
            cache.set(f"ledger_req_{request_id}", response_data, timeout=60)

        return JsonResponse(response_data)

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Points logic error")
        return JsonResponse({
            "status": "error",
            "message": f"Serverda xato yuz berdi: {str(e)}"
        }, status=200) # Toast qizil chiqmasligi uchun 200 qaytaramiz (JSON error ichida bo'ladi)



# ---------- (ixtiyoriy) alohida Davomat/Chaqmoq sahifasi ----------
@login_required
def group_rollcall(request, pk):
    from core.tenant import get_tenant_object_or_404

    g = get_tenant_object_or_404(Group, request, pk=pk)
    if not _can_give_points(request.user, g):
        return HttpResponseForbidden()

    # sana
    date_str = request.GET.get("date") or request.POST.get("date")
    try:
        the_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else localdate()
    except Exception:
        the_date = localdate()

    from django.db.models import Exists, OuterRef, Q

    has_attendance = Attendance.objects.filter(
        group=g,
        student=OuterRef('student'),
        date__year=the_date.year,
        date__month=the_date.month
    )
    enrollments_qs = (
        Enrollment.objects
        .filter(group=g)
        .annotate(has_att=Exists(has_attendance))
        .filter(Q(is_active=True) | Q(is_active=False, has_att=True))
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    students = [e.student for e in enrollments_qs]

    pres_map = {
        a.student_id: a.present for a in Attendance.objects.filter(group=g, date=the_date)
    }
    for s in students:
        s.present = pres_map.get(s.id, False)
        s.balance = Ledger.student_balansi(s.id, center=g.center)

    rules = Rule.objects.order_by("nom")

    if request.method == "POST" and request.POST.get("save") == "1":
        saved = 0
        for s in students:
            present = bool(request.POST.get(f"present_{s.id}"))
            Attendance.objects.update_or_create(
                group=g,
                student=s,
                date=the_date,
                defaults={"present": present, "teacher": request.user if request.user.role == "teacher" else None},
            )
            rule_id = request.POST.get(f"rule_{s.id}")
            amount_raw = request.POST.get(f"ball_{s.id}") or "0"
            try:
                amount = int(amount_raw)
            except ValueError:
                amount = 0
            if rule_id and amount:
                rule = get_object_or_404(Rule, pk=int(rule_id))
                abs_ball = abs(amount)
                if rule.min_baho <= abs_ball <= rule.max_baho:
                    signed = abs_ball if rule.tur == Rule.PLUS else -abs_ball
                    now_local = timezone.localtime(timezone.now()).time()
                    sana = timezone.make_aware(datetime.combine(the_date, now_local))
                    Ledger.objects.create(student=s, beruvchi=request.user, group=g, rule=rule, ball=signed, sana=sana)
                    
                    from chaqmoq.models import LightningHistory
                    from education.models import Student as EdStudent
                    st_model, _ = EdStudent.objects.get_or_create(user=s)
                    LightningHistory.objects.create(
                        student=st_model,
                        points=signed,
                        reason=rule.nom if rule else "Manual ball",
                        source="manual",
                        teacher=request.user
                    )
                    saved += 1
        messages.success(request, f"Saqlash tugadi. {saved} ta chaqmoq yozildi.")
        return redirect(f"{request.path}?date={the_date.isoformat()}")

    return render(
        request,
        "education/group_rollcall.html",
        {"g": g, "date": the_date.isoformat(), "students": students, "rules": rules},
    )



@login_required
def force_absent_attendance(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=group_id)

    date = parse_date(date_str)

    enrollments = Enrollment.objects.filter(group=group, is_active=True)
    forced_count = 0

    for enr in enrollments:
        att, created = Attendance.objects.get_or_create(
            group=group,
            student=enr.student,
            date=date,
            defaults={"present": False}
        )

        # kelgan bo'lsa — forced qilmaymiz
        if att.present:
            continue

        # forced=True qilamiz
        if not att.forced:
            att.forced = True
            att.save()
            forced_count += 1

    return JsonResponse({"ok": True, "count": forced_count})



@require_POST
def toggle_attendance(request):
    student_id = request.POST.get("student_id")
    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    if not (student_id and group_id):
        return JsonResponse({"error": "Invalid data"}, status=400)

    date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()

    att, created = Attendance.objects.get_or_create(
        group_id=group_id,
        student_id=student_id,
        date=date,
        defaults={"teacher": request.user}
    )
    # Validate center
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center and att.group.center_id != center.id:
        return JsonResponse({"error": "Center mismatch"}, status=403)

    # Belgini o'zgartiramiz (agar bor bo'lsa)
    att.present = not att.present
    att.teacher = request.user
    att.save()

    return JsonResponse({
        "success": True,
        "present": att.present,
        "date": att.date.strftime("%Y-%m-%d"),
    })

