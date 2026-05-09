from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _director_or_manager(user) -> bool:
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager")


@login_required
def churn_api_summary(request):
    """Boshqaruv sahifasi uchun churn statistikasi (JSON)."""
    center = getattr(request, 'center', None) or getattr(request.user, 'center', None)
    if not center:
        return JsonResponse({'total': 0, 'high': 0, 'medium': 0, 'low': 0})
    from .models import ChurnRisk
    qs = ChurnRisk.objects.filter(center=center)
    return JsonResponse({
        'total':  qs.count(),
        'high':   qs.filter(risk_level='high').count(),
        'medium': qs.filter(risk_level='medium').count(),
        'low':    qs.filter(risk_level='low').count(),
    })

@require_POST
@login_required
def notifications_mark_read_api(request):
    try:
        # Assuming we can just mark all unread as read for the user
        from .models import Notification
        updated_count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True, 'count': updated_count})
    except Exception:
        logger.exception("notifications_mark_read_api failed")
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


@login_required
def exam_api_summary(request):
    try:
        from core.tenant import get_request_center
        from education.models import CertificateRecord, ExamResult, ExamSession

        center = get_request_center(request)
        if not center:
            return JsonResponse({
                "total_sessions": 0,
                "this_month_completed": 0,
                "avg_percent": 0,
                "pending_certificates": 0,
            })

        if not request.user.is_superuser and getattr(request.user, "role", None) not in ("manager", "director"):
            return JsonResponse({"detail": "forbidden"}, status=403)

        today = timezone.localdate()
        month_start = today.replace(day=1)

        total = ExamSession.objects.filter(center=center).count()
        this_month = ExamSession.objects.filter(
            center=center,
            exam_date__gte=month_start,
            status="completed",
        ).count()
        avg_pct = (
            ExamResult.objects.filter(
                center=center,
                exam_date__gte=month_start,
            )
            .exclude(percent__isnull=True)
            .aggregate(a=Avg("percent"))["a"] or 0
        )
        pending_certs = CertificateRecord.objects.filter(
            center=center,
            status="draft",
        ).count()

        return JsonResponse({
            "total_sessions": total,
            "this_month_completed": this_month,
            "avg_percent": round(float(avg_pct), 1),
            "pending_certificates": pending_certs,
        })
    except Exception:
        logger.exception("exam_api_summary failed")
        return JsonResponse({"detail": "error"}, status=500)


@login_required
def dashboard_quick_stats(request):
    """
    Director va Manager dashboard uchun tezkor statistikalar (JSON).

    Eski fieldlar (director boshqaruv): today_income, debtors, active_groups,
      attendance_pct, attendance_label.
    Yangi fieldlar (manager KPI grid uchun, home view deferred bo'lganidan
      keyin AJAX orqali yuklanadi): students, teachers, products,
      pending_requests.
    """
    if not _director_or_manager(request.user):
        return JsonResponse({"detail": "forbidden"}, status=403)

    from django.db.models import Count, Q
    from accounts.models import User
    from core.tenant import get_request_center
    from core.dashboard_metrics import (
        get_center_active_groups_count,
        get_center_attendance_snapshot,
        get_center_debtors_count,
        get_center_today_income,
        month_start,
    )
    from store.models import Product, PurchaseRequest

    center = get_request_center(request)
    if not center:
        return JsonResponse({"detail": "center_not_found"}, status=403)

    today = timezone.localdate()
    current_month = month_start(today)
    attendance = get_center_attendance_snapshot(center, today)

    # ✅ Manager KPI — 3 alohida count() emas, 1 aggregate query.
    user_agg = User.objects.filter(center=center).aggregate(
        teachers=Count("id", filter=Q(role="teacher")),
        students=Count("id", filter=Q(role="student", is_archived=False)),
    )
    pending_status = getattr(PurchaseRequest, "PENDING", "pending")

    return JsonResponse(
        {
            # director
            "today_income": get_center_today_income(center, today),
            "debtors": get_center_debtors_count(center, current_month),
            "active_groups": get_center_active_groups_count(center),
            "attendance_pct": attendance["pct"],
            "attendance_label": attendance["label"],
            # manager KPI grid
            "students": user_agg["students"] or 0,
            "teachers": user_agg["teachers"] or 0,
            "products": Product.objects.filter(center=center).count(),
            "pending_requests": PurchaseRequest.objects.filter(
                center=center, status=pending_status,
            ).count(),
        }
    )


@login_required
def dashboard_low_activity_api(request):
    """Manager dashboard 'Faolligi Past Talabalar' bloki — deferred load."""
    if not _director_or_manager(request.user):
        return JsonResponse({"detail": "forbidden"}, status=403)

    from core.tenant import get_request_center
    from core.views import _get_low_activity_data

    center = get_request_center(request)
    if not center:
        return JsonResponse({"items": []})

    items = _get_low_activity_data(center, limit=5)
    return JsonResponse({"items": items})


def _pct_change(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return None if current else 0.0
    return round((current - previous) / previous * 100, 1)


@login_required
def manager_dashboard_api(request):
    """Manager paneli uchun to'liq dashboard ma'lumotlari (KPI + chart + feed).

    Manager uchun qoidalar:
      • Pul/foyda ko'rsatkichlari ochilmaydi (faqat to'lov SONI, summa emas).
      • Hamma narsa center scope'da.
    """
    if not _director_or_manager(request.user):
        return JsonResponse({"detail": "forbidden"}, status=403)

    from datetime import date, datetime, time as _time, timedelta
    from django.db.models import Count, Q, F, Sum
    from django.db.models.functions import Coalesce
    from accounts.models import User
    from core.tenant import get_request_center
    from core.dashboard_metrics import (
        active_groups_for_center,
        attendance_for_center,
        attendance_present_filter,
        get_center_attendance_snapshot,
        get_center_debtors_count,
        month_start,
        payments_for_center,
        active_enrollments_for_center,
    )
    from education.models import Group, Attendance
    from store.models import Lead

    center = get_request_center(request)
    if not center:
        return JsonResponse({"detail": "center_not_found"}, status=403)

    today = timezone.localdate()
    cur_month = month_start(today)
    prev_month = month_start(cur_month - timedelta(days=1))
    present_q = attendance_present_filter()

    # ── Sana filteri (query params: from / to) ──────────────────────
    def _parse_d(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    d_from = _parse_d(request.GET.get("from")) or cur_month
    d_to   = _parse_d(request.GET.get("to"))   or today
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    period_days = max(1, (d_to - d_from).days + 1)
    # Oldingi solishtirish davri (delta uchun): joriy davrdan oldingi xuddi shu uzunlikdagi oraliq
    prev_to_d   = d_from - timedelta(days=1)
    prev_from_d = prev_to_d - timedelta(days=period_days - 1)

    # ── KPI ─────────────────────────────────────────────────────────
    students_qs = User.objects.filter(center=center, role="student", is_archived=False)
    # Tanlangan davr oxiridagi aktiv o'quvchilar (snapshot)
    active_students = students_qs.filter(date_joined__date__lte=d_to).count()
    prev_active_students = students_qs.filter(date_joined__date__lte=prev_to_d).count()

    new_this_month = students_qs.filter(
        date_joined__date__range=(d_from, d_to)
    ).count()
    new_prev_month = students_qs.filter(
        date_joined__date__range=(prev_from_d, prev_to_d)
    ).count()

    # Tanlangan davr davomat % (avg)
    try:
        att_qs_period = Attendance.objects.filter(group__center=center, date__range=(d_from, d_to))
        att_total_p = att_qs_period.count()
        att_present_p = att_qs_period.filter(present_q).count()
        att_pct_today = round(att_present_p * 100 / att_total_p) if att_total_p else 0
        att_today = {"pct": att_pct_today, "label": f"{att_present_p}/{att_total_p}"}
    except Exception:
        att_today = {"pct": 0, "label": "0/0"}
        att_pct_today = 0

    try:
        att_qs_prev = Attendance.objects.filter(group__center=center, date__range=(prev_from_d, prev_to_d))
        att_total_pp = att_qs_prev.count()
        att_present_pp = att_qs_prev.filter(present_q).count()
        att_pct_yest = round(att_present_pp * 100 / att_total_pp) if att_total_pp else 0
    except Exception:
        att_pct_yest = 0

    # Qarzdorlar — d_to oyiga snapshot
    debtors_now = get_center_debtors_count(center, d_to.replace(day=1))
    debtors_prev = get_center_debtors_count(center, prev_to_d.replace(day=1))

    # Faol guruhlar (snapshot)
    active_groups = active_groups_for_center(center).count()

    # Lidlar (tanlangan davr ichida vs oldingi davr)
    leads_qs = Lead.objects.filter(center=center)
    leads_week = leads_qs.filter(qoshilgan_sana__date__range=(d_from, d_to)).count()
    leads_prev_week = leads_qs.filter(qoshilgan_sana__date__range=(prev_from_d, prev_to_d)).count()
    leads_total = leads_qs.count()

    # To'lovlar — soni (tanlangan davr ichida)
    pay_qs = payments_for_center(center)
    pays_today = pay_qs.filter(paid_date__range=(d_from, d_to)).count()
    pays_yest = pay_qs.filter(paid_date__range=(prev_from_d, prev_to_d)).count()

    # ── Bugungi darslar (groups with class today) ───────────────────
    # GroupSchedule.weekday: 1=Mon..7=Sun; Python weekday(): 0=Mon..6=Sun
    weekday = today.weekday() + 1  # Python 0-based → GroupSchedule 1-based
    today_groups = []
    try:
        from django.db.models import Prefetch
        from education.models import GroupSchedule

        groups_qs = active_groups_for_center(center).select_related("oqituvchi").prefetch_related(
            Prefetch("schedules", queryset=GroupSchedule.objects.all(), to_attr="_schedules_cache")
        )[:200]
        # Bugungi Attendance'ni bitta query bilan olish
        group_ids = [g.pk for g in groups_qs]
        att_today_rows = (
            Attendance.objects.filter(group_id__in=group_ids, date=today)
            .values("group_id")
            .annotate(
                total=Count("id"),
                present_count=Count("id", filter=present_q),
            )
        )
        att_today_map = {row["group_id"]: row for row in att_today_rows}

        for g in groups_qs:
            schedule = getattr(g, "_schedules_cache", [])
            has_today = any(getattr(sc, "weekday", -1) == weekday for sc in schedule)
            if not has_today:
                continue
            att_row = att_today_map.get(g.pk, {})
            att_total = att_row.get("total", 0)
            att_present = att_row.get("present_count", 0)
            taken = att_total > 0
            teacher = getattr(g, "oqituvchi", None)
            teacher_name = ""
            if teacher:
                teacher_name = (getattr(teacher, "ism", "") or "") + " " + (getattr(teacher, "familya", "") or "")
                teacher_name = teacher_name.strip() or getattr(teacher, "username", "")
            time_label = ""
            for sc in schedule:
                if getattr(sc, "weekday", -1) == weekday:
                    st = getattr(sc, "start_time", None)
                    if st:
                        time_label = st.strftime("%H:%M")
                    break
            today_groups.append({
                "id": g.pk,
                "name": getattr(g, "nom", "") or f"Guruh #{g.pk}",
                "teacher": teacher_name,
                "time": time_label,
                "taken": taken,
                "present": att_present,
                "total": att_total,
                "pct": round(att_present * 100 / att_total) if att_total else 0,
            })
    except Exception:
        logger.exception("manager_dashboard_api today_groups failed")
        today_groups = []
    today_groups.sort(key=lambda r: (r["taken"], r["time"] or "99:99"))

    # ── Davomat dinamikasi (oxirgi 30 kun) ──────────────────────────
    # N+1 fix: 30 marta alohida query o'rniga bitta aggregate query
    att_labels = []
    att_values = []
    try:
        thirty_days_ago = today - timedelta(days=29)
        att_30_rows = (
            attendance_for_center(center)
            .filter(date__gte=thirty_days_ago, date__lte=today)
            .values("date")
            .annotate(
                total=Count("id"),
                present_count=Count("id", filter=present_q),
            )
        )
        att_30_map = {row["date"]: row for row in att_30_rows}
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            row = att_30_map.get(d, {})
            total_d = row.get("total", 0)
            present_d = row.get("present_count", 0)
            pct_d = round(present_d * 100 / total_d) if total_d else 0
            att_labels.append(d.strftime("%d.%m"))
            att_values.append(pct_d)
    except Exception:
        att_labels = []
        att_values = []

    # ── Lead funnel ─────────────────────────────────────────────────
    funnel = {"new": 0, "contacted": 0, "trial": 0, "registered": 0}
    try:
        funnel["new"] = leads_qs.count()
        funnel["contacted"] = leads_qs.filter(
            Q(activities__isnull=False)
        ).distinct().count()
        funnel["trial"] = leads_qs.filter(
            Q(trial_lessons__isnull=False)
        ).distinct().count()
        funnel["registered"] = leads_qs.filter(
            Q(converted_to_student=True) | Q(converted_user__isnull=False)
        ).count()
    except Exception:
        pass

    # ── Top guruhlar to'liqlik bo'yicha ─────────────────────────────
    # N+1 fix: har guruh uchun alohida _Pay.aggregate() o'rniga bitta annotate query
    top_groups = []
    top_groups_full = []  # Director-style format ("Eng yaxshi guruhlar" jadvali uchun)
    try:
        from education.models import Payment as _Pay
        gqs = (
            active_groups_for_center(center)
            .annotate(
                enrolled=Count(
                    "enrollments",
                    filter=Q(enrollments__is_active=True, enrollments__is_deleted=False),
                    distinct=True,
                ),
                revenue=Coalesce(
                    Sum(
                        "group_payments__summa",
                        filter=Q(group_payments__paid_date__range=(d_from, d_to)),
                    ),
                    0,
                ),
            )
            .select_related("oqituvchi")[:80]
        )
        for g in gqs:
            cap = int(getattr(g, "max_students", 0) or 0)
            enr = int(getattr(g, "enrolled", 0) or 0)
            pct = round(enr * 100 / cap) if cap else 0
            teacher = getattr(g, "oqituvchi", None)
            t_name = ""
            if teacher:
                t_name = ((getattr(teacher, "ism", "") or "") + " " + (getattr(teacher, "familya", "") or "")).strip()
            top_groups.append({
                "id": g.pk,
                "name": getattr(g, "nom", "") or f"Guruh #{g.pk}",
                "teacher": t_name or "—",
                "enrolled": enr,
                "capacity": cap,
                "fill_pct": pct,
            })

            # Director-style row (initials + capacity + revenue)
            name = getattr(g, "nom", "") or f"Guruh #{g.pk}"
            words = [w for w in name.split() if w]
            if len(words) >= 2:
                initials = (words[0][0] + words[1][0]).upper()
            elif words:
                initials = words[0][:2].upper()
            else:
                initials = "G"
            rev_sum = int(getattr(g, "revenue", 0) or 0)
            if pct >= 95:
                status_lbl = "To'ldirilgan"
            elif enr:
                status_lbl = "Faol"
            else:
                status_lbl = "To'ldirilmoqda"
            top_groups_full.append({
                "id": g.pk,
                "name": name,
                "initials": initials,
                "teacher": t_name or "—",
                "status": status_lbl,
                "enrolled": enr,
                "capacity": max(cap, enr),
                "fill_percent": pct,
                "revenue": rev_sum,
            })

        top_groups.sort(key=lambda r: -r["fill_pct"])
        top_groups = top_groups[:8]
        top_groups_full.sort(key=lambda r: (-r["fill_percent"], -r["enrolled"], -r["revenue"], r["name"]))
        top_groups_full = top_groups_full[:5]
    except Exception:
        logger.exception("manager_dashboard_api top_groups failed")
        top_groups = []
        top_groups_full = []

    # ── So'nggi faollik (director-style: payment / absence / lead) ─
    def _activity_dt(d, t=None):
        if not d:
            return timezone.now()
        try:
            dt = datetime.combine(d, t or _time.min)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except Exception:
            return timezone.now()

    def _name(user):
        if not user:
            return "—"
        full = ((getattr(user, "ism", "") or "") + " " + (getattr(user, "familya", "") or "")).strip()
        return full or getattr(user, "username", "—") or "—"

    recent_activity = []
    try:
        recent_pays_a = pay_qs.filter(paid_date__range=(d_from, d_to)).select_related("student", "group").order_by(
            "-paid_date", "-paid_time", "-id"
        )[:8]
        for p in recent_pays_a:
            paid_at = _activity_dt(getattr(p, "paid_date", None), getattr(p, "paid_time", None))
            recent_activity.append({
                "type": "payment",
                "title": f"{_name(getattr(p, 'student', None))} to'lov qildi",
                "subtitle": getattr(getattr(p, "group", None), "nom", "") or "Guruh",
                "amount": int(getattr(p, "summa", 0) or 0),
                "timestamp": paid_at.isoformat(),
                "_sort": paid_at,
            })

        try:
            absent_filter = Q(status__in=["absent_excused", "absent_unexcused"]) | Q(present=False, forced=False)
            recent_abs = (
                Attendance.objects.filter(group__center=center, date__range=(d_from, d_to))
                .filter(absent_filter)
                .select_related("student", "group")
                .order_by("-date", "-id")[:8]
            )
            for a in recent_abs:
                happened_at = _activity_dt(a.date, _time(23, 59))
                recent_activity.append({
                    "type": "absence",
                    "title": f"{_name(getattr(a, 'student', None))} darsga kelmadi",
                    "subtitle": getattr(getattr(a, "group", None), "nom", "") or "Guruh",
                    "amount": None,
                    "timestamp": happened_at.isoformat(),
                    "_sort": happened_at,
                })
        except Exception:
            pass

        try:
            converted_q = leads_qs.filter(
                Q(converted_to_student=True) | Q(converted_user__isnull=False),
                Q(converted_at__date__range=(d_from, d_to)) | Q(qoshilgan_sana__date__range=(d_from, d_to)),
            ).select_related("yonalish", "manba").order_by("-converted_at", "-qoshilgan_sana", "-id")[:8]
            for L in converted_q:
                converted_at = (
                    getattr(L, "converted_at", None)
                    or getattr(L, "qoshilgan_sana", None)
                    or timezone.now()
                )
                subtitle = (
                    getattr(getattr(L, "yonalish", None), "nom", "")
                    or getattr(getattr(L, "manba", None), "nom", "")
                    or "CRM"
                )
                full_name = ""
                try:
                    full_name = L.full_name or str(L)
                except Exception:
                    full_name = str(L)
                recent_activity.append({
                    "type": "lead",
                    "title": f"{full_name} ro'yxatdan o'tdi",
                    "subtitle": subtitle,
                    "amount": None,
                    "timestamp": (converted_at.isoformat() if hasattr(converted_at, "isoformat") else str(converted_at)),
                    "_sort": converted_at,
                })
        except Exception:
            pass

        recent_activity.sort(key=lambda x: x["_sort"], reverse=True)
        recent_activity = [
            {k: v for k, v in item.items() if k != "_sort"}
            for item in recent_activity[:7]
        ]
    except Exception:
        logger.exception("manager_dashboard_api recent_activity failed")
        recent_activity = []

    # ── Eski (oddiy) so'nggi faollik feed ───────────────────────────
    recent = []
    try:
        # Yangi to'lovlar
        recent_pays = pay_qs.select_related("student").order_by("-id")[:6]
        for p in recent_pays:
            stu = getattr(p, "student", None)
            stu_name = ""
            if stu:
                stu_name = ((getattr(stu, "ism", "") or "") + " " + (getattr(stu, "familya", "") or "")).strip() or getattr(stu, "username", "")
            recent.append({
                "type": "payment",
                "title": "To'lov qabul qilindi",
                "sub": stu_name or "Noma'lum",
                "ts": p.paid_date.isoformat() if p.paid_date else "",
                "icon": "money-bill-wave",
                "tone": "green",
            })
        # Yangi lidlar
        recent_leads = leads_qs.order_by("-qoshilgan_sana")[:4]
        for L in recent_leads:
            recent.append({
                "type": "lead",
                "title": "Yangi lid qo'shildi",
                "sub": getattr(L, "ism", "") or "Lid",
                "ts": L.qoshilgan_sana.isoformat() if L.qoshilgan_sana else "",
                "icon": "phone-volume",
                "tone": "rose",
            })
        # Yangi studentlar
        recent_students = students_qs.order_by("-date_joined")[:4]
        for s in recent_students:
            full = ((getattr(s, "ism", "") or "") + " " + (getattr(s, "familya", "") or "")).strip()
            recent.append({
                "type": "student",
                "title": "Yangi o'quvchi qo'shildi",
                "sub": full or getattr(s, "username", ""),
                "ts": s.date_joined.isoformat() if s.date_joined else "",
                "icon": "user-graduate",
                "tone": "blue",
            })
        recent.sort(key=lambda r: r["ts"] or "", reverse=True)
        recent = recent[:10]
    except Exception:
        logger.exception("manager_dashboard_api recent failed")
        recent = []

    # ── E'tibor talab qiladigan o'quvchilar ─────────────────────────
    attention = []
    try:
        from core.views import _get_low_activity_data
        low = _get_low_activity_data(center, limit=6) or []
        for s in low:
            attention.append({
                "id": s.get("student_id"),
                "name": s.get("name"),
                "phone": s.get("phone", ""),
                "course": s.get("course", ""),
                "rate": int(s.get("status", 0) or 0),
                "avatar": s.get("avatar", ""),
            })
    except Exception:
        attention = []

    return JsonResponse({
        "kpi": {
            "active_students": active_students,
            "new_this_month": new_this_month,
            "att_pct_today": att_pct_today,
            "att_today_label": att_today.get("label", "0/0"),
            "debtors": debtors_now,
            "active_groups": active_groups,
            "leads_week": leads_week,
            "leads_total": leads_total,
            "pays_today": pays_today,
            "changes": {
                "active_students": _pct_change(active_students, prev_active_students),
                "new_students": _pct_change(new_this_month, new_prev_month),
                "att_pct": _pct_change(att_pct_today, att_pct_yest),
                "debtors": _pct_change(debtors_now, debtors_prev),
                "leads": _pct_change(leads_week, leads_prev_week),
                "pays": _pct_change(pays_today, pays_yest),
            },
        },
        "charts": {
            "att_labels": att_labels,
            "att_values": att_values,
            "funnel": [funnel["new"], funnel["contacted"], funnel["trial"], funnel["registered"]],
            "funnel_labels": ["Yangi lid", "Bog'langan", "Trial dars", "Ro'yxatdan o'tdi"],
            "top_groups": top_groups,
        },
        "today_groups": today_groups,
        "recent": recent,
        "top_groups_full": top_groups_full,
        "recent_activity": recent_activity,
        "attention": attention,
        "period": {
            "from": d_from.isoformat(),
            "to":   d_to.isoformat(),
            "days": period_days,
        },
        "synced_at": timezone.now().isoformat(),
    })


@login_required
def dashboard_student_init_api(request):
    """Student dashboard boshlangan'ich ma'lumotlar — balance + last actions."""
    from core.tenant import get_request_center
    from core.views import _student_last_actions
    from chaqmoq.views import _get_balances_with_legacy_fallback

    user = request.user
    if getattr(user, "role", None) != "student" and not user.is_superuser:
        return JsonResponse({"detail": "forbidden"}, status=403)

    center = get_request_center(request) or getattr(user, "center", None)
    balance = _get_balances_with_legacy_fallback([user.id], center=center).get(user.id, 0)
    last_actions = _student_last_actions(user.id, center=center)

    # created_at datetime → ISO string (JSON serialize uchun)
    for a in last_actions:
        ca = a.get("created_at")
        if ca is not None and not isinstance(ca, str):
            try:
                a["created_at"] = ca.isoformat()
            except Exception:
                a["created_at"] = str(ca)

    return JsonResponse({
        "balance": int(balance or 0),
        "last_actions": last_actions,
    })
