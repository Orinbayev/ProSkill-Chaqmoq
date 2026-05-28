from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.db import models as db_models
from django.db.models import Avg, Q
from django.utils import timezone
import json
import logging
import random

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


# ─────────────────────── Student Panel APIs ──────────────────────────────────

def _sp_student_only(request):
    role = getattr(request.user, "role", None)
    if role != "student" and not request.user.is_superuser:
        return JsonResponse({"detail": "forbidden"}, status=403)
    return None


def _sp_center(request):
    from core.tenant import get_request_center
    return get_request_center(request) or getattr(request.user, "center", None)


@login_required
def student_panel_dashboard_api(request):
    """Student panel — KPI cards + next lessons."""
    err = _sp_student_only(request)
    if err:
        return err

    from datetime import date, timedelta
    from core.mobile_api import (
        _student_open_debt,
        _student_attendance_summary,
        _student_groups,
    )
    from chaqmoq.views import _get_balances_with_legacy_fallback
    from education.models import GroupSchedule

    user = request.user
    center = _sp_center(request)

    balance = _get_balances_with_legacy_fallback([user.id], center=center).get(user.id, 0)
    debt = _student_open_debt(user, center)

    today = timezone.localdate()
    att = _student_attendance_summary(
        user, center,
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=1),
    )
    att_rate = att.get("recent_attendance_rate", att.get("attendance_rate", 0))

    groups = _student_groups(user, center)
    active_groups = [g for g in groups if g.get("is_active")]
    active_ids = [g["id"] for g in active_groups]

    # Next lessons: today + tomorrow (GroupSchedule weekday: Mon=1, Sun=7)
    tomorrow = today + timedelta(days=1)
    today_wd = today.weekday() + 1      # Mon→1 … Sun→7
    tomorrow_wd = tomorrow.weekday() + 1

    schedules = (
        GroupSchedule.objects
        .filter(group_id__in=active_ids, weekday__in=[today_wd, tomorrow_wd])
        .select_related("group", "group__oqituvchi")
        .order_by("weekday", "start_time")
    )
    next_lessons = []
    for sch in schedules:
        teacher = sch.group.oqituvchi
        next_lessons.append({
            "group_name": sch.group.nom,
            "day": "Bugun" if sch.weekday == today_wd else "Ertaga",
            "start_time": sch.start_time.strftime("%H:%M"),
            "end_time": sch.end_time.strftime("%H:%M") if sch.end_time else "",
            "room": sch.room or "",
            "teacher": teacher.get_full_name() if teacher else "",
        })

    return JsonResponse({
        "balance": int(balance or 0),
        "debt": int(debt),
        "att_rate": att_rate,
        "att_present": att.get("recent_present_lessons", 0),
        "att_total": att.get("recent_total_lessons", 0),
        "groups_total": len(groups),
        "groups_active": len(active_groups),
        "payment_status": "debt" if debt > 0 else "paid",
        "next_lessons": next_lessons,
    })


@login_required
def student_panel_groups_api(request):
    """Student panel — groups list with schedules."""
    err = _sp_student_only(request)
    if err:
        return err

    from core.mobile_api import _student_groups
    from education.models import GroupSchedule

    user = request.user
    center = _sp_center(request)

    groups = _student_groups(user, center)
    group_ids = [g["id"] for g in groups]

    schedules_qs = (
        GroupSchedule.objects
        .filter(group_id__in=group_ids)
        .order_by("weekday", "start_time")
    )
    sched_map: dict[int, list] = {}
    for sch in schedules_qs:
        sched_map.setdefault(sch.group_id, []).append({
            "weekday": sch.weekday,
            "weekday_name": sch.weekday_uz,
            "start_time": sch.start_time.strftime("%H:%M"),
            "end_time": sch.end_time.strftime("%H:%M") if sch.end_time else "",
            "room": sch.room or "",
        })

    for g in groups:
        g["schedules"] = sched_map.get(g["id"], [])

    return JsonResponse({"groups": groups})


@login_required
def student_panel_attendance_api(request):
    """Student panel — monthly attendance calendar."""
    err = _sp_student_only(request)
    if err:
        return err

    from datetime import date, timedelta
    from collections import defaultdict
    import calendar as cal_mod
    from core.mobile_api import _student_monthly_attendance_summary, _add_months
    from education.models import Attendance
    from django.db.models import Q

    user = request.user
    center = _sp_center(request)

    month_str = request.GET.get("month", "")
    if month_str:
        try:
            month_start = date.fromisoformat(month_str + "-01")
        except ValueError:
            return JsonResponse({"error": "Invalid month format. Use YYYY-MM."}, status=400)
    else:
        month_start = timezone.localdate().replace(day=1)

    month_end = _add_months(month_start, 1)
    summary = _student_monthly_attendance_summary(user, center, month_start)

    att_qs = (
        Attendance.objects
        .filter(student=user, group__center=center, date__gte=month_start, date__lt=month_end)
        .values("date", "status", "present", "forced")
    )

    day_map: dict[str, list] = defaultdict(list)
    for att in att_qs:
        is_present = att.get("forced") or att.get("present") or att.get("status") == "present"
        day_map[att["date"].isoformat()].append("present" if is_present else att.get("status", "absent"))

    calendar_days = []
    cur = month_start
    while cur < month_end:
        iso = cur.isoformat()
        entries = day_map.get(iso, [])
        if entries:
            all_p = all(e == "present" for e in entries)
            any_p = any(e == "present" for e in entries)
            status = "present" if all_p else ("partial" if any_p else "absent")
        else:
            status = "no_class"
        calendar_days.append({"date": iso, "day": cur.day, "weekday": cur.weekday(), "status": status})
        cur += timedelta(days=1)

    return JsonResponse({
        "month": month_start.strftime("%Y-%m"),
        "summary": summary,
        "calendar": calendar_days,
    })


@login_required
def student_panel_payments_api(request):
    """Student panel — payment history + current month status."""
    err = _sp_student_only(request)
    if err:
        return err

    from core.mobile_api import _student_open_debt
    from education.models import Payment

    user = request.user
    center = _sp_center(request)

    debt = _student_open_debt(user, center)

    payments = (
        Payment.objects
        .filter(student=user, center=center, is_deleted=False)
        .select_related("group")
        .order_by("-paid_date", "-id")[:30]
    )
    payments_list = [
        {
            "id": p.id,
            "group_name": p.group.nom if p.group else "",
            "amount": p.summa,
            "payment_type": p.payment_type,
            "paid_date": p.paid_date.isoformat(),
            "note": p.note or "",
        }
        for p in payments
    ]

    return JsonResponse({
        "current_debt": int(debt),
        "payment_status": "debt" if debt > 0 else "paid",
        "payments": payments_list,
    })


# ─────────────────────── Parent Panel APIs ───────────────────────────────────

def _pp_resolve_child(request, child_pk: int):
    """Returns (child, center) or JsonResponse error."""
    from accounts.models import User
    user = request.user
    role = getattr(user, "role", None)
    if role != "parent" and not user.is_superuser:
        return None, None, JsonResponse({"detail": "forbidden"}, status=403)

    center = _sp_center(request)
    child_qs = user.children.filter(pk=child_pk, role="student")
    if center:
        child_qs = child_qs.filter(center=center)
    try:
        child = child_qs.get()
    except Exception:
        return None, None, JsonResponse({"detail": "child not found"}, status=404)
    return child, center, None


@login_required
def parent_panel_children_api(request):
    """Parent panel — list of linked children with basic stats."""
    from datetime import timedelta
    from core.mobile_api import _student_open_debt, _student_balance, _student_attendance_summary

    user = request.user
    if getattr(user, "role", None) != "parent" and not user.is_superuser:
        return JsonResponse({"detail": "forbidden"}, status=403)

    center = _sp_center(request)
    children = user.children.filter(role="student").order_by("ism", "familya")
    if center:
        children = children.filter(center=center)

    result = []
    today = timezone.localdate()
    for ch in children:
        att = _student_attendance_summary(
            ch, center,
            start_date=today - timezone.timedelta(days=30),
            end_date=today + timezone.timedelta(days=1),
        )
        result.append({
            "id": ch.id,
            "full_name": ch.get_full_name(),
            "balance": _student_balance(ch, center),
            "debt": _student_open_debt(ch, center),
            "att_rate": att.get("recent_attendance_rate", att.get("attendance_rate", 0)),
        })

    return JsonResponse({"children": result})


@login_required
def parent_panel_child_dashboard_api(request, child_pk: int):
    """Parent panel — KPI + next lessons for one child."""
    from datetime import timedelta
    from core.mobile_api import (
        _student_open_debt, _student_attendance_summary, _student_groups, _student_balance,
    )
    from education.models import GroupSchedule

    child, center, err = _pp_resolve_child(request, child_pk)
    if err:
        return err

    balance = _student_balance(child, center)
    debt = _student_open_debt(child, center)
    today = timezone.localdate()

    att = _student_attendance_summary(
        child, center,
        start_date=today - timezone.timedelta(days=30),
        end_date=today + timezone.timedelta(days=1),
    )
    att_rate = att.get("recent_attendance_rate", att.get("attendance_rate", 0))

    groups = _student_groups(child, center)
    active_groups = [g for g in groups if g.get("is_active")]
    active_ids = [g["id"] for g in active_groups]

    tomorrow = today + timezone.timedelta(days=1)
    today_wd = today.weekday() + 1
    tomorrow_wd = tomorrow.weekday() + 1

    schedules = (
        GroupSchedule.objects
        .filter(group_id__in=active_ids, weekday__in=[today_wd, tomorrow_wd])
        .select_related("group", "group__oqituvchi")
        .order_by("weekday", "start_time")
    )
    next_lessons = []
    for sch in schedules:
        teacher = sch.group.oqituvchi
        next_lessons.append({
            "group_name": sch.group.nom,
            "day": "Bugun" if sch.weekday == today_wd else "Ertaga",
            "start_time": sch.start_time.strftime("%H:%M"),
            "end_time": sch.end_time.strftime("%H:%M") if sch.end_time else "",
            "room": sch.room or "",
            "teacher": teacher.get_full_name() if teacher else "",
        })

    return JsonResponse({
        "child_id": child.id,
        "full_name": child.get_full_name(),
        "balance": int(balance or 0),
        "debt": int(debt),
        "att_rate": att_rate,
        "att_present": att.get("recent_present_lessons", 0),
        "att_total": att.get("recent_total_lessons", 0),
        "groups_total": len(groups),
        "groups_active": len(active_groups),
        "payment_status": "debt" if debt > 0 else "paid",
        "next_lessons": next_lessons,
    })


@login_required
def parent_panel_child_groups_api(request, child_pk: int):
    """Parent panel — groups list for one child."""
    from core.mobile_api import _student_groups
    from education.models import GroupSchedule

    child, center, err = _pp_resolve_child(request, child_pk)
    if err:
        return err

    groups = _student_groups(child, center)
    group_ids = [g["id"] for g in groups]
    sched_map: dict[int, list] = {}
    for sch in GroupSchedule.objects.filter(group_id__in=group_ids).order_by("weekday", "start_time"):
        sched_map.setdefault(sch.group_id, []).append({
            "weekday": sch.weekday,
            "weekday_name": sch.weekday_uz,
            "start_time": sch.start_time.strftime("%H:%M"),
            "end_time": sch.end_time.strftime("%H:%M") if sch.end_time else "",
            "room": sch.room or "",
        })
    for g in groups:
        g["schedules"] = sched_map.get(g["id"], [])

    return JsonResponse({"groups": groups})


@login_required
def parent_panel_child_attendance_api(request, child_pk: int):
    """Parent panel — monthly attendance calendar for one child."""
    from datetime import date, timedelta
    from collections import defaultdict
    from core.mobile_api import _student_monthly_attendance_summary, _add_months
    from education.models import Attendance
    from django.db.models import Q

    child, center, err = _pp_resolve_child(request, child_pk)
    if err:
        return err

    month_str = request.GET.get("month", "")
    if month_str:
        try:
            month_start = date.fromisoformat(month_str + "-01")
        except ValueError:
            return JsonResponse({"error": "Invalid month format. Use YYYY-MM."}, status=400)
    else:
        month_start = timezone.localdate().replace(day=1)

    month_end = _add_months(month_start, 1)
    summary = _student_monthly_attendance_summary(child, center, month_start)

    att_qs = (
        Attendance.objects
        .filter(student=child, group__center=center, date__gte=month_start, date__lt=month_end)
        .values("date", "status", "present", "forced")
    )

    day_map: dict[str, list] = defaultdict(list)
    for att in att_qs:
        is_present = att.get("forced") or att.get("present") or att.get("status") == "present"
        day_map[att["date"].isoformat()].append("present" if is_present else att.get("status", "absent"))

    calendar_days = []
    cur = month_start
    while cur < month_end:
        iso = cur.isoformat()
        entries = day_map.get(iso, [])
        if entries:
            all_p = all(e == "present" for e in entries)
            any_p = any(e == "present" for e in entries)
            status = "present" if all_p else ("partial" if any_p else "absent")
        else:
            status = "no_class"
        calendar_days.append({"date": iso, "day": cur.day, "weekday": cur.weekday(), "status": status})
        cur += timedelta(days=1)

    return JsonResponse({
        "month": month_start.strftime("%Y-%m"),
        "summary": summary,
        "calendar": calendar_days,
    })


@login_required
def parent_panel_child_payments_api(request, child_pk: int):
    """Parent panel — payment history for one child."""
    from core.mobile_api import _student_open_debt
    from education.models import Payment

    child, center, err = _pp_resolve_child(request, child_pk)
    if err:
        return err

    debt = _student_open_debt(child, center)
    payments = (
        Payment.objects
        .filter(student=child, center=center, is_deleted=False)
        .select_related("group")
        .order_by("-paid_date", "-id")[:30]
    )
    payments_list = [
        {
            "id": p.id,
            "group_name": p.group.nom if p.group else "",
            "amount": p.summa,
            "payment_type": p.payment_type,
            "paid_date": p.paid_date.isoformat(),
            "note": p.note or "",
        }
        for p in payments
    ]
    return JsonResponse({
        "current_debt": int(debt),
        "payment_status": "debt" if debt > 0 else "paid",
        "payments": payments_list,
    })


# ─────────────────────── Student Games API ───────────────────────────────────

_GAME_CONFIGS = {
    # Matematik
    "math_sprint":      {"name": "Math Sprint",        "emoji": "🧮", "max_coins": 15, "min_score": 5,  "coins_per_correct": True},
    "times_table":      {"name": "Ko'paytirish",        "emoji": "📊", "max_coins": 12, "min_score": 5,  "coins_per_correct": True},
    "number_sequence":  {"name": "Ketma-ketlik",        "emoji": "🧩", "max_coins": 12, "min_score": 4,  "coins_per_correct": True},
    # Til
    "english_words":    {"name": "Inglizcha So'zlar",  "emoji": "🔡", "max_coins": 12, "min_score": 4,  "coins_per_correct": True},
    "word_scramble":    {"name": "So'z Tartibi",       "emoji": "🔤", "max_coins": 10, "min_score": 4,  "coins_per_correct": True},
    # Geografiya
    "geography_quiz":   {"name": "Geografiya",          "emoji": "🌍", "max_coins": 15, "min_score": 4,  "coins_per_correct": True},
    # Fan
    "science_quiz":     {"name": "Fan Savollari",       "emoji": "🔬", "max_coins": 15, "min_score": 4,  "coins_per_correct": True},
    "shapes_quiz":      {"name": "Geometriya",          "emoji": "📐", "max_coins": 10, "min_score": 4,  "coins_per_correct": True},
    # Umumiy bilim
    "quick_quiz":       {"name": "Tez Bilim",           "emoji": "⚡", "max_coins": 15, "min_score": 4,  "coins_per_correct": True},
    # Xotira
    "memory_match":     {"name": "Memory Match",        "emoji": "🧠", "max_coins": 10, "min_score": 1,  "coins_per_correct": False},
    # Mantiq o'yinlari
    "chess":            {"name": "Shaxmat",             "emoji": "♟",  "max_coins": 20, "min_score": 1,  "coins_per_correct": False},
    "checkers":         {"name": "Shashka",             "emoji": "🔴", "max_coins": 15, "min_score": 1,  "coins_per_correct": False},
    # Bilim testlari
    "true_false":       {"name": "Rost yoki Yolg'on?",  "emoji": "✅", "max_coins": 12, "min_score": 6,  "coins_per_correct": False},
    "formula_fill":     {"name": "Formula To'ldirish",  "emoji": "🔢", "max_coins": 15, "min_score": 5,  "coins_per_correct": True},
    "crossword":        {"name": "Krossvord",            "emoji": "📝", "max_coins": 15, "min_score": 3,  "coins_per_correct": True},
}


def _get_game_center_cfg(center):
    """Return {slug: CenterGameConfig} for a center (cached per request cycle)."""
    from core.models import CenterGameConfig
    return {cc.game_slug: cc for cc in CenterGameConfig.objects.filter(center=center)}


def _get_global_game_cfg():
    """Return set of globally-disabled game slugs."""
    from core.models import GlobalGameConfig
    return set(GlobalGameConfig.objects.filter(is_enabled=False).values_list("game_slug", flat=True))


def _resolve_game_cfg(slug, default_cfg, center_cfg_map, global_disabled):
    """Return effective (max_coins, min_score, is_enabled) for a game."""
    if slug in global_disabled:
        return None  # globally disabled
    cc = center_cfg_map.get(slug)
    if cc and not cc.is_enabled:
        return None  # center disabled
    max_coins = (cc.max_coins if cc and cc.max_coins > 0 else default_cfg["max_coins"])
    min_score = (cc.min_score if cc and cc.min_score > 0 else default_cfg["min_score"])
    return {"max_coins": max_coins, "min_score": min_score}


@login_required
@require_GET
def student_game_status_api(request):
    """Return list of active games with today's earned status + student level."""
    err = _sp_student_only(request)
    if err:
        return err

    from core.models import GameSession, StudentGameProgress
    user = request.user
    center = _sp_center(request)
    today = timezone.localdate()

    global_disabled = _get_global_game_cfg()
    center_cfg_map = _get_game_center_cfg(center)

    earned_today = set(
        GameSession.objects.filter(
            student=user, center=center,
            coins_earned__gt=0,
            played_at__date=today,
        ).values_list("game_slug", flat=True)
    )

    progress_map = {
        p.game_slug: p.current_level
        for p in StudentGameProgress.objects.filter(center=center, student=user)
    }

    recent = (
        GameSession.objects.filter(student=user, center=center)
        .order_by("-played_at")[:10]
        .values("game_slug", "score", "coins_earned", "played_at")
    )
    recent_list = [
        {
            "game_slug": s["game_slug"],
            "game_name": _GAME_CONFIGS.get(s["game_slug"], {}).get("name", s["game_slug"]),
            "score": s["score"],
            "coins_earned": s["coins_earned"],
            "played_at": s["played_at"].isoformat(),
        }
        for s in recent
    ]

    games = []
    for slug, cfg in _GAME_CONFIGS.items():
        eff = _resolve_game_cfg(slug, cfg, center_cfg_map, global_disabled)
        if eff is None:
            continue
        games.append({
            "slug": slug,
            "name": cfg["name"],
            "emoji": cfg["emoji"],
            "max_coins": eff["max_coins"],
            "earned_today": slug in earned_today,
            "current_level": progress_map.get(slug, 1),
        })

    return JsonResponse({"games": games, "recent": recent_list})


@login_required
@require_POST
def student_game_result_api(request):
    """Submit game result; award 1 ball if eligible (max once per day per game)."""
    err = _sp_student_only(request)
    if err:
        return err

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    game_slug = str(data.get("game_slug", ""))
    score = max(0, int(data.get("score", 0)))
    duration_sec = max(0, int(data.get("duration_sec", 0)))
    level = max(1, int(data.get("level", 1)))

    config = _GAME_CONFIGS.get(game_slug)
    if not config:
        return JsonResponse({"error": "Unknown game"}, status=400)

    from core.models import GameSession, StudentBallsWallet, StudentGameProgress

    user = request.user
    center = _sp_center(request)
    today = timezone.localdate()

    global_disabled = _get_global_game_cfg()
    center_cfg_map = _get_game_center_cfg(center)
    eff = _resolve_game_cfg(game_slug, config, center_cfg_map, global_disabled)
    if eff is None:
        return JsonResponse({"error": "Game disabled"}, status=403)

    effective_min_score = eff["min_score"]
    total_games = len(_GAME_CONFIGS)

    already_ball = GameSession.objects.filter(
        student=user,
        game_slug=game_slug,
        balls_earned=1,
        played_at__date=today,
    ).exists()

    daily_unique_games = GameSession.objects.filter(
        student=user,
        balls_earned=1,
        played_at__date=today,
    ).values("game_slug").distinct().count()

    ball = 0
    if not already_ball and score >= effective_min_score and daily_unique_games < total_games:
        ball = 1
        wallet, _ = StudentBallsWallet.objects.get_or_create(
            center=center, student=user,
            defaults={"total_balls": 0, "lifetime_balls": 0},
        )
        wallet.total_balls += 1
        wallet.lifetime_balls += 1
        wallet.last_ball_at = timezone.now()
        wallet.save(update_fields=["total_balls", "lifetime_balls", "last_ball_at"])

    GameSession.objects.create(
        center=center,
        student=user,
        game_slug=game_slug,
        score=score,
        level=level,
        duration_sec=duration_sec,
        coins_earned=0,
        balls_earned=ball,
    )

    progress, _ = StudentGameProgress.objects.get_or_create(
        center=center, student=user, game_slug=game_slug,
        defaults={"current_level": 1, "best_score": 0, "total_sessions": 0},
    )
    progress.total_sessions += 1
    if score > progress.best_score:
        progress.best_score = score
    level_up = False
    if score >= effective_min_score and not already_ball:
        if progress.current_level < 9:
            progress.current_level += 1
            level_up = True
    progress.save(update_fields=["current_level", "best_score", "total_sessions", "updated_at"])

    try:
        wallet_obj = StudentBallsWallet.objects.get(center=center, student=user)
        total_balls = wallet_obj.total_balls
    except StudentBallsWallet.DoesNotExist:
        total_balls = 0

    return JsonResponse({
        "ok": True,
        "balls_earned": ball,
        "already_earned_today": already_ball,
        "daily_balls": daily_unique_games + (1 if ball else 0),
        "total_balls": total_balls,
        "total_games": total_games,
        "new_level": progress.current_level,
        "level_up": level_up,
    })


@login_required
@require_POST
def game_convert_balls_api(request):
    """Convert accumulated balls to chaqmoq (once per eligibility)."""
    err = _sp_student_only(request)
    if err:
        return err

    from core.models import StudentBallsWallet, GameBallsConfig, GameBallsConversionLog
    from chaqmoq.models import Ledger

    user = request.user
    center = _sp_center(request)

    config, _ = GameBallsConfig.objects.get_or_create(
        center=center,
        defaults={"min_balls_to_convert": 100, "chaqmoq_per_conversion": 5},
    )

    wallet, _ = StudentBallsWallet.objects.get_or_create(
        center=center, student=user,
        defaults={"total_balls": 0, "lifetime_balls": 0},
    )

    if wallet.total_balls < config.min_balls_to_convert:
        return JsonResponse({
            "ok": False,
            "error": f"Yetarli ball yo'q. Kerak: {config.min_balls_to_convert}, Sizda: {wallet.total_balls}",
            "total_balls": wallet.total_balls,
            "min_balls": config.min_balls_to_convert,
        }, status=400)

    wallet.total_balls -= config.min_balls_to_convert
    wallet.save(update_fields=["total_balls"])

    Ledger.objects.create(
        student=user,
        beruvchi=None,
        rule=None,
        rule_nom=f"🎮 O'yin bali: {config.min_balls_to_convert} ball → {config.chaqmoq_per_conversion} ⚡",
        ball=config.chaqmoq_per_conversion,
        sana=timezone.now(),
    )

    GameBallsConversionLog.objects.create(
        center=center, student=user,
        balls_spent=config.min_balls_to_convert,
        chaqmoq_earned=config.chaqmoq_per_conversion,
    )

    from chaqmoq.views import _get_balances_with_legacy_fallback
    new_balance = _get_balances_with_legacy_fallback([user.id], center=center).get(user.id, 0)

    return JsonResponse({
        "ok": True,
        "balls_spent": config.min_balls_to_convert,
        "chaqmoq_earned": config.chaqmoq_per_conversion,
        "remaining_balls": wallet.total_balls,
        "new_chaqmoq_balance": int(new_balance or 0),
    })


@login_required
@require_POST
def game_balls_config_api(request):
    """Save GameBallsConfig for a center (director/manager only)."""
    u = request.user
    if u.role not in ("director", "manager") and not u.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    min_balls = max(1, int(data.get("min_balls_to_convert", 100)))
    chaqmoq = max(1, int(data.get("chaqmoq_per_conversion", 5)))

    from core.models import GameBallsConfig
    center = _sp_center(request)
    if not center:
        return JsonResponse({"error": "No center"}, status=400)

    cfg, _ = GameBallsConfig.objects.get_or_create(
        center=center,
        defaults={"min_balls_to_convert": min_balls, "chaqmoq_per_conversion": chaqmoq},
    )
    cfg.min_balls_to_convert = min_balls
    cfg.chaqmoq_per_conversion = chaqmoq
    cfg.save(update_fields=["min_balls_to_convert", "chaqmoq_per_conversion", "updated_at"])

    return JsonResponse({"ok": True, "min_balls_to_convert": min_balls, "chaqmoq_per_conversion": chaqmoq})


# ══════════════════════════════════════════════════════════════════
#  GAME MANAGEMENT APIs
# ══════════════════════════════════════════════════════════════════

@login_required
def game_config_api(request):
    """GET: list all games + center config. POST: save center game config."""
    from core.models import GlobalGameConfig, CenterGameConfig, GameSuggestion

    u = request.user
    if u.role not in ("director", "manager") and not u.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)

    center = _sp_center(request)

    if request.method == "GET":
        global_disabled = _get_global_game_cfg()
        center_cfgs = {cc.game_slug: cc for cc in CenterGameConfig.objects.filter(center=center)}
        result = []
        for slug, cfg in _GAME_CONFIGS.items():
            cc = center_cfgs.get(slug)
            result.append({
                "slug": slug,
                "name": cfg["name"],
                "emoji": cfg["emoji"],
                "max_coins_default": cfg["max_coins"],
                "min_score_default": cfg["min_score"],
                "is_globally_enabled": slug not in global_disabled,
                "is_center_enabled": cc.is_enabled if cc else True,
                "center_max_coins": cc.max_coins if cc else 0,
                "center_min_score": cc.min_score if cc else 0,
            })
        suggestions = list(
            GameSuggestion.objects.filter(center=center)
            .select_related("student")
            .values(
                "id", "game_name", "description", "is_reviewed",
                "created_at", "student__first_name", "student__last_name",
            )[:50]
        )
        return JsonResponse({"games": result, "suggestions": suggestions})

    # POST — save single game config
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    slug = str(data.get("slug", ""))
    if slug not in _GAME_CONFIGS:
        return JsonResponse({"error": "Unknown game"}, status=400)

    cc, _ = CenterGameConfig.objects.get_or_create(center=center, game_slug=slug)
    if "is_enabled" in data:
        cc.is_enabled = bool(data["is_enabled"])
    if "max_coins" in data:
        cc.max_coins = max(0, int(data["max_coins"]))
    if "min_score" in data:
        cc.min_score = max(0, int(data["min_score"]))
    cc.updated_by = u
    cc.save()
    return JsonResponse({"ok": True})


@login_required
def global_game_config_api(request):
    """GET: list global game states. POST: toggle global enabled. Super admin only."""
    from core.models import GlobalGameConfig

    if not request.user.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)

    if request.method == "GET":
        existing = {g.game_slug: g.is_enabled for g in GlobalGameConfig.objects.all()}
        result = [
            {
                "slug": slug,
                "name": cfg["name"],
                "emoji": cfg["emoji"],
                "is_enabled": existing.get(slug, True),
            }
            for slug, cfg in _GAME_CONFIGS.items()
        ]
        return JsonResponse({"games": result})

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    slug = str(data.get("slug", ""))
    if slug not in _GAME_CONFIGS:
        return JsonResponse({"error": "Unknown game"}, status=400)

    gc, _ = GlobalGameConfig.objects.get_or_create(game_slug=slug)
    gc.is_enabled = bool(data.get("is_enabled", True))
    gc.save()
    return JsonResponse({"ok": True, "is_enabled": gc.is_enabled})


@login_required
@require_POST
def game_suggestion_api(request):
    """Student: submit a game suggestion."""
    from core.models import GameSuggestion

    err = _sp_student_only(request)
    if err:
        return err

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    game_name = str(data.get("game_name", "")).strip()[:100]
    description = str(data.get("description", "")).strip()[:500]
    if not game_name:
        return JsonResponse({"error": "game_name required"}, status=400)

    center = _sp_center(request)
    GameSuggestion.objects.create(
        center=center, student=request.user,
        game_name=game_name, description=description,
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def game_suggestion_review_api(request, pk):
    """Director/Manager: mark a suggestion as reviewed."""
    from core.models import GameSuggestion

    u = request.user
    if u.role not in ("director", "manager") and not u.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)

    center = _sp_center(request)
    try:
        s = GameSuggestion.objects.get(pk=pk, center=center)
    except GameSuggestion.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    s.is_reviewed = True
    s.save(update_fields=["is_reviewed"])
    return JsonResponse({"ok": True})


# ── Default question banks (fallback when no DB questions exist) ────────────
_DEFAULT_QUESTIONS = {
    "geography_quiz": [
        {"q": "Frantsiyaning poytaxti?", "opts": ["Paris", "Rim", "Madrid", "Berlin"], "a": 0},
        {"q": "Yaponiyaning poytaxti?", "opts": ["Pekin", "Tokio", "Seul", "Bangkok"], "a": 1},
        {"q": "Braziliyaning poytaxti?", "opts": ["Rio de Janeyro", "San-Paulo", "Braziliya", "Buenos-Ayres"], "a": 2},
        {"q": "Avstraliyaning poytaxti?", "opts": ["Sidney", "Melburn", "Kanberra", "Brisben"], "a": 2},
        {"q": "Kanada poytaxti?", "opts": ["Toronto", "Monreal", "Vankuver", "Ottawa"], "a": 3},
        {"q": "Rossiyaning poytaxti?", "opts": ["Moskva", "Sankt-Peterburg", "Novosibirsk", "Yekaterinburg"], "a": 0},
        {"q": "Xitoyning poytaxti?", "opts": ["Shanxay", "Pekin", "Gonkong", "Chengdu"], "a": 1},
        {"q": "Hindistonning poytaxti?", "opts": ["Mumbay", "Nyu-Delhi", "Kalkutta", "Bangalore"], "a": 1},
        {"q": "Misrning poytaxti?", "opts": ["Aleksandriya", "Qohira", "Luxor", "Giza"], "a": 1},
        {"q": "O'zbekistonning poytaxti?", "opts": ["Samarqand", "Buxoro", "Toshkent", "Namangan"], "a": 2},
        {"q": "Germaniyaning poytaxti?", "opts": ["Myunxen", "Gamburg", "Frankfurt", "Berlin"], "a": 3},
        {"q": "Italiyaning poytaxti?", "opts": ["Milan", "Venetsiya", "Rim", "Florentsiya"], "a": 2},
        {"q": "Ispaniyaning poytaxti?", "opts": ["Barselona", "Valensiya", "Madrid", "Sevil"], "a": 2},
        {"q": "Qozog'istonning poytaxti?", "opts": ["Olma-Ota", "Astana", "Shimkent", "Qaraganda"], "a": 1},
        {"q": "Turkiyaning poytaxti?", "opts": ["Istanbul", "Izmir", "Anqara", "Bursa"], "a": 2},
    ],
    "english_words": [
        {"q": "\"Kitob\" inglizcha?", "opts": ["Notebook", "Book", "Pen", "Paper"], "a": 1},
        {"q": "\"Daraxt\" inglizcha?", "opts": ["Flower", "Grass", "Tree", "Leaf"], "a": 2},
        {"q": "\"Maktab\" inglizcha?", "opts": ["Library", "Office", "School", "College"], "a": 2},
        {"q": "\"Suv\" inglizcha?", "opts": ["Milk", "Water", "Juice", "Tea"], "a": 1},
        {"q": "\"Uy\" inglizcha?", "opts": ["Room", "Garden", "House", "Street"], "a": 2},
        {"q": "\"O'qituvchi\" inglizcha?", "opts": ["Student", "Teacher", "Doctor", "Driver"], "a": 1},
        {"q": "\"Quyosh\" inglizcha?", "opts": ["Moon", "Star", "Cloud", "Sun"], "a": 3},
        {"q": "\"Ot\" (hayvon) inglizcha?", "opts": ["Dog", "Cat", "Horse", "Cow"], "a": 2},
        {"q": "\"Rang\" inglizcha?", "opts": ["Sound", "Shape", "Color", "Size"], "a": 2},
        {"q": "\"Yil\" inglizcha?", "opts": ["Week", "Month", "Day", "Year"], "a": 3},
        {"q": "\"Do'st\" inglizcha?", "opts": ["Enemy", "Friend", "Brother", "Sister"], "a": 1},
        {"q": "\"Non\" inglizcha?", "opts": ["Rice", "Bread", "Cake", "Soup"], "a": 1},
        {"q": "\"Havo\" inglizcha?", "opts": ["Water", "Fire", "Air", "Earth"], "a": 2},
        {"q": "\"Bola\" inglizcha?", "opts": ["Man", "Woman", "Child", "Baby"], "a": 2},
        {"q": "\"Kechqurun\" inglizcha?", "opts": ["Morning", "Afternoon", "Evening", "Night"], "a": 2},
    ],
    "science_quiz": [
        {"q": "Suvning kimyoviy formulasi?", "opts": ["CO2", "H2O", "O2", "NaCl"], "a": 1},
        {"q": "Quyosh sistemasidagi eng katta sayyora?", "opts": ["Saturn", "Yer", "Mars", "Yupiter"], "a": 3},
        {"q": "Inson tanasida necha suyak bor?", "opts": ["106", "206", "306", "406"], "a": 1},
        {"q": "Fotosintez uchun qaysi gaz kerak?", "opts": ["Kislorod", "Vodorod", "CO2", "Azot"], "a": 2},
        {"q": "Yorug'lik tezligi taxminan?", "opts": ["100,000 km/s", "200,000 km/s", "300,000 km/s", "400,000 km/s"], "a": 2},
        {"q": "DNA nima?", "opts": ["Protein", "Irsiy ma'lumot molekulasi", "Vitamin", "Ferment"], "a": 1},
        {"q": "Yer o'z o'qi atrofida necha soatda aylanadi?", "opts": ["12", "24", "36", "48"], "a": 1},
        {"q": "Eng yengil kimyoviy element?", "opts": ["Kislorod", "Geliy", "Vodorod", "Uglerod"], "a": 2},
        {"q": "Qon guruhlarining turi nechta?", "opts": ["2", "3", "4", "5"], "a": 2},
        {"q": "Osmon nima uchun ko'k?", "opts": ["Suv bug'i", "Yorug'lik tarqalishi", "Ozon", "Kislorod"], "a": 1},
        {"q": "Magnetning qutblari nechtadan?", "opts": ["1", "2", "3", "4"], "a": 1},
        {"q": "Yerga eng yaqin sayyora?", "opts": ["Mars", "Venus", "Merkuriy", "Saturn"], "a": 1},
        {"q": "Issiqlik qanday o'lchanadi?", "opts": ["Metr", "Kilogramm", "Daraja Celsius", "Sekund"], "a": 2},
        {"q": "Asal qaysi hayvon tomonidan yasaladi?", "opts": ["Kapalak", "Qo'ng'iz", "Ari", "Chivin"], "a": 2},
        {"q": "Inson eshita oladigan tovush chastotasi?", "opts": ["20-200 Hz", "20-20,000 Hz", "200-2,000 Hz", "2-200 kHz"], "a": 1},
    ],
    "quick_quiz": [
        {"q": "O'zbekiston mustaqilligini qachon oldi?", "opts": ["1990", "1991", "1992", "1993"], "a": 1},
        {"q": "Bir yilda necha kun bor?", "opts": ["355", "360", "365", "370"], "a": 2},
        {"q": "Eng katta okean?", "opts": ["Atlantika", "Hind", "Arktika", "Tinch okean"], "a": 3},
        {"q": "Futbol jamoasida nechta futbolchi?", "opts": ["9", "10", "11", "12"], "a": 2},
        {"q": "\"Cho'l kemasi\" deb qaysi hayvon ataladi?", "opts": ["Fil", "Zirafa", "Tuya", "Ot"], "a": 2},
        {"q": "Pi (π) taxminiy qiymati?", "opts": ["2.71", "3.14", "1.41", "1.73"], "a": 1},
        {"q": "Eng uzun daryo?", "opts": ["Amazon", "Nil", "Yangtze", "Mississippi"], "a": 1},
        {"q": "Xona temperaturasida suyuq metal?", "opts": ["Temir", "Mis", "Simob", "Rux"], "a": 2},
        {"q": "1 kilometr necha metr?", "opts": ["10", "100", "1000", "10000"], "a": 2},
        {"q": "Dunyodagi eng baland tog'?", "opts": ["K2", "Elbrus", "Everest", "Kilimanjaro"], "a": 2},
        {"q": "Shaxmat taxtasida nechta katak?", "opts": ["32", "48", "64", "81"], "a": 2},
        {"q": "Bir daqiqada necha sekund?", "opts": ["30", "45", "60", "100"], "a": 2},
        {"q": "Eng katta kontinent?", "opts": ["Afrika", "Amerika", "Yevropa", "Osiyo"], "a": 3},
        {"q": "Inson yuragi 1 daqiqada necha marta uradi?", "opts": ["40", "60-80", "100-120", "140-160"], "a": 1},
        {"q": "Dunyodagi eng katta cho'l?", "opts": ["Sahara", "Gobi", "Arabiston", "Antarktida"], "a": 3},
    ],
    "word_scramble": [
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["MATEMATICS", "MATHEMATICS", "MATHMATICS", "MATHEMATCS"], "a": 1},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["GEOGRAFY", "GEOGRAHY", "GEOGRAPHY", "GIOGRAPHY"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["BIOLOGIY", "BIOLOGI", "BIOLOGY", "BIOLOGHY"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["PHYSIC", "PHYICS", "PHYSYCS", "PHYSICS"], "a": 3},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["LITARATURE", "LITERTURE", "LITERATURE", "LITTERATURE"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["CHEMESTRY", "CHEMISTRY", "CHEMISTERY", "CHIMISTRY"], "a": 1},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["CALENDER", "CALANDAR", "CALENDAR", "CALANDER"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["RECIEVE", "RECEIVE", "RECEVE", "RECEEVE"], "a": 1},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["BELEIVE", "BELEEVE", "BELIEVE", "BILIEVE"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["BEGINING", "BEGINNING", "BEGGINING", "BEGININING"], "a": 1},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["GRAMMER", "GRAMMARR", "GRAMMAR", "GRAMAR"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["KNOWLEGE", "KNOWEDGE", "KNOLEDGE", "KNOWLEDGE"], "a": 3},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["WRITTING", "WRITNG", "WRITING", "WRITEING"], "a": 2},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["EXCELENT", "EXCELLENT", "EXCELLANT", "EXCILENT"], "a": 1},
        {"q": "Qaysi so'z to'g'ri yozilgan?", "opts": ["NECESARY", "NECCESSARY", "NECESSARY", "NECESSERY"], "a": 2},
    ],
    "number_sequence": [
        {"q": "2, 4, 6, 8, __?", "opts": ["9", "10", "11", "12"], "a": 1},
        {"q": "1, 3, 5, 7, __?", "opts": ["8", "9", "10", "11"], "a": 1},
        {"q": "2, 4, 8, 16, __?", "opts": ["24", "28", "32", "64"], "a": 2},
        {"q": "1, 4, 9, 16, __?", "opts": ["20", "24", "25", "30"], "a": 2},
        {"q": "1, 1, 2, 3, 5, __?", "opts": ["6", "7", "8", "9"], "a": 2},
        {"q": "10, 20, 30, 40, __?", "opts": ["45", "48", "50", "55"], "a": 2},
        {"q": "100, 50, 25, __?", "opts": ["10", "12", "12.5", "15"], "a": 2},
        {"q": "3, 6, 9, 12, __?", "opts": ["14", "15", "16", "18"], "a": 1},
        {"q": "1, 2, 4, 7, 11, __?", "opts": ["14", "15", "16", "17"], "a": 2},
        {"q": "5, 10, 20, 40, __?", "opts": ["60", "70", "80", "100"], "a": 2},
        {"q": "1, 8, 27, 64, __?", "opts": ["100", "125", "128", "256"], "a": 1},
        {"q": "2, 3, 5, 7, 11, __?", "opts": ["12", "13", "14", "15"], "a": 1},
        {"q": "0, 1, 3, 6, 10, __?", "opts": ["12", "13", "14", "15"], "a": 3},
        {"q": "256, 128, 64, 32, __?", "opts": ["8", "12", "16", "24"], "a": 2},
        {"q": "3, 9, 27, 81, __?", "opts": ["162", "243", "324", "405"], "a": 1},
    ],
    "shapes_quiz": [
        {"q": "Uchburchak nechta tomonli?", "opts": ["2", "3", "4", "5"], "a": 1},
        {"q": "Kvadratning burchaklari nechta?", "opts": ["2", "3", "4", "6"], "a": 2},
        {"q": "Doira doimiyligi pi taxminan?", "opts": ["2.71", "3.14", "4.00", "1.73"], "a": 1},
        {"q": "Kvadratning perimetri = ?", "opts": ["a^2", "4a", "2a", "a+4"], "a": 1},
        {"q": "To'rtburchakning yuz formulasi?", "opts": ["a+b", "a*b", "2(a+b)", "a^2"], "a": 1},
        {"q": "Doira yuzining formulasi?", "opts": ["pi*r", "pi*r^2", "2*pi*r", "pi*d"], "a": 1},
        {"q": "Kubning nechta qirrasi bor?", "opts": ["6", "8", "10", "12"], "a": 3},
        {"q": "Uchburchakning burchaklari yig'indisi?", "opts": ["90", "180", "270", "360"], "a": 1},
        {"q": "Pifagor teoremasi: a^2 + b^2 = ?", "opts": ["c", "c^2", "2c", "c+1"], "a": 1},
        {"q": "To'g'ri burchakli uchburchakdagi eng uzun tomon?", "opts": ["Katetlar", "Gipotenuza", "Median", "Balandlik"], "a": 1},
    ],
    "true_false": [
        {"q": "Yer quyosh atrofida aylanadi", "a": True},
        {"q": "Suvning formulasi H2O", "a": True},
        {"q": "Afrikaning poytaxti Qohira", "a": False},
        {"q": "Uchburchak burchaklari yig'indisi 180 daraja", "a": True},
        {"q": "Eng katta okean Atlantika", "a": False},
        {"q": "Pi (π) taxminan 3.14 ga teng", "a": True},
        {"q": "Yorug'lik tovushdan sekin harakat qiladi", "a": False},
        {"q": "O'zbekiston 1991-yilda mustaqil bo'ldi", "a": True},
        {"q": "Inson tanasida 106 ta suyak bor", "a": False},
        {"q": "Olmos tabiatdagi eng qattiq modda", "a": True},
        {"q": "Quyosh sistemasida 8 ta sayyora bor", "a": True},
        {"q": "Mis elektr tokini o'tkazmaydi", "a": False},
        {"q": "Vodorod eng yengil kimyoviy element", "a": True},
        {"q": "Braziliyaning poytaxti Rio de Janeyro", "a": False},
        {"q": "1 kilometr = 1000 metr", "a": True},
        {"q": "Shaxmat taxtasida 64 ta katak bor", "a": True},
        {"q": "Quyosh yulduz hisoblanadi", "a": True},
        {"q": "Oy Yerdan kichik", "a": True},
        {"q": "Antarktida dunyodagi eng katta cho'l", "a": True},
        {"q": "Futbol jamoasida 12 ta o'yinchi bo'ladi", "a": False},
    ],
    "formula_fill": [
        {"q": "Doira yuzi: S = π × r × __?", "opts": ["d", "r", "2", "π"], "a": 1, "fill": "r"},
        {"q": "Uchburchak yuzi: S = (a × h) ÷ __?", "opts": ["3", "2", "4", "π"], "a": 1, "fill": "2"},
        {"q": "Kvadrat perimetri: P = 4 × __?", "opts": ["r", "d", "a", "h"], "a": 2, "fill": "a"},
        {"q": "To'g'ri to'rtburchak yuzi: S = a × __?", "opts": ["a", "b", "h", "r"], "a": 1, "fill": "b"},
        {"q": "Tezlik formulasi: v = s ÷ __?", "opts": ["m", "t", "a", "F"], "a": 1, "fill": "t"},
        {"q": "Pifagor teoremasi: c² = a² + __?", "opts": ["b", "b²", "2b", "c"], "a": 1, "fill": "b²"},
        {"q": "Kuch formulasi: F = m × __?", "opts": ["v", "t", "a", "s"], "a": 2, "fill": "a"},
        {"q": "Tezlanish: a = (v - v₀) ÷ __?", "opts": ["s", "m", "t", "F"], "a": 2, "fill": "t"},
        {"q": "Elektr quvvati: P = U × __?", "opts": ["R", "I", "t", "Q"], "a": 1, "fill": "I"},
        {"q": "Ish formulasi: A = F × __?", "opts": ["t", "m", "s", "a"], "a": 2, "fill": "s"},
    ],
    "math_sprint": [
        {"q": "12 + 15 = ?", "opts": ["25", "27", "28", "26"], "a": 1},
        {"q": "9 × 7 = ?", "opts": ["54", "56", "63", "72"], "a": 2},
        {"q": "100 - 37 = ?", "opts": ["63", "73", "57", "67"], "a": 0},
        {"q": "48 ÷ 6 = ?", "opts": ["6", "7", "8", "9"], "a": 2},
        {"q": "13 × 4 = ?", "opts": ["48", "52", "56", "44"], "a": 1},
        {"q": "125 + 75 = ?", "opts": ["200", "190", "210", "195"], "a": 0},
        {"q": "144 ÷ 12 = ?", "opts": ["10", "11", "12", "13"], "a": 2},
        {"q": "8² = ?", "opts": ["56", "64", "72", "80"], "a": 1},
        {"q": "√81 = ?", "opts": ["7", "8", "9", "10"], "a": 2},
        {"q": "15 × 15 = ?", "opts": ["215", "225", "235", "245"], "a": 1},
        {"q": "1000 - 256 = ?", "opts": ["754", "744", "764", "734"], "a": 1},
        {"q": "36 ÷ 4 = ?", "opts": ["8", "9", "10", "7"], "a": 1},
        {"q": "7 × 8 = ?", "opts": ["48", "54", "56", "64"], "a": 2},
        {"q": "250 + 375 = ?", "opts": ["615", "625", "635", "645"], "a": 1},
        {"q": "3³ = ?", "opts": ["9", "18", "27", "36"], "a": 2},
    ],
    "times_table": [
        {"q": "3 × 3 = ?", "opts": ["6", "9", "12", "15"], "a": 1},
        {"q": "4 × 5 = ?", "opts": ["16", "18", "20", "24"], "a": 2},
        {"q": "6 × 7 = ?", "opts": ["36", "40", "42", "48"], "a": 2},
        {"q": "8 × 9 = ?", "opts": ["63", "72", "76", "81"], "a": 1},
        {"q": "7 × 7 = ?", "opts": ["42", "45", "47", "49"], "a": 3},
        {"q": "9 × 9 = ?", "opts": ["72", "81", "90", "99"], "a": 1},
        {"q": "6 × 8 = ?", "opts": ["42", "44", "48", "54"], "a": 2},
        {"q": "5 × 9 = ?", "opts": ["40", "42", "45", "50"], "a": 2},
        {"q": "4 × 8 = ?", "opts": ["28", "30", "32", "36"], "a": 2},
        {"q": "7 × 8 = ?", "opts": ["48", "54", "56", "64"], "a": 2},
        {"q": "3 × 9 = ?", "opts": ["21", "24", "27", "30"], "a": 2},
        {"q": "6 × 6 = ?", "opts": ["30", "32", "36", "40"], "a": 2},
        {"q": "5 × 7 = ?", "opts": ["30", "33", "35", "40"], "a": 2},
        {"q": "8 × 8 = ?", "opts": ["56", "60", "64", "72"], "a": 2},
        {"q": "9 × 6 = ?", "opts": ["48", "52", "54", "60"], "a": 2},
    ],
}


_AI_AUTO_GEN_THRESHOLD = 20   # if pool < this, trigger background AI generation
_QUESTIONS_PER_SESSION = 10   # how many questions to return per game session


def _get_questions_for_game(game_slug, center, level=None):
    """Return shuffled question list for a game. DB first, fallback to defaults."""
    from core.models import GameQuestion
    qs = GameQuestion.objects.filter(
        game_slug=game_slug,
        is_active=True,
    ).filter(
        Q(center=center) | Q(center__isnull=True)
    )
    if level:
        qs = qs.filter(level=level)
    questions = list(qs.values("id", "level", "question_data", "is_ai_generated"))
    if not questions:
        defaults = _DEFAULT_QUESTIONS.get(game_slug, [])
        questions = [{"id": None, "level": 1, "question_data": q, "is_ai_generated": False} for q in defaults]
    random.shuffle(questions)
    return questions


def _trigger_ai_question_generation(game_slug, center, user):
    """Fire-and-forget: generate AI questions for a game if pool is thin."""
    from core.models import GameQuestion
    existing = GameQuestion.objects.filter(
        game_slug=game_slug, center=center, is_active=True
    ).count()
    if existing >= _AI_AUTO_GEN_THRESHOLD:
        return
    try:
        import threading
        def _gen():
            _auto_generate_questions(game_slug, center, user)
        t = threading.Thread(target=_gen, daemon=True)
        t.start()
    except Exception as e:
        logger.warning("auto-gen questions failed to start: %s", e)


def _auto_generate_questions(game_slug, center, user):
    """Generate 30 questions via Gemini and save to DB for a game."""
    from core.models import GameQuestion
    try:
        prompt = _build_question_prompt(game_slug, count=30)
        if not prompt:
            return
        from core.services.ai_insights import _prompt_json
        result = _prompt_json(prompt)
        if not isinstance(result, list):
            return
        objs = []
        for item in result[:30]:
            if not isinstance(item, dict):
                continue
            objs.append(GameQuestion(
                center=center,
                game_slug=game_slug,
                level=item.get("level", 1),
                question_data=item,
                is_ai_generated=True,
                is_active=True,
                created_by=user,
            ))
        if objs:
            GameQuestion.objects.bulk_create(objs, ignore_conflicts=True)
            logger.info("auto-generated %d questions for %s center=%s", len(objs), game_slug, center.pk if center else None)
    except Exception as e:
        logger.warning("auto-generate questions error: %s", e)


def _build_question_prompt(game_slug, count=30):
    """Build Gemini prompt for auto-generating questions."""
    prompts = {
        "math_sprint": f"""Generate {count} arithmetic questions for Uzbek school students (grades 3-8).
Return JSON array. Each item: {{"q": "12 × 8 = ?", "opts": ["86","94","96","98"], "a": 2, "level": 1}}
Levels 1-9 (1=easy, 9=hard). Mix addition, subtraction, multiplication, division.
Vary difficulty across levels. Return ONLY the JSON array.""",

        "times_table": f"""Generate {count} multiplication table questions (2×-12×) for Uzbek students.
JSON array. Each: {{"q": "7 × 9 = ?", "opts": ["54","62","63","72"], "a": 2, "level": 1}}
Levels 1-9. Level 1=easy tables (2,3,4), level 9=hard (11,12). Return ONLY JSON array.""",

        "number_sequence": f"""Generate {count} number sequence completion questions.
JSON array. Each: {{"q": "2, 4, 8, 16, ?", "opts": ["24","28","32","36"], "a": 2, "level": 1}}
Include arithmetic, geometric, Fibonacci-like sequences. Levels 1-9. Return ONLY JSON array.""",

        "formula_fill": f"""Generate {count} fill-in-the-blank math/science formula questions for students.
JSON array. Each: {{"q": "S = v × ___", "opts": ["a","t","m","F"], "a": 1, "level": 1}}
Mix physics, math, chemistry formulas. Levels 1-9. Return ONLY JSON array.""",

        "geography_quiz": f"""Generate {count} geography questions about world capitals, countries, oceans.
JSON array. Each: {{"q": "Germaniyaning poytaxti?", "opts": ["Berlin","Parij","Vena","Bryussel"], "a": 0, "level": 1}}
Questions in Uzbek language. Levels 1-9. Return ONLY JSON array.""",

        "english_words": f"""Generate {count} English vocabulary questions (Uzbek translation).
JSON array. Each: {{"q": "'Apple' so'zining tarjimasi?", "opts": ["Olma","Nok","Uzum","Shaftoli"], "a": 0, "level": 1}}
Cover A1-B2 vocabulary. Levels 1-9. Return ONLY JSON array.""",

        "science_quiz": f"""Generate {count} science questions (physics, chemistry, biology) for Uzbek students.
JSON array. Each: {{"q": "Suvning qaynash harorati necha daraja?", "opts": ["80°C","90°C","100°C","110°C"], "a": 2, "level": 1}}
Questions in Uzbek. Levels 1-9. Return ONLY JSON array.""",

        "quick_quiz": f"""Generate {count} general knowledge trivia questions for Uzbek school students.
JSON array. Each: {{"q": "O'zbekistonning poytaxti?", "opts": ["Samarqand","Toshkent","Buxoro","Namangan"], "a": 1, "level": 1}}
Questions in Uzbek. Mix history, geography, science, culture. Levels 1-9. Return ONLY JSON array.""",

        "word_scramble": f"""Generate {count} word unscramble questions in Uzbek.
JSON array. Each: {{"q": "AMLOM — bu so'zni to'g'irla", "opts": ["MOLAM","MOLMA","MALMO","MALMO"], "a": 0, "level": 1}}
Use common Uzbek nouns. Levels 1-9 by word length. Return ONLY JSON array.""",

        "shapes_quiz": f"""Generate {count} geometry/shapes questions for Uzbek students.
JSON array. Each: {{"q": "To'rtburchakning perimetri qanday hisoblanadi?", "opts": ["2(a+b)","a×b","a²","4a"], "a": 0, "level": 1}}
Questions in Uzbek. Levels 1-9. Return ONLY JSON array.""",

        "true_false": f"""Generate {count} true/false science/general knowledge statements for Uzbek students.
JSON array. Each: {{"q": "Yer quyosh atrofida aylanadi", "a": true, "level": 1}}
Use 'a': true or false. Statements in Uzbek. Levels 1-9. Return ONLY JSON array.""",

        "chess": f"""Generate {count} chess tactics questions (basic rules, piece moves).
JSON array. Each: {{"q": "Ferz necha yo'nalishda yura oladi?", "opts": ["4","6","8","2"], "a": 2, "level": 1}}
Questions in Uzbek. Levels 1-9. Return ONLY JSON array.""",

        "checkers": f"""Generate {count} checkers/draughts rule questions.
JSON array. Each: {{"q": "Shashkada donalar necha dona?", "opts": ["10","12","16","8"], "a": 1, "level": 1}}
Questions in Uzbek. Levels 1-9. Return ONLY JSON array.""",

        "memory_match": f"""Generate {count} memory/matching pairs for a card flip game.
JSON array. Each: {{"word": "Apple", "match": "Olma", "level": 1}}
Use English-Uzbek word pairs. Levels 1-9 by difficulty. Return ONLY JSON array.""",

        "crossword": f"""Generate {count} crossword-style word definition clues for Uzbek students.
JSON array. Each: {{"q": "Issiqlik o'lchov birligi", "opts": ["Kelvin","Metr","Kilogram","Sekund"], "a": 0, "level": 1}}
Questions in Uzbek. Levels 1-9. Return ONLY JSON array.""",
    }
    return prompts.get(game_slug)


@login_required
@require_GET
def game_student_questions_api(request, game_slug):
    """Return randomly shuffled questions for a game session."""
    center = _sp_center(request)
    if not center:
        return JsonResponse({"error": "no center"}, status=400)
    if game_slug not in _GAME_CONFIGS:
        return JsonResponse({"error": "unknown game"}, status=404)

    from core.models import StudentGameProgress
    try:
        progress = StudentGameProgress.objects.get(center=center, student=request.user, game_slug=game_slug)
        level = progress.current_level
    except StudentGameProgress.DoesNotExist:
        level = 1

    questions = _get_questions_for_game(game_slug, center)

    # Auto-generate if pool is thin (async, non-blocking)
    if len(questions) < _AI_AUTO_GEN_THRESHOLD:
        _trigger_ai_question_generation(game_slug, center, request.user)

    # Return random subset for this session
    session_qs = random.sample(questions, min(_QUESTIONS_PER_SESSION, len(questions)))

    return JsonResponse({"ok": True, "questions": session_qs, "current_level": level})


@login_required
def game_questions_manage_api(request, game_slug):
    """GET: list questions. POST: add question. DELETE: remove question (director/manager)."""
    u = request.user
    if u.role not in ("director", "manager") and not u.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)
    if game_slug not in _GAME_CONFIGS:
        return JsonResponse({"error": "unknown game"}, status=404)

    from core.models import GameQuestion
    center = _sp_center(request)

    if request.method == "GET":
        db_qs = list(
            GameQuestion.objects.filter(center=center, game_slug=game_slug, is_active=True)
            .values("id", "level", "question_data", "is_ai_generated", "created_at")
        )
        defaults = _DEFAULT_QUESTIONS.get(game_slug, [])
        return JsonResponse({
            "ok": True,
            "game": _GAME_CONFIGS[game_slug],
            "db_questions": db_qs,
            "default_questions": defaults,
            "db_count": len(db_qs),
            "default_count": len(defaults),
        })

    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "invalid json"}, status=400)
        level = int(data.get("level", 1))
        question_data = data.get("question_data")
        if not question_data:
            return JsonResponse({"error": "question_data required"}, status=400)
        q = GameQuestion.objects.create(
            center=center,
            game_slug=game_slug,
            level=level,
            question_data=question_data,
            created_by=u,
        )
        return JsonResponse({"ok": True, "id": q.pk})

    if request.method == "DELETE":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "invalid json"}, status=400)
        pk = data.get("id")
        GameQuestion.objects.filter(pk=pk, center=center, game_slug=game_slug).update(is_active=False)
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required
@require_POST
def game_questions_ai_generate(request, game_slug):
    """AI orqali o'yin savollari generatsiya qilish (director/manager)."""
    u = request.user
    if u.role not in ("director", "manager") and not u.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)
    if game_slug not in _GAME_CONFIGS:
        return JsonResponse({"error": "unknown game"}, status=404)

    from core.models import GameQuestion
    from core.services.ai_insights import _prompt_json

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    count = min(int(data.get("count", 10)), 30)
    level = int(data.get("level", 1))
    center = _sp_center(request)
    cfg = _GAME_CONFIGS[game_slug]
    game_name = cfg["name"]

    game_type_hints = {
        "geography_quiz": 'Har bir savol uchun to\'g\'ri javob va 3 ta noto\'g\'ri javob bering. Mavzu: dunyo geografiyasi, poytaxtlar, daryolar, tog\'lar.',
        "english_words": "Har bir savol o'zbek so'zi bo'lsin va 4 ta inglizcha variant bering (1 ta to'g'ri).",
        "science_quiz": "Har bir savol fan va tabiat haqida bo'lsin (fizika, kimyo, biologiya, astronomiya).",
        "quick_quiz": "Har bir savol umumiy bilimlar haqida bo'lsin (tarix, sport, tabiat, matematika).",
        "word_scramble": "Har bir savol \"Qaysi so'z to'g'ri yozilgan?\" shaklida bo'lsin, 4 ta inglizcha variant.",
        "number_sequence": "Har bir savol sonlar ketma-ketligi haqida bo'lsin. 4 ta javob varianti bering.",
        "shapes_quiz": "Har bir savol geometriya va shakllar haqida bo'lsin. 4 ta javob varianti bering.",
        "math_sprint": "Har bir savol arifmetik hisob masalasi bo'lsin. 4 ta javob varianti bering.",
        "times_table": "Har bir savol ko'paytirish jadvaliga doir bo'lsin (2dan 12gacha). 4 ta javob varianti bering.",
        "true_false": "Har bir savol \"ha\" yoki \"yo'q\" bilan javob beriladigan bo'lsin. Javob true yoki false bo'lsin.",
        "formula_fill": "Har bir savol formula to'ldirish haqida bo'lsin. 4 ta variant bering.",
        "memory_match": "Har bir savol yodlash mashqi bo'lsin — emoji juftliklarini tasvirlovchi format.",
    }
    hint = game_type_hints.get(game_slug, "Har bir savol 4 ta javob variantiga ega bo'lsin.")

    if game_slug == "true_false":
        prompt = f"""
Sen O'zbekistondagi ta'lim markazida o'quvchilar uchun "{game_name}" o'yini savollarini yozayapsan (daraja: {level}).
{hint}
{count} ta savol yarat. Natijani FAQAT JSON formatda qaytar:
{{
  "questions": [
    {{"q": "Savol matni?", "a": true}},
    {{"q": "Savol matni?", "a": false}},
    ...
  ]
}}
"""
    else:
        prompt = f"""
Sen O'zbekistondagi ta'lim markazida o'quvchilar uchun "{game_name}" o'yini savollarini yozayapsan (daraja: {level}).
{hint}
{count} ta savol yarat. Natijani FAQAT JSON formatda qaytar:
{{
  "questions": [
    {{"q": "Savol matni?", "opts": ["A", "B", "C", "D"], "a": 0}},
    ...
  ]
}}
"a" — to'g'ri javob indeksi (0–3). Barcha savollar o'zbek tilida bo'lsin.
"""

    try:
        result = _prompt_json(
            prompt,
            default={"questions": []},
            cache_key=f"game_ai_{game_slug}_l{level}_{count}",
            ttl=60,
        )
        generated = result.get("questions", [])
        if not generated:
            return JsonResponse({"error": "AI javob bermadi"}, status=500)

        saved = []
        for item in generated[:count]:
            q = GameQuestion.objects.create(
                center=center,
                game_slug=game_slug,
                level=level,
                question_data=item,
                is_ai_generated=True,
                created_by=u,
            )
            saved.append({"id": q.pk, "question_data": item})

        return JsonResponse({"ok": True, "count": len(saved), "questions": saved})
    except Exception as e:
        logger.exception("game_questions_ai_generate failed")
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
#  GURUH CHAT API
# ─────────────────────────────────────────────

def _check_chat_access(u, group, center):
    if u.role in ('director', 'manager'):
        return True
    if u.role == 'teacher':
        return group.oqituvchi_id == u.id or group.support_teacher_id == u.id
    if u.role == 'student':
        from education.models import Enrollment
        return Enrollment.objects.filter(group=group, student=u, is_deleted=False).exists()
    return False


def _msg_to_dict(m, me_id):
    from core.models import ChatMessageRead
    atts = [
        {
            'type': a.att_type,
            'name': a.original_name,
            'url': a.file.url if a.file else '',
            'link': a.link_url,
            'size': a.file_size,
        }
        for a in m.attachments.all()
    ]
    reply = None
    if m.reply_to and not m.reply_to.is_deleted:
        reply = {
            'id': m.reply_to.id,
            'sender': m.reply_to.sender.get_full_name() or m.reply_to.sender.email,
            'sender_id': m.reply_to.sender_id,
            'body': m.reply_to.body[:80],
            'has_att': m.reply_to.attachments.exists(),
        }
    read_count = m.reads.exclude(user_id=me_id).count() if m.sender_id == me_id else 0
    return {
        'id': m.id,
        'sender_id': m.sender_id,
        'sender_name': m.sender.get_full_name() or m.sender.email,
        'sender_role': m.sender.role,
        'body': m.body,
        'reply': reply,
        'attachments': atts,
        'created_at': m.created_at.strftime('%H:%M'),
        'created_date': m.created_at.strftime('%Y-%m-%d'),
        'created_iso': m.created_at.isoformat(),
        'is_mine': m.sender_id == me_id,
        'read_count': read_count,
    }


def _update_presence(chat, user):
    from core.models import ChatPresence
    ChatPresence.objects.update_or_create(chat=chat, user=user, defaults={})


def _get_online_count(chat):
    from core.models import ChatPresence
    from django.utils import timezone
    cutoff = timezone.now() - timezone.timedelta(minutes=3)
    return ChatPresence.objects.filter(chat=chat, last_seen__gte=cutoff).count()


def _mark_messages_read(messages, user):
    from core.models import ChatMessageRead
    existing = set(
        ChatMessageRead.objects.filter(message__in=messages, user=user)
        .values_list('message_id', flat=True)
    )
    new_reads = [
        ChatMessageRead(message=m, user=user)
        for m in messages
        if m.sender_id != user.id and m.id not in existing
    ]
    if new_reads:
        ChatMessageRead.objects.bulk_create(new_reads, ignore_conflicts=True)


@login_required
def chat_messages_api(request, group_id):
    from education.models import Group
    from core.models import GroupChat, ChatMessage
    from django.shortcuts import get_object_or_404

    u = request.user
    center = getattr(u, 'center', None)
    if not center:
        return JsonResponse({'ok': False}, status=403)

    group = get_object_or_404(Group, id=group_id, center=center)
    if not _check_chat_access(u, group, center):
        return JsonResponse({'ok': False}, status=403)

    chat = get_object_or_404(GroupChat, group=group, center=center)

    # Update presence
    _update_presence(chat, u)

    after_id = request.GET.get('after')
    if after_id:
        try:
            qs = list(
                ChatMessage.objects.filter(chat=chat, is_deleted=False, id__gt=int(after_id))
                .select_related('sender', 'reply_to', 'reply_to__sender')
                .prefetch_related('attachments', 'reads')
                .order_by('created_at')
            )
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': 'invalid after'}, status=400)
    else:
        qs = list(reversed(list(
            ChatMessage.objects.filter(chat=chat, is_deleted=False)
            .select_related('sender', 'reply_to', 'reply_to__sender')
            .prefetch_related('attachments', 'reads')
            .order_by('-created_at')[:60]
        )))

    # Mark incoming messages as read
    _mark_messages_read(qs, u)

    # Updated read counts for my recent messages
    from core.models import ChatMessageRead
    my_recent = list(
        ChatMessage.objects.filter(chat=chat, sender=u, is_deleted=False)
        .order_by('-created_at')[:30]
        .prefetch_related('reads')
    )
    my_reads = {
        m.id: m.reads.exclude(user=u).count()
        for m in my_recent
    }

    # Typing users (excluding current user)
    now = timezone.now()
    from core.models import ChatPresence as CP
    typing_qs = CP.objects.filter(
        chat=chat, typing_until__gt=now
    ).exclude(user=u).select_related('user')
    typing_users = [
        {
            'name': p.user.get_full_name() or p.user.email,
            'role': getattr(p.user, 'role', ''),
        }
        for p in typing_qs
    ]

    return JsonResponse({
        'ok': True,
        'messages': [_msg_to_dict(m, u.id) for m in qs],
        'online_count': _get_online_count(chat),
        'my_reads': my_reads,
        'typing_users': typing_users,
    })


@login_required
@require_POST
def chat_typing_api(request, group_id):
    """Foydalanuvchi yozayotganini qayd etadi (4 soniya muddatli)."""
    from education.models import Group
    from core.models import GroupChat, ChatPresence
    from django.shortcuts import get_object_or_404

    u = request.user
    center = getattr(u, 'center', None)
    if not center:
        return JsonResponse({'ok': False}, status=403)

    group = get_object_or_404(Group, id=group_id, center=center)
    if not _check_chat_access(u, group, center):
        return JsonResponse({'ok': False}, status=403)

    chat = get_object_or_404(GroupChat, group=group, center=center)
    typing_until = timezone.now() + timezone.timedelta(seconds=4)
    ChatPresence.objects.update_or_create(
        chat=chat, user=u,
        defaults={'typing_until': typing_until},
    )
    return JsonResponse({'ok': True})


@login_required
@require_POST
def chat_send_api(request, group_id):
    from education.models import Group
    from core.models import GroupChat, ChatMessage, ChatAttachment
    from django.shortcuts import get_object_or_404

    u = request.user
    center = getattr(u, 'center', None)
    if not center:
        return JsonResponse({'ok': False, 'error': "Ruxsat yo'q"}, status=403)

    group = get_object_or_404(Group, id=group_id, center=center)
    if not _check_chat_access(u, group, center):
        return JsonResponse({'ok': False, 'error': "Ruxsat yo'q"}, status=403)

    chat, _ = GroupChat.objects.get_or_create(center=center, group=group)
    _update_presence(chat, u)

    body = request.POST.get('body', '').strip()
    reply_to_id = request.POST.get('reply_to', '').strip()
    link_url = request.POST.get('link_url', '').strip()
    uploaded_file = request.FILES.get('file')

    if not body and not uploaded_file and not link_url:
        return JsonResponse({'ok': False, 'error': "Xabar bo'sh bo'lishi mumkin emas"}, status=400)

    reply_to = None
    if reply_to_id:
        try:
            reply_to = ChatMessage.objects.get(id=int(reply_to_id), chat=chat, is_deleted=False)
        except (ChatMessage.DoesNotExist, ValueError):
            pass

    msg = ChatMessage.objects.create(chat=chat, sender=u, center=center, body=body, reply_to=reply_to)

    att = None
    if uploaded_file:
        MAX_SIZE = 20 * 1024 * 1024
        if uploaded_file.size > MAX_SIZE:
            msg.delete()
            return JsonResponse({'ok': False, 'error': 'Fayl hajmi 20MB dan oshmasligi kerak'}, status=400)
        ext = uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''
        if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
            att_type = ChatAttachment.ATT_IMAGE
        elif ext == 'pdf':
            att_type = ChatAttachment.ATT_PDF
        else:
            att_type = ChatAttachment.ATT_FILE
        att = ChatAttachment.objects.create(
            message=msg, file=uploaded_file, att_type=att_type,
            original_name=uploaded_file.name, file_size=uploaded_file.size,
        )
    elif link_url:
        att = ChatAttachment.objects.create(
            message=msg, link_url=link_url, att_type=ChatAttachment.ATT_LINK,
            original_name=link_url[:255],
        )

    msg_data = _msg_to_dict(
        ChatMessage.objects.select_related('sender', 'reply_to', 'reply_to__sender')
        .prefetch_related('attachments', 'reads').get(pk=msg.pk),
        u.id,
    )
    return JsonResponse({
        'ok': True,
        'message': msg_data,
        'online_count': _get_online_count(chat),
    })
