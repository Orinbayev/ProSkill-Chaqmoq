"""
Auto-split from education/views.py (phase 7 god-file reduction).
Public API re-exported via education.views package.
"""
from __future__ import annotations

from .common import *  # noqa: F403


# ---------- HUB va ro'yxatlar ----------
@login_required
def groups_hub(request):
    """
    📘 Guruhlar markaziy sahifasi — barcha kategoriyalar ro'yxati.
    """
    from ..models import Category  # agar alohida model bo'lsa
    categories = Category.objects.all() if hasattr(Category, "objects") else []
    return render(request, "education/groups_home.html", {
        "categories": categories,
    })



def group_delete_confirm(request, id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=id)
    if request.method == "POST":
        group.delete(deleted_by=request.user)
        return redirect("education:groups_home")
    return render(request, "education/group_delete_confirm.html", {"g": group})



@login_required
def edit_category(request, id):
    # ✅ Strict isolation: Only the center's own or global (if primary center)
    from core.tenant import get_request_center
    center = get_request_center(request)
    first_center = Center.objects.order_by("id").first()
    
    if first_center and center and center.id == first_center.id:
        # Primary center can edit its own and global orphans
        cat = get_object_or_404(Category, Q(center=center) | Q(center__isnull=True), id=id)
    else:
        # Other centers can only edit their own
        cat = get_object_or_404(Category, center=center, id=id)
        
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")

        name_stripped = (name or "").strip()
        if not name_stripped:
            messages.error(request, "Bo'lim nomi bo'sh bo'lishi mumkin emas!")
            return render(request, "education/category_edit.html", {"cat": cat})

        # Check for duplication (case-insensitive, same center, including soft-deleted)
        qs = Category.all_objects.filter(name__iexact=name_stripped, center=cat.center).exclude(id=cat.id)
        if qs.exists():
            messages.error(request, "Ushbu nomdagi bo'lim allaqachon mavjud!")
            return render(request, "education/category_edit.html", {"cat": cat})

        cat.name = name_stripped
        cat.description = description

        # 🔹 Agar yangi rasm tanlangan bo'lsa, yangisini saqlaymiz
        if image:
            cat.image = image

        cat.save()
        messages.success(request, "Bo'lim muvaffaqiyatli tahrirlandi ✅")
        return redirect("education:groups_home")

    return render(request, "education/category_edit.html", {"cat": cat})



@login_required
def delete_category(request, id):
    # ✅ Strict isolation: Only the center's own or global (if primary center)
    from core.tenant import get_request_center
    center = get_request_center(request)
    first_center = Center.objects.order_by("id").first()
    
    if first_center and center and center.id == first_center.id:
        cat = get_object_or_404(Category, Q(center=center) | Q(center__isnull=True), id=id)
    else:
        cat = get_object_or_404(Category, center=center, id=id)

    if request.method == "POST":
        cat.delete(deleted_by=request.user)
        messages.success(request, "Bo'lim o'chirildi 🗑️")
        return redirect("education:groups_home")
    return render(request, "education/category_delete_confirm.html", {"cat": cat})



@login_required
def groups_by_category(request, category):
    if category not in ("lang", "it"):
        raise Http404("Noto'g'ri kategoriya")

    rows = (
        Group.objects.filter(category=category)
        .select_related("center", "oqituvchi")
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)),
            sana=Coalesce(F("course_start_date"), Cast(F("tuzilgan"), models.DateField()))
        )
        .order_by("nom")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)
    return render(
        request,
        "education/groups_by_category.html",
        {"rows": rows, "category": category, "can_manage": _can_manage(request.user)},
    )



# DRY: guruh yaratish
@login_required
def create_group_for_category(request, category_id):
    from core.tenant import get_request_center, get_tenant_object_or_404

    # Global (center=NULL) yoki shu markaz category — boshqa markazniki 404.
    category = get_tenant_object_or_404(
        Category, request, id=category_id, allow_global=True
    )
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo'q.")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)

            # 🟢 To'g'ri maydon: ForeignKey bo'lgan 'category_obj'
            group.category_obj = category

            # Center assignment
            center = get_request_center(request)
            if center:
                group.center = center

            # Eski 'category' maydoni ham to'ldirilsa yaxshi
            group.category = Group.IT  # yoki Group.LANG — kerakli turga qarab
            group.save()

            messages.success(request, f"✅ '{group.nom}' guruhi {category.name} bo'limiga qo'shildi.")
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm()

    from core.tenant import get_request_center as _grc
    _center = _grc(request)
    _cts = CourseTemplate.objects.filter(center=_center, is_active=True).order_by("name") if _center else []
    return render(request, "education/group_form.html", {
        "form": form, "category": category, "course_templates": _cts,
    })



# (eski ro'yxatlar kerak bo'lsa)
@login_required
def guruhlar(request):
    rows = (
        Group.objects.select_related("center", "oqituvchi")
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)),
            sana=Coalesce(F("course_start_date"), Cast(F("tuzilgan"), models.DateField()))
        )
        .order_by("nom")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)
    return render(request, "education/groups.html", {"rows": rows, "can_manage": _can_manage(request.user)})



@login_required
def guruhlar_tillar(request):
    return groups_by_category(request, Group.LANG)



@login_required
def guruhlar_it(request):
    return groups_by_category(request, Group.IT)



# ---------- Bitta guruh (bitta sahifada hamma narsa) ----------
@login_required
def group_detail(request, pk: int):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    if request.user.role == "teacher" and g.oqituvchi != request.user:
        # Support teacher ham guruhni ko'ra oladi va davomat qila oladi
        if g.support_teacher_id != request.user.id:
            return HttpResponseForbidden("Siz bu guruhni ko'ra olmaysiz.")

    date_str = request.GET.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    if not selected_date:
        selected_date = localdate()
    selected_month = month_first_day(selected_date)

    from django.db.models import Exists, OuterRef, Q

    has_attendance = Attendance.objects.filter(
        group=g,
        student=OuterRef('student'),
        date__year=selected_month.year,
        date__month=selected_month.month
    )
    enrollments = list(
        Enrollment.objects
        .filter(group=g)
        .annotate(has_att=Exists(has_attendance))
        .filter(Q(is_active=True) | Q(is_active=False, has_att=True))
        .select_related("student", "group")   # ✅ MUHIM
        .order_by("student__ism", "student__familya")
    )
    student_user_ids = [e.student_id for e in enrollments]
    # Faqat shu guruh (g) bo'yicha fee/paid hisoblaymiz.
    # Boshqa guruhlarni kiritish studentni boshqa guruhda ortiqcha to'lagan bo'lsa
    # bu guruhda ham "To'langan" ko'rsatishiga olib kelgan — noto'g'ri xatti-harakat.
    student_enrollment_qs = Enrollment.objects.filter(
        student_id__in=student_user_ids,
        group=g,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False,
    ).filter(
        Q(is_active=True) | Q(id__in=[e.id for e in enrollments])
    )
    if center:
        student_enrollment_qs = student_enrollment_qs.filter(center=center)
    student_enrollment_ids = list(student_enrollment_qs.values_list("id", flat=True))

    # Faqat shu guruh bo'yicha tanlangan oy to'lov holatini hisoblaymiz.
    fee_field = tuition_month_fee_field()
    student_enrollments = list(student_enrollment_qs.select_related("group"))
    eligible_enrollment_ids = [enrollment.id for enrollment in student_enrollments]

    from django.utils import timezone as _tz2

    _existing_ids = set(
        TuitionMonth.all_objects.filter(
            enrollment_id__in=eligible_enrollment_ids,
            month=selected_month,
        ).values_list("enrollment_id", flat=True)
    )
    _to_create = []
    for _enr in student_enrollments:
        if _enr.id not in _existing_ids:
            _fee = (
                _enr.student_payable_amount
                if _enr.student_payable_amount not in (None, 0)
                else _enr.kurs_narhi
                or int(getattr(_enr.group, "kurs_narxi", 0) or 0)
            )
            _to_create.append(
                TuitionMonth(
                    enrollment=_enr,
                    center_id=_enr.center_id,
                    month=selected_month,
                    fee_amount=_fee or 0,
                )
            )
    if _to_create:
        TuitionMonth.objects.bulk_create(_to_create, ignore_conflicts=True)
    TuitionMonth.all_objects.filter(
        enrollment_id__in=eligible_enrollment_ids,
        month=selected_month,
        is_deleted=True,
    ).update(is_deleted=False, restored_at=_tz2.now())

    student_total_fee_map = {
        sid: 0 for sid in student_user_ids
    }
    if eligible_enrollment_ids:
        student_total_fee_map.update(
            {
                row["enrollment__student_id"]: int(row["fee"] or 0)
                for row in (
                    TuitionMonth.objects
                    .filter(
                        enrollment_id__in=eligible_enrollment_ids,
                        month=selected_month,
                    )
                    .values("enrollment__student_id")
                    .annotate(fee=Coalesce(Sum(fee_field), 0))
                )
            }
        )

    student_total_paid_map = {
        row["tuition_month__enrollment__student_id"]: int(row["paid"] or 0)
        for row in (
            PaymentAllocation.objects
            .filter(
                tuition_month__enrollment_id__in=eligible_enrollment_ids or student_enrollment_ids,
                tuition_month__month=selected_month,
            )
            .values("tuition_month__enrollment__student_id")
            .annotate(paid=Coalesce(Sum("amount"), 0))
        )
    }

    # Balanslar: avval Ledger, agar studentda umuman Ledger bo'lmasa LightningHistory fallback.
    ledger_qs = Ledger.objects.filter(student_id__in=student_user_ids)
    if center:
        ledger_qs = ledger_qs.filter(
            Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True)
        )
    ledger_balance_map = {
        row["student_id"]: int(row["s"] or 0)
        for row in (
            ledger_qs.values("student_id").annotate(s=Coalesce(Sum("ball"), 0))
        )
    }
    history_balance_map = {}
    missing_balance_user_ids = [sid for sid in student_user_ids if sid not in ledger_balance_map]
    if missing_balance_user_ids:
        from chaqmoq.models import LightningHistory

        student_models = {
            st.user_id: st.id
            for st in Student.objects.filter(user_id__in=missing_balance_user_ids)
        }
        if student_models:
            history_qs = LightningHistory.objects.filter(student_id__in=student_models.values())
            if center:
                history_qs = history_qs.filter(student__user__center=center)
            history_totals = {
                row["student_id"]: int(row["s"] or 0)
                for row in (
                    history_qs.values("student_id").annotate(s=Coalesce(Sum("points"), 0))
                )
            }
            history_balance_map = {
                user_id: history_totals.get(student_pk, 0)
                for user_id, student_pk in student_models.items()
            }

    # Sana bo'yicha Attendance (DateTimeField bo'lsa ham ishlaydi)
    try:
        start = make_aware(datetime.combine(selected_date, datetime.min.time()))
        end   = make_aware(datetime.combine(selected_date + timedelta(days=1),
                                           datetime.min.time()))
        att_qs = Attendance.objects.filter(group=g, date__gte=start, date__lt=end)
    except Exception:
        att_qs = Attendance.objects.filter(group=g, date=selected_date)

    pres_map   = {}
    forced_map = {}
    status_map = {}
    for a in att_qs:
        pres_map[a.student_id]   = a.present
        forced_map[a.student_id] = getattr(a, "forced", False)
        status_map[a.student_id] = getattr(a, "status", "present" if a.present else "none")

    # Studentga soxta fieldlar
    for e in enrollments:
        s = e.student
        s.balance = int(ledger_balance_map.get(s.id, history_balance_map.get(s.id, 0)))
        s.present_today     = bool(pres_map.get(s.id, False))
        s.forced_today      = bool(forced_map.get(s.id, False))
        s.attendance_status = status_map.get(s.id, "none")  # 'present' | 'absent_excused' | 'absent_unexcused' | 'none'

        total_fee = int(student_total_fee_map.get(s.id, 0))
        total_paid = int(student_total_paid_map.get(s.id, 0))
        total_remaining = max(0, total_fee - total_paid)

        if total_fee <= 0 or total_paid >= total_fee:
            payment_status = "paid"
            payment_status_label = "To'liq to'langan"
        elif total_paid > 0:
            payment_status = "partial"
            payment_status_label = "Chala to'langan"
        else:
            payment_status = "unpaid"
            payment_status_label = "To'lov qilinmagan"

        if total_fee <= 0:
            payment_status_title = "Tanlangan oy uchun to'lov majburiyati yo'q"
        elif payment_status == "paid":
            payment_status_title = (
                f"Tanlangan oy uchun to'liq to'langan: {total_paid:,} / {total_fee:,} so'm"
            )
        elif payment_status == "partial":
            payment_status_title = (
                f"Tanlangan oy uchun chala to'langan: {total_paid:,} / {total_fee:,} so'm"
                f" • Qoldiq: {total_remaining:,} so'm"
            )
        else:
            payment_status_title = f"Tanlangan oy uchun to'lov qilinmagan: 0 / {total_fee:,} so'm"

        e.payment_status = payment_status
        e.payment_status_label = payment_status_label
        e.payment_status_title = payment_status_title
        e.payment_month_fee = total_fee
        e.payment_month_paid = total_paid
        e.payment_month_remaining = total_remaining


    can_add_student = False
    can_remove_student = False
    
    if request.user.role == "director" or request.user.is_superuser:
        can_add_student = True
        can_remove_student = True
    elif center:
        if request.user.role == "manager":
            can_add_student = center.manager_can_add_student
            can_remove_student = center.manager_can_remove_student
        elif request.user.role == "teacher":
            can_add_student = center.teacher_can_add_student
            can_remove_student = center.teacher_can_remove_student

    # ✅ Filter rules by center and role
    rules_qs = Rule.objects.filter(Q(center=center) | Q(center__isnull=True))
    if request.user.role == 'teacher':
        rules_qs = rules_qs.filter(can_teacher=True)
    elif request.user.role == 'manager':
        rules_qs = rules_qs.filter(can_manager=True)
    elif request.user.role == 'director':
        rules_qs = rules_qs.filter(can_director=True)

    # Tanlangan sana bo'yicha kunlik chaqmoq o'zgarishlari (student + group + date)
    recent_history = (
        DailyLightningRecord.objects.filter(
            group=g,
            date=selected_date,
            student_id__in=student_user_ids,
        )
        .values("student_id")
        .annotate(
            recent_add=Coalesce(Sum("plus_points"), 0),
            recent_sub=Coalesce(Sum("minus_points"), 0),
        )
    )
    recent_history_map = {
        str(item["student_id"]): {
            "add": int(item["recent_add"] or 0),
            "sub": int(item["recent_sub"] or 0),
        }
        for item in recent_history
        if item["recent_add"] or item["recent_sub"]
    }

    exam_reminder_state = None
    if request.user.role in ("teacher", "director", "manager") or request.user.is_superuser:
        try:
            from education.services.exam_service import get_exam_reminder_state
            exam_reminder_state = get_exam_reminder_state(
                group=g,
                on_date=selected_date,
            )
        except Exception:
            logger.exception("Failed to calculate exam reminder state")
            exam_reminder_state = None

    can_view_internal_ranking = request.user.role in ("teacher", "director", "manager") or request.user.is_superuser
    internal_ranking_preview = []
    if can_view_internal_ranking:
        try:
            from education.services.ranking_service import get_group_internal_ranking_preview

            internal_ranking_preview = get_group_internal_ranking_preview(
                group=g,
                on_date=selected_date,
                limit=3,
                actor=request.user,
                persist=False,
            )
        except Exception:
            logger.exception("Failed to calculate group internal ranking preview")
            internal_ranking_preview = []

    closure_state = None
    if request.user.role in ("teacher", "director", "manager") or request.user.is_superuser:
        try:
            from education.services.closure_service import get_group_closure_state

            closure_state = get_group_closure_state(
                group=g,
                on_date=selected_date,
            )
        except Exception:
            logger.exception("Failed to calculate group closure state")
            closure_state = None

    # ── Yangi clean Batafsil sahifasi uchun KPI va o'quvchilar ro'yxati ──
    from education.models import GroupSchedule as _GS
    today_now = localdate()
    month_start_now = today_now.replace(day=1)
    enrolled_total = len(student_enrollments) or len(enrollments)
    capacity = int(getattr(g, "max_students", 0) or 0)
    fill_pct = round(enrolled_total * 100 / capacity, 1) if capacity else 0

    # Davomat (oxirgi 30 kun) — per-student ma'lumotlardan group KPI ni chiqaramiz (4→2 query)
    att_from = today_now - timedelta(days=30)
    att_per_student_total = dict(
        Attendance.objects.filter(group=g, date__gte=att_from, date__lte=today_now)
        .values("student_id").annotate(c=Count("id")).values_list("student_id", "c")
    )
    att_per_student_pres = dict(
        Attendance.objects.filter(
            group=g, date__gte=att_from, date__lte=today_now,
        ).filter(Q(status="present") | Q(present=True) | Q(forced=True))
        .values("student_id").annotate(c=Count("id")).values_list("student_id", "c")
    )
    att_total_g = sum(att_per_student_total.values())
    att_present_g = sum(att_per_student_pres.values())
    att_rate_g = round(att_present_g * 100 / att_total_g, 1) if att_total_g else 0

    # Oylik tushum
    monthly_rev = int(
        Payment.objects.filter(
            group=g,
            paid_date__gte=month_start_now,
            paid_date__lte=today_now,
        ).aggregate(s=Sum("summa"))["s"] or 0
    )

    # Jadval matni
    sched_rows = list(_GS.objects.filter(group=g).order_by("weekday", "start_time"))
    _wd_map = {1: "Du", 2: "Se", 3: "Ch", 4: "Pa", 5: "Ju", 6: "Sh", 7: "Ya"}
    _days_seen = []
    _start_time = None
    _room = ""
    for s in sched_rows:
        sh = _wd_map.get(s.weekday)
        if sh and sh not in _days_seen:
            _days_seen.append(sh)
        if not _start_time and s.start_time:
            _start_time = s.start_time
        if not _room and (s.room or "").strip():
            _room = (s.room or "").strip()
    schedule_days_text = "·".join(_days_seen) if _days_seen else "—"
    schedule_time_text = _start_time.strftime("%H:%M") if _start_time else ""
    schedule_room_text = _room

    # Avatar palitra
    _avatar_palette = [
        ("#2563eb", "#dbeafe"), ("#7c3aed", "#ede9fe"),
        ("#10b981", "#d1fae5"), ("#d97706", "#fef3c7"),
        ("#dc2626", "#fee2e2"), ("#0ea5e9", "#e0f2fe"),
        ("#db2777", "#fce7f3"), ("#0d9488", "#ccfbf1"),
    ]

    def _student_avatar(name):
        safe = (name or "?").strip() or "?"
        idx = sum(ord(c) for c in safe) % len(_avatar_palette)
        col, bg = _avatar_palette[idx]
        return safe[:2].upper(), col, bg

    # att_per_student_total / att_per_student_pres already computed above (shared with KPI)

    student_rows = []
    paid_count = 0
    for enr in enrollments:
        student = enr.student
        sname = f"{student.ism or ''} {student.familya or ''}".strip() or student.username
        initials, col, bg = _student_avatar(sname)
        joined_at = getattr(enr, "created_at", None) or getattr(enr, "tuzilgan", None)
        atot = int(att_per_student_total.get(student.id) or 0)
        apre = int(att_per_student_pres.get(student.id) or 0)
        s_att = round(apre * 100 / atot, 1) if atot else 0
        fee = int(student_total_fee_map.get(student.id) or 0)
        paid = int(student_total_paid_map.get(student.id) or 0)
        if fee <= 0:
            pay_label, pay_kind = ("—", "none")
        elif paid >= fee:
            pay_label, pay_kind = ("To'lagan", "paid")
            paid_count += 1
        elif paid > 0:
            pay_label, pay_kind = ("Qisman", "partial")
        else:
            pay_label, pay_kind = ("To'lamagan", "unpaid")
        student_rows.append({
            "id": student.id,
            "enrollment_id": enr.id,
            "name": sname,
            "initials": initials,
            "color": col,
            "bg": bg,
            "joined": joined_at,
            "att_rate": s_att,
            "pay_label": pay_label,
            "pay_kind": pay_kind,
        })

    # Avg per-student monthly fee for KPI subtitle
    avg_per_oy = 0
    if enrolled_total:
        try:
            avg_per_oy = int(round((monthly_rev or 0) / enrolled_total))
        except Exception:
            avg_per_oy = 0

    ctx = {
        "g": g,
        "group": g,
        "enrollments": enrollments,
        "rules_plus": rules_qs.filter(tur=Rule.PLUS).order_by("nom"),
        "rules_minus": rules_qs.filter(tur=Rule.MINUS).order_by("nom"),
        "can_add_student": can_add_student,
        "can_remove_student": can_remove_student,
        "selected_date": selected_date.isoformat(),
        "today": localdate().isoformat(),
        "recent_history_map": recent_history_map,
        "exam_reminder_state": exam_reminder_state,
        "internal_ranking_preview": internal_ranking_preview,
        "can_view_internal_ranking": can_view_internal_ranking,
        "closure_state": closure_state,
        "can_transfer_student": user_can_transfer_student(request.user),
        # New clean detail context
        "kpi_enrolled": enrolled_total,
        "kpi_capacity": capacity,
        "kpi_fill_pct": fill_pct,
        "kpi_att_rate": att_rate_g,
        "kpi_monthly_rev": monthly_rev,
        "kpi_avg_per_oy": avg_per_oy,
        "schedule_days_text": schedule_days_text,
        "schedule_time_text": schedule_time_text,
        "schedule_room_text": schedule_room_text,
        "student_rows": student_rows,
        "students_paid_count": paid_count,
    }
    return render(request, "education/group_detail.html", ctx)



@login_required
def group_schedule_manage(request, group_id: int):
    """
    Guruh jadvalini ko'rish va tahrirlash.
    Teacher faqat o'z guruhlarini ko'ra oladi.
    Manager/Director — hamma guruhlarni.
    """
    from core.tenant import get_request_center
    from education.models import GroupSchedule

    try:
        center = get_request_center(request)
        if not center:
            raise Http404("Center not found")
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_WEEKLY_SCHEDULE,
            message="Jadval bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response

        role = getattr(request.user, "role", "")
        if role == "teacher" and not request.user.is_superuser:
            group = get_object_or_404(
                Group.objects.select_related("oqituvchi", "center"),
                pk=group_id,
                center=center,
                oqituvchi=request.user,
                is_archived=False,
            )
        else:
            if role not in ("manager", "director") and not request.user.is_superuser:
                return redirect("core:home")
            group = get_object_or_404(
                Group.objects.select_related("oqituvchi", "center"),
                pk=group_id,
                center=center,
                is_archived=False,
            )

        schedules = (
            GroupSchedule.objects.filter(group=group, center=center)
            .select_related("group", "group__oqituvchi")
            .order_by("weekday", "start_time")
        )

        if request.method == "POST":
            action = (request.POST.get("action") or "").strip().lower()

            if action == "save_bulk":
                weekdays_raw = request.POST.getlist("weekdays")
                start_time_value = (request.POST.get("start_time") or "").strip()
                duration_min = _get_int(request.POST, "duration", 0)
                room = (request.POST.get("room") or "").strip()
                start_time_obj = parse_time(start_time_value) if start_time_value else None
                weekdays = []
                for wd in weekdays_raw:
                    try:
                        n = int(wd)
                        if 1 <= n <= 7:
                            weekdays.append(n)
                    except (TypeError, ValueError):
                        continue
                weekdays = sorted(set(weekdays))

                if not weekdays:
                    messages.error(request, "Kamida bitta dars kunini tanlang.")
                elif not start_time_obj:
                    messages.error(request, "Boshlanish vaqtini ko'rsating.")
                elif duration_min <= 0:
                    messages.error(request, "Davomiylikni daqiqalarda kiriting.")
                else:
                    end_minutes = (start_time_obj.hour * 60 + start_time_obj.minute) + duration_min
                    end_minutes = min(end_minutes, 23 * 60 + 59)
                    end_time_obj = (datetime.min.replace(
                        hour=end_minutes // 60, minute=end_minutes % 60
                    )).time()

                    room_clashes = []
                    if room:
                        for wd in weekdays:
                            clashes = list(
                                GroupSchedule.objects.filter(
                                    center=center,
                                    weekday=wd,
                                    start_time=start_time_obj,
                                    room__iexact=room,
                                )
                                .exclude(group=group)
                                .select_related("group")
                                .values_list("group__nom", flat=True)
                                .distinct()
                            )
                            for nom in clashes:
                                if nom not in room_clashes:
                                    room_clashes.append(nom)

                    if room_clashes:
                        messages.warning(
                            request,
                            f"⚠️ Bu vaqtda {', '.join(room_clashes)} ham shu xonadan foydalanadi.",
                        )

                    with transaction.atomic():
                        GroupSchedule.objects.filter(group=group, center=center).delete()
                        for wd in weekdays:
                            GroupSchedule.objects.create(
                                center=center,
                                group=group,
                                weekday=wd,
                                start_time=start_time_obj,
                                end_time=end_time_obj,
                                room=room,
                            )
                    messages.success(request, "✅ Jadval saqlandi.")
                    return redirect("education:group_schedule_manage", group_id=group_id)

            if action == "add":
                weekday = _get_int(request.POST, "weekday", 0)
                start_time_value = (request.POST.get("start_time") or "").strip()
                end_time_value = (request.POST.get("end_time") or "").strip()
                room = (request.POST.get("room") or "").strip()

                start_time_obj = parse_time(start_time_value) if start_time_value else None
                end_time_obj = parse_time(end_time_value) if end_time_value else None

                if not weekday or not start_time_obj:
                    messages.error(request, "Kun va boshlanish vaqti majburiy.")
                elif end_time_obj and end_time_obj <= start_time_obj:
                    messages.warning(request, "Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak.")
                else:
                    exists = GroupSchedule.objects.filter(
                        group=group,
                        weekday=weekday,
                        start_time=start_time_obj,
                    ).exists()
                    room_conflicts = []
                    if room:
                        room_conflicts = list(
                            GroupSchedule.objects.filter(
                                center=center,
                                weekday=weekday,
                                start_time=start_time_obj,
                                room__iexact=room,
                            )
                            .exclude(group=group)
                            .select_related("group")
                            .values_list("group__nom", flat=True)
                            .distinct()
                        )

                    if exists:
                        messages.warning(request, "⚠️ Bu vaqtda jadval allaqachon mavjud.")
                    elif room_conflicts:
                        messages.warning(
                            request,
                            f"⚠️ Bu vaqtda {', '.join(room_conflicts)} ham shu xonada.",
                        )
                    else:
                        GroupSchedule.objects.create(
                            center=center,
                            group=group,
                            weekday=weekday,
                            start_time=start_time_obj,
                            end_time=end_time_obj,
                            room=room,
                        )
                        messages.success(request, "✅ Jadval qo'shildi.")

            elif action == "delete":
                sched_id = _get_int(request.POST, "schedule_id", 0)
                deleted_count, _ = GroupSchedule.objects.filter(
                    pk=sched_id,
                    group=group,
                    center=center,
                ).delete()
                if deleted_count:
                    messages.success(request, "🗑 Jadval o'chirildi.")
                else:
                    messages.warning(request, "Jadval topilmadi.")

            return redirect("education:group_schedule_manage", group_id=group_id)

        rooms_used = list(schedules.exclude(room="").values_list("room", flat=True).distinct())
        conflict_map: dict[str, list[str]] = {}
        if rooms_used:
            conflicting = (
                GroupSchedule.objects.filter(center=center, room__in=rooms_used)
                .exclude(group=group)
                .select_related("group", "group__oqituvchi")
                .order_by("weekday", "start_time")
            )
            for conflict in conflicting:
                key = f"{conflict.weekday}_{conflict.start_time.strftime('%H:%M:%S')}_{conflict.room.strip().lower()}"
                conflict_map.setdefault(key, []).append(conflict.group.nom)

        schedule_map = {weekday: [] for weekday, _ in _schedule_weekday_labels()}
        for schedule in schedules:
            key = f"{schedule.weekday}_{schedule.start_time.strftime('%H:%M:%S')}_{(schedule.room or '').strip().lower()}"
            schedule.conflict_groups = conflict_map.get(key, [])
            schedule_map.setdefault(schedule.weekday, []).append(schedule)

        # Form pre-fill: pick the dominant slot to seed the editor.
        selected_weekdays = sorted({s.weekday for s in schedules})
        common_start = None
        common_duration = 0
        common_room = ""
        if schedules:
            from collections import Counter
            start_counter = Counter(s.start_time for s in schedules if s.start_time)
            if start_counter:
                common_start = start_counter.most_common(1)[0][0]
            room_counter = Counter((s.room or "").strip() for s in schedules)
            non_empty = [(r, c) for r, c in room_counter.items() if r]
            if non_empty:
                non_empty.sort(key=lambda kv: -kv[1])
                common_room = non_empty[0][0]
            duration_counter = Counter()
            for s in schedules:
                if s.start_time and s.end_time:
                    sm = s.start_time.hour * 60 + s.start_time.minute
                    em = s.end_time.hour * 60 + s.end_time.minute
                    if em > sm:
                        duration_counter[em - sm] += 1
            if duration_counter:
                common_duration = duration_counter.most_common(1)[0][0]
        if common_duration == 0:
            common_duration = 90

        weekday_short = [
            (1, "Du", "Dushanba"), (2, "Se", "Seshanba"), (3, "Ch", "Chorshanba"),
            (4, "Pa", "Payshanba"), (5, "Ju", "Juma"), (6, "Sh", "Shanba"),
            (7, "Ya", "Yakshanba"),
        ]
        _wd_short_map = {n: sh for n, sh, _full in weekday_short}
        sched_days_short = [_wd_short_map[n] for n in selected_weekdays if n in _wd_short_map]
        if sched_days_short:
            current_schedule_text = " · ".join(sched_days_short)
            if common_start:
                current_schedule_text = f"{current_schedule_text} · {common_start.strftime('%H:%M')}"
        else:
            current_schedule_text = ""

        return render(
            request,
            "education/group_schedule_manage.html",
            {
                "group": group,
                "schedules": schedules,
                "schedule_map": schedule_map,
                "weekday_choices": GroupSchedule.WEEKDAY_CHOICES,
                "weekday_labels": _schedule_weekday_labels(),
                "conflict_map": conflict_map,
                "selected_weekdays": selected_weekdays,
                "common_start": common_start,
                "common_duration": common_duration,
                "common_room": common_room,
                "weekday_short": weekday_short,
                "current_schedule_text": current_schedule_text,
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("group_schedule_manage failed: group_id=%s", group_id)
        messages.error(request, "Jadvalni yuklashda xatolik yuz berdi.")
        return redirect("education:group_detail", pk=group_id)



@login_required
@require_GET
def schedule_conflict_check(request):
    """
    AJAX: Bu xona, kuni, vaqtida boshqa guruh bormi?
    Parametrlar: room, weekday, start_time, exclude_group_id
    """
    from core.tenant import get_request_center
    from education.models import GroupSchedule

    try:
        center = get_request_center(request)
        if not center:
            return JsonResponse({"conflict": False, "groups": []})
        if not center_ui_feature_enabled(center, FEATURE_UI_WEEKLY_SCHEDULE):
            return JsonResponse({"detail": "disabled"}, status=403)

        role = getattr(request.user, "role", "")
        if role not in ("teacher", "manager", "director") and not request.user.is_superuser:
            return JsonResponse({"detail": "forbidden"}, status=403)

        room = (request.GET.get("room") or "").strip()
        weekday = _get_int(request.GET, "weekday", 0)
        start_time_value = (request.GET.get("start_time") or "").strip()
        exclude_gid = _get_int(request.GET, "exclude_group_id", 0)
        start_time_obj = parse_time(start_time_value) if start_time_value else None

        if not room or not weekday or not start_time_obj:
            return JsonResponse({"conflict": False, "groups": []})

        qs = (
            GroupSchedule.objects.filter(
                center=center,
                room__iexact=room,
                weekday=weekday,
                start_time=start_time_obj,
            )
            .select_related("group")
            .order_by("group__nom")
        )
        if exclude_gid:
            qs = qs.exclude(group_id=exclude_gid)

        conflicts = [item.group.nom for item in qs]
        return JsonResponse({"conflict": bool(conflicts), "groups": conflicts})
    except Exception:
        logger.exception("schedule_conflict_check failed")
        return JsonResponse({"conflict": False, "groups": []}, status=500)



@login_required
def weekly_schedule_view(request):
    """
    Manager/Director uchun haftalik jadval — vaqt × kun gridi,
    o'qituvchi rangi, o'qituvchi yuklamasi, Excel/PDF eksport.
    """
    from core.tenant import get_request_center
    from education.models import GroupSchedule
    from collections import defaultdict

    try:
        center = get_request_center(request)
        if not center:
            raise Http404("Center not found")
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_WEEKLY_SCHEDULE,
            message="Haftalik jadval bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response

        role = getattr(request.user, "role", "")
        if role not in ("manager", "director") and not request.user.is_superuser:
            return redirect("core:home")

        teacher_id = _get_int(request.GET, "teacher", 0)
        room_filter = (request.GET.get("room") or "").strip()

        base_qs = (
            GroupSchedule.objects.filter(center=center, group__is_archived=False)
            .select_related("group", "group__oqituvchi", "group__category_obj")
            .order_by("weekday", "start_time", "group__nom")
        )
        if teacher_id:
            base_qs = base_qs.filter(group__oqituvchi_id=teacher_id)

        qs = base_qs
        if room_filter:
            qs = qs.filter(room__icontains=room_filter)

        total_slots_count = base_qs.count()
        filtered_slots_count = qs.count()

        weekday_labels = _schedule_weekday_labels()
        week_map = {weekday: [] for weekday, _ in weekday_labels}
        for schedule in qs:
            week_map[schedule.weekday].append(schedule)

        all_slots = list(qs)
        if all_slots:
            earliest = min(_weekly_t_to_min(s.start_time) for s in all_slots)
            latest = max(
                _weekly_t_to_min(s.end_time) if s.end_time
                else _weekly_t_to_min(s.start_time) + 60
                for s in all_slots
            )
            grid_start = (earliest // _WEEKLY_SLOT_MIN) * _WEEKLY_SLOT_MIN
            grid_end = -(-latest // _WEEKLY_SLOT_MIN) * _WEEKLY_SLOT_MIN
        else:
            grid_start, grid_end = 8 * 60, 22 * 60
        grid_start = max(grid_start, 6 * 60)
        grid_end = min(grid_end, 23 * 60 + 30)

        time_slots = []
        cur = grid_start
        while cur < grid_end:
            hh, mm = divmod(cur, 60)
            time_slots.append({"minute": cur, "label": f"{hh:02d}:{mm:02d}"})
            cur += _WEEKLY_SLOT_MIN

        teachers_in_use = []
        seen_teacher_ids = set()
        for s in all_slots:
            tch = s.group.oqituvchi
            if tch and tch.id not in seen_teacher_ids:
                seen_teacher_ids.add(tch.id)
                teachers_in_use.append(tch)

        time_grid = {wd: [[] for _ in time_slots] for wd, _ in weekday_labels}
        for s in all_slots:
            start_m = _weekly_t_to_min(s.start_time)
            end_m = _weekly_t_to_min(s.end_time) if s.end_time else start_m + 60
            slot_idx = max(0, (start_m - grid_start) // _WEEKLY_SLOT_MIN)
            if slot_idx >= len(time_slots):
                continue
            tch = s.group.oqituvchi
            time_grid[s.weekday][slot_idx].append({
                "item": s,
                "is_unassigned": not s.group.oqituvchi_id,
                "teacher_name": tch.get_full_name() if tch else "Belgilanmagan",
                "teacher_initials": _weekly_teacher_initials(tch),
            })

        used_idx = sorted({
            idx
            for wd, _ in weekday_labels
            for idx, cell in enumerate(time_grid[wd])
            if cell
        })
        filtered_time_slots = [time_slots[i] for i in used_idx]
        filtered_time_grid = {
            wd: [time_grid[wd][i] for i in used_idx] for wd, _ in weekday_labels
        }
        grid_rows = []
        for new_idx, orig_idx in enumerate(used_idx):
            slot = time_slots[orig_idx]
            cells = [time_grid[wd][orig_idx] for wd, _ in weekday_labels]
            grid_rows.append({"label": slot["label"], "cells": cells, "minute": slot["minute"]})

        teacher_load_map = defaultdict(lambda: {
            "minutes": 0, "lessons": 0, "days": set(), "rooms": set(),
        })
        for s in all_slots:
            tid = s.group.oqituvchi_id
            key = tid if tid else "unassigned"
            start_m = _weekly_t_to_min(s.start_time)
            end_m = _weekly_t_to_min(s.end_time) if s.end_time else start_m + 60
            teacher_load_map[key]["minutes"] += max(0, end_m - start_m)
            teacher_load_map[key]["lessons"] += 1
            teacher_load_map[key]["days"].add(s.weekday)
            if s.room:
                teacher_load_map[key]["rooms"].add(s.room)

        weekday_short = {1: "Du", 2: "Se", 3: "Ch", 4: "Pa", 5: "Ju", 6: "Sh", 7: "Ya"}
        teacher_loads = []
        for tch in teachers_in_use:
            ld = teacher_load_map.get(tch.id) or {"minutes": 0, "lessons": 0, "days": set(), "rooms": set()}
            teacher_loads.append({
                "teacher": tch,
                "initials": _weekly_teacher_initials(tch),
                "lessons": ld["lessons"],
                "hours": round(ld["minutes"] / 60.0, 1),
                "days_count": len(ld["days"]),
                "days_short": [weekday_short[d] for d in sorted(ld["days"])],
                "rooms": sorted(ld["rooms"]),
            })
        if "unassigned" in teacher_load_map:
            ld = teacher_load_map["unassigned"]
            teacher_loads.append({
                "teacher": None,
                "initials": "?",
                "lessons": ld["lessons"],
                "hours": round(ld["minutes"] / 60.0, 1),
                "days_count": len(ld["days"]),
                "days_short": [weekday_short[d] for d in sorted(ld["days"])],
                "rooms": sorted(ld["rooms"]),
            })
        teacher_loads.sort(key=lambda x: (-x["hours"], -x["lessons"]))

        groups_qs = (
            Group.objects.filter(center=center, is_archived=False)
            .select_related("oqituvchi", "category_obj")
            .order_by("nom")
        )
        if teacher_id:
            groups_qs = groups_qs.filter(oqituvchi_id=teacher_id)

        total_groups_count = groups_qs.count()
        scheduled_group_ids = list(base_qs.values_list("group_id", flat=True).distinct())
        groups_with_schedule_count = len(scheduled_group_ids)
        unscheduled_groups = list(groups_qs.exclude(id__in=scheduled_group_ids)[:12])
        unscheduled_groups_count = max(total_groups_count - groups_with_schedule_count, 0)

        empty_state_message = ""
        if not filtered_slots_count:
            if room_filter:
                empty_state_message = f'"{room_filter}" bo‘yicha mos jadval topilmadi.'
            elif teacher_id:
                empty_state_message = "Tanlangan o‘qituvchi uchun jadval hali kiritilmagan."
            else:
                empty_state_message = "Haftalik jadval hali kiritilmagan."

        rooms = (
            GroupSchedule.objects.filter(center=center)
            .exclude(room="")
            .values_list("room", flat=True)
            .distinct()
            .order_by("room")
        )
        teachers = User.objects.filter(
            center=center,
            role="teacher",
            is_archived=False,
        ).order_by("ism", "familya")

        export = (request.GET.get("export") or "").strip().lower()
        if export in ("excel", "1", "xlsx"):
            return _weekly_schedule_excel(
                center, weekday_labels, week_map, filtered_time_slots, filtered_time_grid,
                teacher_loads, teacher_id, room_filter, teachers,
            )
        if export == "pdf":
            return _weekly_schedule_pdf(
                center, weekday_labels, filtered_time_slots, filtered_time_grid,
                teacher_loads, teacher_id, room_filter, teachers,
            )

        return render(
            request,
            "education/weekly_schedule.html",
            {
                "week_map": week_map,
                "weekday_labels": weekday_labels,
                "grid_rows": grid_rows,
                "teacher_loads": teacher_loads,
                "rooms": rooms,
                "teachers": teachers,
                "selected_teacher": teacher_id,
                "selected_room": room_filter,
                "total_slots_count": total_slots_count,
                "filtered_slots_count": filtered_slots_count,
                "total_groups_count": total_groups_count,
                "groups_with_schedule_count": groups_with_schedule_count,
                "unscheduled_groups_count": unscheduled_groups_count,
                "unscheduled_groups": unscheduled_groups,
                "empty_state_message": empty_state_message,
                "has_filters": bool(teacher_id or room_filter),
                "teachers_in_use_count": len(teachers_in_use),
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("weekly_schedule_view failed")
        messages.error(request, "Haftalik jadvalni yuklashda xatolik yuz berdi.")
        return redirect("core:home")



@login_required
def teacher_schedule_view(request):
    """
    O'qituvchi o'z haftalik jadvalini ko'radi.
    """
    from core.tenant import get_request_center
    from education.models import GroupSchedule

    try:
        center = get_request_center(request)
        if not center:
            raise Http404("Center not found")
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_WEEKLY_SCHEDULE,
            message="Dars jadvali bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response

        if request.user.role != "teacher" and not request.user.is_superuser:
            return redirect("core:home")

        teacher = request.user
        schedules = (
            GroupSchedule.objects.filter(
                center=center,
                group__oqituvchi=teacher,
                group__is_archived=False,
                group__is_deleted=False,
            )
            .select_related("group", "group__oqituvchi")
            .order_by("weekday", "start_time")
        )

        week_map = {weekday: [] for weekday, _ in _schedule_weekday_labels()}
        for schedule in schedules:
            week_map[schedule.weekday].append(schedule)

        groups_qs = (
            Group.objects.filter(center=center, oqituvchi=teacher, is_archived=False)
            .select_related("category_obj")
            .order_by("nom")
        )
        scheduled_group_ids = list(schedules.values_list("group_id", flat=True).distinct())
        unscheduled_groups = list(groups_qs.exclude(id__in=scheduled_group_ids))

        return render(
            request,
            "education/teacher_schedule.html",
            {
                "week_map": week_map,
                "weekday_labels": _schedule_weekday_labels(),
                "total_lessons": schedules.count(),
                "unscheduled_groups": unscheduled_groups,
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("teacher_schedule_view failed")
        messages.error(request, "Jadvalni yuklashda xatolik yuz berdi.")
        return redirect("core:home")



@login_required
def group_bulk_remove(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "POST bo'lishi shart."})

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
         qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # ruxsat tekshirish
    can_remove = False
    if request.user.role == "director" or request.user.is_superuser:
        can_remove = True
    elif center:
        if request.user.role == "manager":
            can_remove = center.manager_can_remove_student
        elif request.user.role == "teacher":
            can_remove = center.teacher_can_remove_student

    if not can_remove:
        return JsonResponse({"ok": False, "msg": "Sizda o'quvchilarni o'chirish huquqi yo'q."})

    ids = request.POST.getlist("enrollment_ids")

    if not ids:
        return JsonResponse({"ok": False, "msg": "ID kelmagan."})

    qs = Enrollment.objects.filter(id__in=ids, group=g)
    count = qs.count()
    qs.delete()

    return JsonResponse({"ok": True, "deleted": count})



def category_detail(request, category_id):
    from core.tenant import get_request_center, get_tenant_object_or_404

    center = get_request_center(request)
    # Boshqa markaz category → 404 (PermissionDenied o'rniga, IDOR leak yo'q)
    category = get_tenant_object_or_404(
        Category, request, id=category_id, allow_global=True
    )

    groups = (
        Group.objects
        .filter(category_obj=category)
        .select_related("center", "oqituvchi")
        .order_by("id")
    )
    if center:
        groups = groups.filter(center=center)

    # Filter by status (default: active)
    status = request.GET.get('status', 'active')
    
    # ✅ TEACHERLAR UCHUN "ARXIV" YOPIQ
    if request.user.role == 'teacher':
        status = 'active'
        groups = groups.filter(is_archived=False)
    else:
        if status == 'archived':
            groups = groups.filter(is_archived=True)
        else:
            groups = groups.filter(is_archived=False)

    groups_count = groups.count()

    return render(request, "education/category_detail.html", {
        "category": category,
        "groups": groups,
        "groups_count": groups_count,
        "status": status,
        "is_teacher": request.user.role == 'teacher', # Template uchun
    })



@login_required
def group_toggle_archive(request, pk):
    """Guruhni arxivga ko'chirish: GET → tasdiqlash sahifasi, POST → amal."""
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=pk)

    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()

    def _redirect_to(fallback):
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return fallback

    if not _can_manage(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return _redirect_to(redirect("education:all_groups"))

    if request.method == "POST":
        # Restoration mode skips confirmation entry.
        if group.is_archived:
            group.is_archived = False
            group.save(update_fields=["is_archived"])
            messages.success(request, "Guruh arxivdan qaytarildi ✅")
            return _redirect_to(redirect("education:group_detail", pk=group.id))

        confirm_text = (request.POST.get("confirm_name") or "").strip()
        if confirm_text != group.nom:
            messages.error(
                request,
                "Tasdiqlash uchun guruh nomini aynan to'g'ri yozing.",
            )
            enrolled_total = Enrollment.objects.filter(
                group=group, is_active=True, is_deleted=False,
            ).count()
            return render(request, "education/group_archive.html", {
                "group": group, "g": group,
                "enrolled_total": enrolled_total,
                "confirm_value": confirm_text,
            })

        group.is_archived = True
        group.save(update_fields=["is_archived"])
        messages.success(request, "Guruh arxivga ko'chirildi ✅")
        return _redirect_to(redirect("education:all_groups"))

    enrolled_total = Enrollment.objects.filter(
        group=group, is_active=True, is_deleted=False,
    ).count()
    return render(request, "education/group_archive.html", {
        "group": group, "g": group,
        "enrolled_total": enrolled_total,
        "confirm_value": "",
    })



@login_required
def group_toggle_close(request, pk):
    """Guruhni vaqtinchalik to'xtatish formasi (GET) yoki amal (POST)."""
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=pk)

    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()

    def _redirect_back():
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("education:all_groups")

    if not _can_manage(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return _redirect_back()

    if request.method == "POST":
        action = (request.POST.get("action") or "pause").strip().lower()
        if action == "resume" or group.is_closed:
            group.is_closed = False
            group.closed_at = None
            group.closed_by = None
            group.save(update_fields=["is_closed", "closed_at", "closed_by"])
            messages.success(request, "Guruh qayta faollashtirildi ✅")
        else:
            group.is_closed = True
            group.closed_at = timezone.now()
            group.closed_by = request.user
            group.save(update_fields=["is_closed", "closed_at", "closed_by"])
            messages.success(request, "Guruh vaqtinchalik to'xtatildi ✅")
        return _redirect_back()

    enrolled_total = Enrollment.objects.filter(
        group=group, is_active=True, is_deleted=False,
    ).count()
    today_now = timezone.localdate()
    return render(request, "education/group_pause.html", {
        "group": group,
        "g": group,
        "enrolled_total": enrolled_total,
        "default_pause_date": today_now,
        "default_resume_date": today_now + timedelta(days=14),
    })



@login_required
def oylik_hisobot(request):
    """Har bir o'qituvchining oyligini avtomatik hisoblash"""
    oy = datetime.now().strftime("%B")
    yil = datetime.now().year
    oylik_data = []

    teachers = User.objects.filter(role='teacher')

    for teacher in teachers:
        guruhlar = Group.objects.filter(oqituvchi=teacher)
        jami_darslar = 0
        jami_daromad = 0

        for g in guruhlar:
            darslar_soni = Dars.objects.filter(
                guruh=g,
                oqituvchi=teacher,
                sana__month=datetime.now().month,
                sana__year=datetime.now().year
            ).count()

            dars_tolovi = g.dars_boshiga_tolov()
            jami_darslar += darslar_soni
            jami_daromad += darslar_soni * dars_tolovi

        markaz_foydasi = jami_daromad * 0.5  # misol uchun 50/50

        oylik_data.append({
            "oqituvchi": teacher.get_full_name() or teacher.email,
            "guruhlar": guruhlar.count(),
            "darslar": jami_darslar,
            "daromad": round(jami_daromad),
            "markaz_foydasi": round(markaz_foydasi),
        })

        # OylikHisobot jadvaliga yozib qo'yish
        OylikHisobot.objects.update_or_create(
            oqituvchi=teacher,
            oy=oy,
            yil=yil,
            defaults={
                "jami_darslar": jami_darslar,
                "jami_daromad": round(jami_daromad),
                "markaz_foydasi": round(markaz_foydasi)
            }
        )

    return render(request, "education/oylik_hisobot.html", {"oylik_data": oylik_data, "oy": oy, "yil": yil})



@login_required
def group_create_by_category(request, category_id):
    from core.tenant import get_request_center, get_tenant_object_or_404

    center = get_request_center(request)
    category = get_tenant_object_or_404(
        Category, request, id=category_id, allow_global=True
    )

    from billing.services import center_has_feature
    has_manual_oy_dars_soni = center_has_feature(center, "manual_oy_dars_soni") if center else False

    if request.method == "POST":
        form = GroupForm(request.POST, center=center)
        if form.is_valid():
            group = form.save(commit=False)
            group.category_obj = category
            group.center = center
            schedule_mode = form.cleaned_data.get("schedule_mode", "")
            custom_days = form.cleaned_data.get("custom_days") or []
            if schedule_mode in {"odd", "even", "custom"}:
                day_count = len(custom_days) if schedule_mode == "custom" else 3
                group.lessons_per_week = day_count
                if has_manual_oy_dars_soni:
                    if not group.oy_dars_soni:
                        group.oy_dars_soni = day_count * 4
                else:
                    group.oy_dars_soni = 12
            if not group.oy_dars_soni:
                group.oy_dars_soni = 12

            # O'qituvchi tanlanganda foiz teacher profilidan olinadi.
            if group.oqituvchi and getattr(group.oqituvchi, "oqituvchi_foizi", None) is not None:
                group.oqituvchi_foiz = group.oqituvchi.oqituvchi_foizi
            elif not group.oqituvchi_foiz:
                group.oqituvchi_foiz = 40

            from education.services.group_schedule_service import (
                apply_group_duration_defaults,
                sync_simple_group_schedule,
            )
            apply_group_duration_defaults(group)
            group.save()
            sync_simple_group_schedule(
                group=group,
                schedule_mode=schedule_mode,
                custom_days=custom_days,
                start_time=form.cleaned_data.get("schedule_start_time"),
                end_time=form.cleaned_data.get("schedule_end_time"),
                room=form.cleaned_data.get("schedule_room"),
            )
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm(center=center)

    course_templates = CourseTemplate.objects.filter(center=center, is_active=True).order_by("name") if center else []
    return render(request, "education/group_form.html", {
        "form": form,
        "category": category,
        "course_templates": course_templates,
        "has_manual_oy_dars_soni": has_manual_oy_dars_soni,
    })



@login_required
def groups_home(request):
    # ✅ Tenant isolation
    from core.tenant import get_request_center
    center = get_request_center(request)
    
    # kategoriyalar
    from django.db.models import Q
    categories_qs = Category.objects.all().order_by("name")
    if center:
        # ✅ Smart Isolation: 
        # 1. Faqat shu center'ga tegishli bo'limlarni ko'rsatamiz.
        # 2. Agar bu ASOSIY (birinchi yaratilgan) markaz bo'lsa, Global (Legacy) bo'limlarni ham chiqaramiz.
        first_center = Center.objects.order_by("id").first()
        if first_center and center.id == first_center.id:
            categories_qs = categories_qs.filter(Q(center=center) | Q(center__isnull=True))
        else:
            categories_qs = categories_qs.filter(center=center)
        
    categories = list(categories_qs)

    # har bir category uchun guruhlar sonini hisoblab map qilamiz
    counts_qs = (
        Group.objects
    )
    if center:
        counts_qs = counts_qs.filter(center=center)
        
    counts_qs = (
        counts_qs
        .filter(is_archived=False)
        .values("category_obj")          # FK field nomi sizda shu: category_obj
        .annotate(c=Count("id"))
    )
    count_map = {row["category_obj"]: row["c"] for row in counts_qs}

    # template ishlatishi uchun cat.groups_count qo'shib chiqamiz
    for cat in categories:
        cat.groups_count = count_map.get(cat.id, 0)

    return render(request, "education/groups_home.html", {
        "categories": categories,
        "categories_count": len(categories),
    })



@login_required
def all_groups_overview(request):
    """Boshqaruv → Hammasini ko'rish: barcha guruhlar ko'rinishi."""
    from core.tenant import get_request_center
    from education.models import GroupSchedule

    center = get_request_center(request) or get_active_center(request)
    today = timezone.localdate()
    month_start = today.replace(day=1)

    qs = Group.objects.filter(is_archived=False, is_deleted=False)
    if center:
        qs = qs.filter(center=center)

    # ── Filter qiymatlari ──
    q_text = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip().lower()
    cat_id = (request.GET.get("category") or "").strip()
    teacher_id = (request.GET.get("teacher") or "").strip()
    sort_key = (request.GET.get("sort") or "fill").strip().lower()
    view_mode = (request.GET.get("view") or "list").strip().lower()
    if view_mode not in ("list", "grid"):
        view_mode = "list"
    fmt = (request.GET.get("format") or "").strip().lower()

    if q_text:
        qs = qs.filter(Q(nom__icontains=q_text) |
                       Q(category_obj__name__icontains=q_text) |
                       Q(oqituvchi__ism__icontains=q_text) |
                       Q(oqituvchi__familya__icontains=q_text))

    if cat_id.isdigit():
        qs = qs.filter(category_obj_id=int(cat_id))

    if teacher_id.isdigit():
        qs = qs.filter(oqituvchi_id=int(teacher_id))

    # ── Filter dropdown manbalari ──
    cat_choices = list(
        Category.objects
        .filter(groups__in=qs)
        .distinct()
        .order_by("name")
        .values("id", "name")
    )
    teacher_choices = list(
        User.objects
        .filter(role="teacher", id__in=qs.values("oqituvchi_id"))
        .order_by("ism", "familya")
        .values("id", "ism", "familya")
    )
    teacher_choices = [
        {"id": t["id"], "name": f"{t['ism']} {t['familya']}".strip() or "—"}
        for t in teacher_choices
    ]

    groups_for_filter = list(qs.select_related("oqituvchi", "category_obj"))
    group_ids = [g.id for g in groups_for_filter]

    # ── Sig'im / band o'rinlar / fill_pct ──
    enroll_map = dict(
        Enrollment.objects.filter(
            group_id__in=group_ids,
            is_active=True,
            is_deleted=False,
        )
        .values("group_id")
        .annotate(cnt=Count("id"))
        .values_list("group_id", "cnt")
    )

    # ── Bu oygi tushum ──
    rev_map = dict(
        Payment.objects.filter(
            group_id__in=group_ids,
            paid_date__gte=month_start,
            paid_date__lte=today,
        )
        .values("group_id")
        .annotate(s=Sum("summa"))
        .values_list("group_id", "s")
    )

    # ── Davomat (oxirgi 30 kun) ──
    att_from = today - timedelta(days=30)
    att_qs = Attendance.objects.filter(group_id__in=group_ids, date__gte=att_from, date__lte=today)
    att_total_map = dict(
        att_qs.values("group_id").annotate(c=Count("id")).values_list("group_id", "c")
    )
    present_q = Q(status="present") | Q(present=True) | Q(forced=True)
    att_present_map = dict(
        att_qs.filter(present_q).values("group_id").annotate(c=Count("id")).values_list("group_id", "c")
    )

    # ── Schedule (Du · Ch · Ju · 14:00) ──
    schedule_map = {}
    for row in GroupSchedule.objects.filter(group_id__in=group_ids).values(
        "group_id", "weekday", "start_time"
    ).order_by("group_id", "weekday", "start_time"):
        schedule_map.setdefault(row["group_id"], []).append(row)

    rows = []
    total_capacity = 0
    total_enrolled = 0
    total_revenue = 0
    active_count = 0
    fill_pcts = []
    for g in groups_for_filter:
        enrolled = int(enroll_map.get(g.id) or 0)
        capacity = int(getattr(g, "max_students", 0) or 0)
        fill_pct = round(enrolled * 100 / capacity, 1) if capacity else 0
        revenue = int(rev_map.get(g.id) or 0)
        att_total = int(att_total_map.get(g.id) or 0)
        att_present = int(att_present_map.get(g.id) or 0)
        att_rate = round(att_present * 100 / att_total, 1) if att_total else 0
        is_full = capacity and enrolled >= capacity
        is_active = not g.is_closed
        if is_active:
            active_count += 1
        if is_full:
            status_label = "To'ldirilgan"
            status_kind = "full"
        elif is_active:
            status_label = "Faol"
            status_kind = "active"
        else:
            status_label = "Yopiq"
            status_kind = "closed"
        if 0 < fill_pct < 100:
            status_label = "To'ldirilmoqda" if not is_full and is_active else status_label
            if not is_full and is_active:
                status_kind = "filling"
        teacher_name = (
            f"{g.oqituvchi.ism} {g.oqituvchi.familya}".strip()
            if g.oqituvchi else "—"
        )
        cat_name = g.category_obj.name if g.category_obj else (g.get_category_display() if hasattr(g, "get_category_display") else "—")
        sub_label = cat_name
        # Status filter
        if status == "active" and not (is_active and not is_full):
            continue
        if status == "filling" and not (is_active and 0 < fill_pct < 100 and not is_full):
            continue
        if status == "full" and not is_full:
            continue
        if status == "closed" and is_active:
            continue
        initials, color, bg = _all_groups_avatar(g.nom)
        rows.append({
            "id": g.id,
            "name": g.nom,
            "subtitle": sub_label,
            "category_id": g.category_obj_id,
            "teacher_id": g.oqituvchi_id,
            "teacher": teacher_name,
            "schedule": _all_groups_schedule_text(g.id, schedule_map),
            "enrolled": enrolled,
            "capacity": capacity,
            "fill_pct": fill_pct,
            "revenue": revenue,
            "att_rate": att_rate,
            "status_label": status_label,
            "status_kind": status_kind,
            "initials": initials,
            "color": color,
            "bg": bg,
            "is_active": is_active,
        })
        total_capacity += capacity
        total_enrolled += enrolled
        total_revenue += revenue
        if capacity:
            fill_pcts.append(fill_pct)

    # ── Saralash ──
    if sort_key == "name":
        rows.sort(key=lambda r: r["name"].lower())
    elif sort_key == "students":
        rows.sort(key=lambda r: -r["enrolled"])
    elif sort_key == "revenue":
        rows.sort(key=lambda r: -r["revenue"])
    elif sort_key == "att":
        rows.sort(key=lambda r: -r["att_rate"])
    else:  # fill
        rows.sort(key=lambda r: (-r["fill_pct"], -r["revenue"], r["name"].lower()))

    avg_fill = round(sum(fill_pcts) / len(fill_pcts), 1) if fill_pcts else 0

    # ── CSV eksport ──
    if fmt == "csv":
        import csv
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="guruhlar-{today.isoformat()}.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Guruh", "Bo'lim", "O'qituvchi", "Jadval",
            "O'quvchilar", "Sig'im", "To'ldirilganlik %",
            "Davomat %", "Tushum (so'm)", "Holat",
        ])
        for r in rows:
            writer.writerow([
                r["name"], r["subtitle"], r["teacher"], r["schedule"],
                r["enrolled"], r["capacity"], r["fill_pct"],
                r["att_rate"], r["revenue"], r["status_label"],
            ])
        return response

    # ── JSON (AJAX qayta yuklash) ──
    if fmt == "json":
        return JsonResponse({
            "kpis": {
                "active_groups": active_count,
                "total_groups": len(groups_for_filter),
                "students": total_enrolled,
                "avg_fill": avg_fill,
                "monthly_revenue": total_revenue,
            },
            "rows": rows,
        })

    # ── Pagination ──
    paginator = Paginator(rows, _ALL_GROUPS_PAGE_SIZE)
    page_num = request.GET.get("page") or 1
    try:
        page_obj = paginator.page(page_num)
    except Exception:
        page_obj = paginator.page(1)

    base_qs = request.GET.copy()
    if "page" in base_qs:
        base_qs.pop("page")
    base_qs_str = base_qs.urlencode()

    return render(request, "education/all_groups.html", {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_rows": len(rows),
        "kpi_active": active_count,
        "kpi_total": len(groups_for_filter),
        "kpi_students": total_enrolled,
        "kpi_avg_fill": avg_fill,
        "kpi_revenue": total_revenue,
        "q": q_text,
        "status": status,
        "category_id": cat_id,
        "teacher_id": teacher_id,
        "sort": sort_key,
        "view_mode": view_mode,
        "categories": cat_choices,
        "teachers": teacher_choices,
        "base_qs": base_qs_str,
    })



@login_required
def add_category(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES, center=center)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.center = center
            cat.save()
            messages.success(request, "Bo'lim muvaffaqiyatli qo'shildi ✅")
            return redirect("education:groups_home")
    else:
        form = CategoryForm(center=center)
    return render(request, "education/category_add.html", {"form": form})



# ---------- CRUD ----------
@login_required
def group_create(request, category=None):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo'q.")
        return redirect("education:groups_home")

    if category == Group.LANG:
        FormCls, title = LangGroupForm, "Tillar bo'yicha guruh yaratish"
    elif category == Group.IT:
        FormCls, title = ITGroupForm, "IT bo'yicha guruh yaratish"
    else:
        FormCls, title = GroupForm, "Guruh yaratish"

    from core.tenant import get_request_center
    center = get_request_center(request) or getattr(request.user, "center", None)
    from billing.services import center_has_feature
    has_manual_oy_dars_soni = center_has_feature(center, "manual_oy_dars_soni") if center else False

    form = FormCls(request.POST or None, center=center)

    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)
        schedule_mode = form.cleaned_data.get("schedule_mode", "")
        custom_days = form.cleaned_data.get("custom_days") or []

        if schedule_mode in {"odd", "even", "custom"}:
            day_count = len(custom_days) if schedule_mode == "custom" else 3
            g.lessons_per_week = day_count
            if has_manual_oy_dars_soni:
                if not g.oy_dars_soni:
                    g.oy_dars_soni = day_count * 4
            else:
                g.oy_dars_soni = 12

        # 🔹 Kategoriya bo'sh bo'lsa, avtomatik to'ldir
        g.category = category or Group.LANG

        # 🔹 Center avtomatik foydalanuvchidan
        if not g.center_id:
            if center:
                g.center = center
            elif hasattr(request.user, "center") and request.user.center:
                g.center = request.user.center
            else:
                from accounts.models import Center
                g.center = Center.objects.first()

        # Agar narx kiritilmagan bo'lsa, 0 saqlaymiz (500k avtomatik qo'shmaymiz)
        if g.kurs_narxi is None:
            g.kurs_narxi = 0

        # ✅ O'qituvchi foizi
        if g.oqituvchi and getattr(g.oqituvchi, 'oqituvchi_foizi', None) is not None:
            g.oqituvchi_foiz = g.oqituvchi.oqituvchi_foizi
        elif not g.oqituvchi_foiz:
            g.oqituvchi_foiz = 40

        if not g.oy_dars_soni:
            g.oy_dars_soni = 12

        from education.services.group_schedule_service import (
            apply_group_duration_defaults,
            sync_simple_group_schedule,
        )
        apply_group_duration_defaults(g)
        g.save()
        sync_simple_group_schedule(
            group=g,
            schedule_mode=schedule_mode,
            custom_days=custom_days,
            start_time=form.cleaned_data.get("schedule_start_time"),
            end_time=form.cleaned_data.get("schedule_end_time"),
            room=form.cleaned_data.get("schedule_room"),
        )
        messages.success(request, f"✅ {g.nom} guruhi muvaffaqiyatli yaratildi.")
        return redirect("education:group_detail", pk=g.pk)

    elif request.method == "POST":
        print("❌ Forma xato:", form.errors)

    course_templates = CourseTemplate.objects.filter(center=center, is_active=True).order_by("name") if center else []
    return render(request, "education/group_form.html", {
        "form": form, "title": title, "course_templates": course_templates,
        "has_manual_oy_dars_soni": has_manual_oy_dars_soni,
    })



@login_required
def group_edit(request, pk):
    if not request.user.is_superuser and request.user.role not in ["director", "manager", "teacher"]:
        messages.error(request, "Sizda ruxsat yo'q.")
        return redirect("education:groups")

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # Eski qiymatlarni forma o'zgartirmasdan oldin saqlab qolamiz
    old_foiz = g.oqituvchi_foiz
    old_narx = g.kurs_narxi
    old_oqituvchi_id = g.oqituvchi_id

    from billing.services import center_has_feature
    has_manual_oy_dars_soni = center_has_feature(center, "manual_oy_dars_soni") if center else False

    form = GroupForm(request.POST or None, instance=g, center=center)

    if request.method == "POST" and form.is_valid():
        old_oy_dars_soni = g.oy_dars_soni or 12
        updated_group = form.save(commit=False)
        schedule_mode = form.cleaned_data.get("schedule_mode", "")
        custom_days = form.cleaned_data.get("custom_days") or []

        if schedule_mode in {"odd", "even", "custom"}:
            day_count = len(custom_days) if schedule_mode == "custom" else 3
            updated_group.lessons_per_week = day_count
            if has_manual_oy_dars_soni:
                if not updated_group.oy_dars_soni:
                    updated_group.oy_dars_soni = day_count * 4
            else:
                updated_group.oy_dars_soni = 12

        # Har holda bo'sh qolmasin
        if not updated_group.oy_dars_soni:
            updated_group.oy_dars_soni = 12

        # Agar o'qituvchi o'zgargan bo'lsa, mos foizni avtomatik olamiz
        if updated_group.oqituvchi and updated_group.oqituvchi_id != old_oqituvchi_id:
            teacher_foiz = getattr(updated_group.oqituvchi, 'oqituvchi_foizi', None)
            if teacher_foiz is not None:
                updated_group.oqituvchi_foiz = teacher_foiz

        from education.services.group_schedule_service import (
            apply_group_duration_defaults,
            sync_simple_group_schedule,
        )
        apply_group_duration_defaults(updated_group)
        updated_group.save()
        sync_simple_group_schedule(
            group=updated_group,
            schedule_mode=schedule_mode,
            custom_days=custom_days,
            start_time=form.cleaned_data.get("schedule_start_time"),
            end_time=form.cleaned_data.get("schedule_end_time"),
            room=form.cleaned_data.get("schedule_room"),
        )

        new_oy_dars_soni = updated_group.oy_dars_soni or 12
        from education.models import Enrollment, StudentGroupHistory
        from django.db.models import Q

        # Agar guruhning foizi yoki narxi o'zgargan bo'lsa, joriy o'quvchilarga ham ta'sir qilsin
        if updated_group.oqituvchi_foiz != old_foiz or updated_group.kurs_narxi != old_narx:
            enrollments = Enrollment.objects.filter(group=updated_group)

            if updated_group.oqituvchi_foiz != old_foiz:
                enrollments.update(oqituvchi_foiz=updated_group.oqituvchi_foiz)
                StudentGroupHistory.objects.filter(
                    group=updated_group,
                    end_date__isnull=True
                ).update(oqituvchi_foiz=updated_group.oqituvchi_foiz)

            if updated_group.kurs_narxi != old_narx:
                affected_enrollments = enrollments.filter(Q(kurs_narhi=0) | Q(kurs_narhi=old_narx))
                for enr in affected_enrollments:
                    enr.kurs_narhi = updated_group.kurs_narxi
                    enr.save(update_fields=["kurs_narhi"])
                    StudentGroupHistory.objects.filter(
                        student=enr.student,
                        group=updated_group,
                        end_date__isnull=True
                    ).update(kurs_narxi=updated_group.kurs_narxi)
                    sync_tuition_fee(enr, new_fee=updated_group.kurs_narxi)

        # Barcha faol enrollmentlarning monthly_lessons va lesson_pattern ni guruh bilan sinxronlaymiz
        # va joriy oy TuitionMonth feesini qayta hisoblaymiz.
        from education.services.tuition import ensure_tuition_month
        from education.models import GroupSchedule
        today = timezone.localdate()
        cur_month = today.replace(day=1)
        active_enrollments = list(
            Enrollment.objects.filter(group=updated_group, is_active=True)
            .select_related("group", "student")
        )
        for enr in active_enrollments:
            update_fields = ["monthly_lessons"]
            enr.monthly_lessons = new_oy_dars_soni
            # oy_dars_soni belgilangan bo'lsa, lesson_pattern "group" bo'lishi shart
            # (GroupSchedule bo'lmasa ham — calendar proportion ishlatiladi)
            if new_oy_dars_soni > 0 and enr.lesson_pattern in ("odd", "even", "daily", None, ""):
                enr.lesson_pattern = Enrollment.LESSON_PATTERN_GROUP
                update_fields.append("lesson_pattern")
            enr.save(update_fields=update_fields)
            try:
                ensure_tuition_month(enr, cur_month)
            except Exception:
                pass

        messages.success(request, "✅ Guruh yangilandi.")
        return redirect("education:group_detail", pk=g.id)

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Guruhni tahrirlash",
        "description": "Guruh ma'lumotlarini tahrirlash",
        "group": g,
        "has_manual_oy_dars_soni": has_manual_oy_dars_soni,
    })



@login_required
@require_POST
def group_generate_month_debt(request, pk):
    """Guruhning barcha aktiv o'quvchilari uchun joriy oy TuitionMonth ni yaratadi.

    Faqat director/manager/superuser ishlatishi mumkin.
    Guruh oy o'rtasidan ochilgan va o'quvchilarda qarz yozilmagan holatlar uchun.
    """
    if not (request.user.is_superuser or getattr(request.user, "role", None) in ("director", "manager")):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("education:group_edit", pk=pk)

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    today = timezone.localdate()
    cur_month = month_first_day(today)

    enrollments = (
        Enrollment.objects
        .filter(group=g, is_active=True, is_deleted=False)
        .select_related("student")
    )
    created_count = 0
    updated_count = 0
    for enr in enrollments:
        try:
            fee_field = tuition_month_fee_field()
            existing = TuitionMonth.all_objects.filter(
                enrollment=enr, month=cur_month, is_deleted=False
            ).first()
            old_fee = int(getattr(existing, fee_field, 0) or 0) if existing else None
            tm = ensure_tuition_month(enr, cur_month)
            new_fee = int(getattr(tm, fee_field, 0) or 0)
            if old_fee is None:
                created_count += 1
            elif old_fee != new_fee:
                updated_count += 1
        except Exception:
            pass

    month_label = today.strftime("%Y-%B").replace(
        today.strftime("%B"),
        ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
         "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"][today.month - 1]
    )
    messages.success(
        request,
        f"✅ {g.nom} guruhi uchun {month_label} oyi qarzlari yozildi: "
        f"{created_count} yangi, {updated_count} yangilangan."
    )
    return redirect("education:group_edit", pk=pk)



@login_required
def group_list(request):
    """
    Barcha guruhlar ro'yxati.
    """
    rows = (
        Group.objects
        .select_related("center", "oqituvchi", "category_obj")
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)),
            sana=Coalesce(F("course_start_date"), Cast(F("tuzilgan"), models.DateField()))
        )
        .order_by("-id")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    page_num = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', '10')

    if page_size == "all":
        paginator = Paginator(rows, max(1, min(rows.count(), 200)))
    else:
        try:
            page_size = int(page_size)
            if page_size < 1 or page_size > 200:
                page_size = 10
        except ValueError:
            page_size = 10
        paginator = Paginator(rows, page_size)

    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    can_manage = request.user.is_superuser or request.user.role in ["director", "manager", "teacher"]

    context = {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_size,
        "can_manage": can_manage,
    }
    return render(request, "education/groups.html", context)



def get_group_price(request, pk):
    try:
        qs = Group.objects.all()
        from core.tenant import get_request_center
        center = get_request_center(request)
        if center:
            qs = qs.filter(center=center)
        group = qs.get(pk=pk)
        return JsonResponse({
            "price": group.kurs_narxi,
            "oqituvchi_foiz": group.oqituvchi_foiz,
            "monthly_lessons": group.oy_dars_soni,
            "group_name": group.nom,
            "course_id": getattr(group, "category_obj_id", None),
            "course_name": getattr(getattr(group, "category_obj", None), "name", ""),
        })
    except Group.DoesNotExist:
        return JsonResponse({
            "price": 0,
            "oqituvchi_foiz": 40,
            "monthly_lessons": 12,
            "group_name": "",
            "course_id": None,
            "course_name": "",
        })



@login_required
def group_add(request):
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo'q.")
        return redirect("education:groups")

    from core.tenant import get_request_center
    center = get_request_center(request) or getattr(request.user, "center", None)
    from billing.services import center_has_feature
    has_manual_oy_dars_soni = center_has_feature(center, "manual_oy_dars_soni") if center else False

    form = GroupForm(request.POST or None, center=center)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        if not group.center_id:
            group.center = center
        schedule_mode = form.cleaned_data.get("schedule_mode", "")
        custom_days = form.cleaned_data.get("custom_days") or []
        if schedule_mode in {"odd", "even", "custom"}:
            day_count = len(custom_days) if schedule_mode == "custom" else 3
            group.lessons_per_week = day_count
            if has_manual_oy_dars_soni:
                if not group.oy_dars_soni:
                    group.oy_dars_soni = day_count * 4
            else:
                group.oy_dars_soni = 12
        if not group.oy_dars_soni:
            group.oy_dars_soni = 12

        # O'qituvchi tanlanganda foiz teacher profilidan olinadi.
        if group.oqituvchi and getattr(group.oqituvchi, "oqituvchi_foizi", None) is not None:
            group.oqituvchi_foiz = group.oqituvchi.oqituvchi_foizi
        elif not group.oqituvchi_foiz:
            group.oqituvchi_foiz = 40

        from education.services.group_schedule_service import (
            apply_group_duration_defaults,
            sync_simple_group_schedule,
        )
        apply_group_duration_defaults(group)
        group.save()
        sync_simple_group_schedule(
            group=group,
            schedule_mode=schedule_mode,
            custom_days=custom_days,
            start_time=form.cleaned_data.get("schedule_start_time"),
            end_time=form.cleaned_data.get("schedule_end_time"),
            room=form.cleaned_data.get("schedule_room"),
        )
        messages.success(request, "✅ Guruh muvaffaqiyatli qo'shildi.")
        return redirect("education:groups")

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Yangi guruh qo'shish",
        "has_manual_oy_dars_soni": has_manual_oy_dars_soni,
    })



@login_required
def group_delete(request, pk):
    """
    Guruhni o'chirish — tasdiq bilan.
    """
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        category = getattr(group, "category_obj", None)
        group.delete()
        messages.success(request, "🗑️ Guruh o'chirildi.")

        if category:
            return redirect("education:category_detail", category_id=category.id)
        return redirect("education:groups")

    return render(request, "education/group_delete_confirm.html", {"group": group})



@login_required
def my_groups(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    # Asosiy o'qituvchi yoki support teacher sifatida biriktirilgan barcha guruhlar
    rows = (
        Group.objects.filter(
            Q(oqituvchi=request.user) | Q(support_teacher=request.user),
            is_archived=False,
        )
        .select_related("center", "oqituvchi", "category_obj")
        .annotate(student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)))
        .distinct()
        .order_by("nom")
    )
    if center:
        rows = rows.filter(center=center)
    return render(request, "education/my_groups.html", {"rows": rows, "is_support": True})

