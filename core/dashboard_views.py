"""
ChaqmoqApp — 8 ta statistik dashboard uchun view va API endpointlar.
Har bir dashboard:
  - Page view (HTML render)
  - JSON API endpoint (Chart.js uchun ma'lumot)
  - 5 daqiqa cache
  - Director/Manager role check
"""

import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import Center, User
from education.models import Attendance, Category, Enrollment, Group, Payment
from store.models import Expense, Lead, Product, Sale


# ─────────────────────────── Helpers ────────────────────────────

def _get_center(request):
    """Return center for the request user (director / manager / superuser)."""
    user = request.user
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return getattr(request, "center", None) or getattr(user, "center", None)
    role = getattr(user, "role", None)
    if role in ("director", "manager"):
        return getattr(request, "center", None) or getattr(user, "center", None)
    return None


def _parse_dates(request):
    """Parse date_from / date_to query params; default = current month → today."""
    today = timezone.localdate()
    try:
        d_from = date.fromisoformat(request.GET.get("date_from", ""))
    except (ValueError, TypeError):
        d_from = today.replace(day=1)
    try:
        d_to = date.fromisoformat(request.GET.get("date_to", ""))
    except (ValueError, TypeError):
        d_to = today
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    return d_from, d_to


UZ_MONTHS = {
    1: "Yan", 2: "Fev", 3: "Mar", 4: "Apr", 5: "May", 6: "Iyn",
    7: "Iyl", 8: "Avg", 9: "Sen", 10: "Okt", 11: "Noy", 12: "Dek",
}


def _six_month_range(anchor: date):
    """Yield (m_start, m_end, label) for 6 months ending with anchor's month."""
    for i in range(5, -1, -1):
        raw = anchor.replace(day=1) - timedelta(days=30 * i)
        m_start = raw.replace(day=1)
        m_end = m_start.replace(day=calendar.monthrange(m_start.year, m_start.month)[1])
        yield m_start, m_end, UZ_MONTHS[m_start.month]


def _403():
    return JsonResponse({"error": "Ruxsat yo'q"}, status=403)


# ══════════════════════════════════════════════════════════════════
#  1. MOLIYAVIY DASHBOARD
# ══════════════════════════════════════════════════════════════════

@login_required
def financial_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/financial.html", {
        "center": center,
        "page_title": "Moliyaviy Panel",
        "active_dash": "financial",
    })


@login_required
def financial_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_fin:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    pay_qs = Payment.objects.filter(center=center, paid_date__range=(d_from, d_to))
    revenue = pay_qs.aggregate(s=Sum("summa"))["s"] or 0
    pay_count = pay_qs.count()
    avg_pay = int(revenue / pay_count) if pay_count else 0

    exp_qs = Expense.objects.filter(center=center, sana__date__range=(d_from, d_to))
    expenses = exp_qs.aggregate(s=Sum("summa"))["s"] or 0

    # Teacher compensation: attendance × (lesson_price × teacher_%)
    teacher_comp = 0
    att_map = {
        r["group_id"]: r["cnt"]
        for r in Attendance.objects.filter(
            group__center=center, date__range=(d_from, d_to), status="present"
        ).values("group_id").annotate(cnt=Count("id"))
    }
    for enr in Enrollment.objects.filter(group__center=center, is_active=True).select_related("group"):
        cnt = att_map.get(enr.group_id, 0)
        if cnt:
            lessons = enr.group.oy_dars_soni or 12
            lesson_pay = enr.kurs_narhi / lessons if lessons else 0
            teacher_comp += lesson_pay * (enr.oqituvchi_foiz / 100) * cnt
    teacher_comp = int(teacher_comp)

    net_profit = revenue - expenses - teacher_comp
    profit_margin = round(net_profit / revenue * 100, 1) if revenue else 0

    days = (d_to - d_from).days + 1
    prev_rev = Payment.objects.filter(
        center=center,
        paid_date__range=(d_from - timedelta(days=days), d_from - timedelta(days=1)),
    ).aggregate(s=Sum("summa"))["s"] or 0
    rev_growth = round((revenue - prev_rev) / prev_rev * 100, 1) if prev_rev else 0

    # 6-month trend
    m_labels, m_inc, m_exp = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_inc.append(int(Payment.objects.filter(center=center, paid_date__range=(ms, me)).aggregate(s=Sum("summa"))["s"] or 0))
        m_exp.append(int(Expense.objects.filter(center=center, sana__date__range=(ms, me)).aggregate(s=Sum("summa"))["s"] or 0))

    # Payment type breakdown
    type_map = {"cash": "Naqd", "card": "Karta", "mixed": "Aralash"}
    pay_types = [
        {"label": type_map.get(r["payment_type"], r["payment_type"]),
         "value": int(r["total"] or 0), "count": r["cnt"]}
        for r in pay_qs.values("payment_type").annotate(total=Sum("summa"), cnt=Count("id"))
    ]

    # Category breakdown
    cat_breakdown = [
        {"label": r.get("group__category_obj__name") or "Bo'limsiz",
         "value": int(r["total"] or 0)}
        for r in pay_qs.values("group__category_obj__name")
            .annotate(total=Sum("summa")).order_by("-total")[:6]
    ]

    data = {
        "kpis": {
            "revenue": revenue, "net_profit": net_profit,
            "expenses": expenses, "teacher_comp": teacher_comp,
            "profit_margin": profit_margin, "avg_pay": avg_pay,
            "pay_count": pay_count, "rev_growth": rev_growth,
        },
        "charts": {
            "m_labels": m_labels, "m_inc": m_inc, "m_exp": m_exp,
            "pay_types": pay_types, "cat_breakdown": cat_breakdown,
        },
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  2. O'QUVCHI SAMARADORLIGI
# ══════════════════════════════════════════════════════════════════

@login_required
def student_performance_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/student_performance.html", {
        "center": center,
        "page_title": "O'quvchi Samaradorligi",
        "active_dash": "student_performance",
    })


@login_required
def student_performance_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_stud:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    students_qs = User.objects.filter(center=center, role="student", is_archived=False)
    total_students = students_qs.count()
    active_enroll = Enrollment.objects.filter(group__center=center, is_active=True, student__is_archived=False)
    active_count = active_enroll.values("student").distinct().count()
    new_students = students_qs.filter(date_joined__date__range=(d_from, d_to)).count()

    att_qs = Attendance.objects.filter(group__center=center, date__range=(d_from, d_to))
    total_att = att_qs.count()
    present_att = att_qs.filter(status="present").count()
    avg_att_rate = round(present_att / total_att * 100, 1) if total_att else 0

    per_student = att_qs.values("student_id").annotate(
        tot=Count("id"), pres=Count("id", filter=Q(status="present"))
    )
    low_activity = sum(1 for r in per_student if (r["pres"] / r["tot"] * 100 if r["tot"] else 0) < 70)
    churn_risk = sum(1 for r in per_student if (r["pres"] / r["tot"] * 100 if r["tot"] else 0) < 30)

    thirty_ago = timezone.localdate() - timedelta(days=30)
    recent_ids = Attendance.objects.filter(
        group__center=center, date__gte=thirty_ago, status="present"
    ).values_list("student_id", flat=True).distinct()
    churn_actual = active_enroll.exclude(student_id__in=recent_ids).values("student").distinct().count()

    group_dist = list(
        active_enroll.values("group__nom").annotate(cnt=Count("student", distinct=True)).order_by("-cnt")[:8]
    )

    m_labels, m_new, m_att = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_new.append(students_qs.filter(date_joined__date__range=(ms, me)).count())
        tot = Attendance.objects.filter(group__center=center, date__range=(ms, me)).count()
        pres = Attendance.objects.filter(group__center=center, date__range=(ms, me), status="present").count()
        m_att.append(round(pres / tot * 100, 1) if tot else 0)

    top_students = list(
        att_qs.values("student__ism", "student__familya").annotate(
            tot=Count("id"), pres=Count("id", filter=Q(status="present"))
        ).order_by("-pres")[:6]
    )
    top_students_data = [
        {
            "name": f"{r['student__ism']} {r['student__familya']}",
            "rate": round(r["pres"] / r["tot"] * 100, 1) if r["tot"] else 0,
            "sessions": r["pres"],
        }
        for r in top_students
    ]

    data = {
        "kpis": {
            "total_students": total_students, "active_count": active_count,
            "new_students": new_students, "avg_att_rate": avg_att_rate,
            "low_activity": low_activity, "churn_actual": churn_actual,
        },
        "charts": {
            "m_labels": m_labels, "m_new": m_new, "m_att": m_att,
            "group_labels": [r["group__nom"] for r in group_dist],
            "group_counts": [r["cnt"] for r in group_dist],
        },
        "top_students": top_students_data,
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  3. USTOZ SAMARADORLIGI
# ══════════════════════════════════════════════════════════════════

@login_required
def teacher_performance_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/teacher_performance.html", {
        "center": center,
        "page_title": "Ustoz Samaradorligi",
        "active_dash": "teacher_performance",
    })


@login_required
def teacher_performance_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_teach:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    teachers = list(User.objects.filter(center=center, role="teacher"))
    total_teachers = len(teachers)

    stats = []
    for t in teachers:
        rev = Payment.objects.filter(
            group__oqituvchi=t, center=center, paid_date__range=(d_from, d_to)
        ).aggregate(s=Sum("summa"))["s"] or 0
        students = Enrollment.objects.filter(
            group__oqituvchi=t, group__center=center, is_active=True
        ).values("student").distinct().count()
        groups = Group.objects.filter(center=center, oqituvchi=t, is_archived=False).count()
        hours = Attendance.objects.filter(
            group__oqituvchi=t, group__center=center,
            date__range=(d_from, d_to), status="present",
        ).count()
        stats.append({
            "name": f"{t.ism} {t.familya}",
            "revenue": int(rev), "students": students,
            "groups": groups, "hours": hours,
        })
    stats.sort(key=lambda x: -x["revenue"])

    total_rev = sum(s["revenue"] for s in stats)
    avg_rev = int(total_rev / total_teachers) if total_teachers else 0
    total_students = sum(s["students"] for s in stats)
    ratio = round(total_students / total_teachers, 1) if total_teachers else 0

    top10 = stats[:10]
    data = {
        "kpis": {
            "total_teachers": total_teachers, "avg_rev": avg_rev,
            "total_rev": total_rev, "ratio": ratio,
            "total_hours": sum(s["hours"] for s in stats),
        },
        "charts": {
            "names": [s["name"] for s in top10],
            "revenues": [s["revenue"] for s in top10],
            "students": [s["students"] for s in top10],
            "hours": [s["hours"] for s in top10],
        },
        "teacher_list": stats[:15],
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  4. GURUH VA KURSLAR
# ══════════════════════════════════════════════════════════════════

@login_required
def groups_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/groups.html", {
        "center": center,
        "page_title": "Guruh va Kurslar",
        "active_dash": "groups",
    })


@login_required
def groups_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_grp:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    groups_qs = Group.objects.filter(center=center, is_archived=False)
    total_groups = groups_qs.count()
    active_groups = groups_qs.filter(is_closed=False).count()

    active_enroll_total = Enrollment.objects.filter(group__center=center, is_active=True).count()
    avg_size = round(active_enroll_total / active_groups, 1) if active_groups else 0

    group_stats = []
    for g in groups_qs.select_related("oqituvchi", "category_obj")[:20]:
        enrolled = Enrollment.objects.filter(group=g, is_active=True).count()
        rev = Payment.objects.filter(group=g, paid_date__range=(d_from, d_to)).aggregate(s=Sum("summa"))["s"] or 0
        att_tot = Attendance.objects.filter(group=g, date__range=(d_from, d_to)).count()
        att_pre = Attendance.objects.filter(group=g, date__range=(d_from, d_to), status="present").count()
        group_stats.append({
            "name": g.nom,
            "teacher": f"{g.oqituvchi.ism} {g.oqituvchi.familya}" if g.oqituvchi else "—",
            "category": g.category_obj.name if g.category_obj else g.category,
            "enrolled": enrolled,
            "revenue": int(rev),
            "att_rate": round(att_pre / att_tot * 100, 1) if att_tot else 0,
        })
    group_stats.sort(key=lambda x: -x["revenue"])

    cat_dist = list(
        Enrollment.objects.filter(group__center=center, is_active=True)
        .values("group__category_obj__name")
        .annotate(cnt=Count("student", distinct=True))
        .order_by("-cnt")[:6]
    )

    m_labels, m_enroll, m_rev = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_enroll.append(Enrollment.objects.filter(group__center=center, created_at__date__range=(ms, me)).count())
        m_rev.append(int(Payment.objects.filter(center=center, paid_date__range=(ms, me)).aggregate(s=Sum("summa"))["s"] or 0))

    top8 = group_stats[:8]
    data = {
        "kpis": {
            "total_groups": total_groups, "active_groups": active_groups,
            "avg_size": avg_size, "total_rev": sum(g["revenue"] for g in group_stats),
        },
        "charts": {
            "m_labels": m_labels, "m_enroll": m_enroll, "m_rev": m_rev,
            "cat_labels": [r["group__category_obj__name"] or "Boshqa" for r in cat_dist],
            "cat_counts": [r["cnt"] for r in cat_dist],
            "grp_names": [g["name"] for g in top8],
            "grp_revs": [g["revenue"] for g in top8],
            "grp_enroll": [g["enrolled"] for g in top8],
        },
        "group_list": group_stats[:12],
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  5. TO'LOV VA OBUNALAR
# ══════════════════════════════════════════════════════════════════

@login_required
def billing_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/billing.html", {
        "center": center,
        "page_title": "To'lov va Obunalar",
        "active_dash": "billing",
    })


@login_required
def billing_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_bill:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    pay_qs = Payment.objects.filter(center=center, paid_date__range=(d_from, d_to))
    total_pay = pay_qs.aggregate(s=Sum("summa"))["s"] or 0
    pay_count = pay_qs.count()
    avg_pay = int(total_pay / pay_count) if pay_count else 0

    daily = list(pay_qs.values("paid_date").annotate(tot=Sum("summa")).order_by("paid_date"))
    daily_labels = [str(r["paid_date"]) for r in daily]
    daily_amounts = [int(r["tot"] or 0) for r in daily]

    type_map = {"cash": "Naqd", "card": "Karta", "mixed": "Aralash"}
    pay_types = [
        {"label": type_map.get(r["payment_type"], r["payment_type"]),
         "value": int(r["total"] or 0), "count": r["cnt"]}
        for r in pay_qs.values("payment_type").annotate(total=Sum("summa"), cnt=Count("id"))
    ]

    # Subscription info
    sub_info = {}
    try:
        sub = center.subscriptions.filter(status="ACTIVE").first()
        if sub:
            sub_info = {
                "plan": sub.plan.title,
                "status": sub.status,
                "days_left": sub.days_left(),
                "expires_at": str(sub.expires_at.date()) if sub.expires_at else None,
                "monthly_price": sub.plan.monthly_price,
            }
    except Exception:
        pass

    # Current month debt
    total_debt, total_debtors = 0, 0
    try:
        from django.db.models import OuterRef, Subquery
        from django.db.models.functions import Coalesce
        from education.models import PaymentAllocation, TuitionMonth
        from education.services.tuition import tuition_month_fee_field

        cur_month = timezone.localdate().replace(day=1)
        fee_field = tuition_month_fee_field()
        fee_sub = TuitionMonth.objects.filter(enrollment=OuterRef("pk"), month=cur_month).values("enrollment").annotate(s=Sum(fee_field)).values("s")
        paid_sub = PaymentAllocation.objects.filter(tuition_month__enrollment=OuterRef("pk"), tuition_month__month=cur_month).values("tuition_month__enrollment").annotate(s=Sum("amount")).values("s")
        debt_qs = (
            Enrollment.objects.filter(group__center=center, is_active=True, student__is_archived=False)
            .annotate(f=Coalesce(Subquery(fee_sub), 0), p=Coalesce(Subquery(paid_sub), 0))
            .annotate(d=F("f") - F("p")).filter(d__gt=0)
        )
        total_debt = int(debt_qs.aggregate(s=Sum("d"))["s"] or 0)
        total_debtors = debt_qs.values("student").distinct().count()
    except Exception:
        pass

    data = {
        "kpis": {
            "total_pay": total_pay, "pay_count": pay_count,
            "avg_pay": avg_pay, "total_debt": total_debt,
            "total_debtors": total_debtors,
        },
        "subscription": sub_info,
        "charts": {
            "daily_labels": daily_labels,
            "daily_amounts": daily_amounts,
            "pay_types": pay_types,
        },
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  6. MARKETING VA LIDLAR
# ══════════════════════════════════════════════════════════════════

@login_required
def marketing_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/marketing.html", {
        "center": center,
        "page_title": "Marketing va Lidlar",
        "active_dash": "marketing",
    })


@login_required
def marketing_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_mkt:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    leads_qs = Lead.objects.filter(center=center, qoshilgan_sana__date__range=(d_from, d_to))
    total_leads = leads_qs.count()
    converted = leads_qs.filter(Q(converted_to_student=True) | Q(converted_user__isnull=False)).count()
    conv_rate = round(converted / total_leads * 100, 1) if total_leads else 0

    days = (d_to - d_from).days + 1
    prev_leads = Lead.objects.filter(
        center=center,
        qoshilgan_sana__date__range=(d_from - timedelta(days=days), d_from - timedelta(days=1)),
    ).count()
    leads_growth = round((total_leads - prev_leads) / prev_leads * 100, 1) if prev_leads else 0

    by_source = list(
        leads_qs.values("manba__nom")
        .annotate(
            total=Count("id"),
            conv=Count("id", filter=Q(converted_to_student=True) | Q(converted_user__isnull=False)),
        )
        .order_by("-total")[:8]
    )

    m_labels, m_leads, m_conv = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        qs = Lead.objects.filter(center=center, qoshilgan_sana__date__range=(ms, me))
        m_leads.append(qs.count())
        m_conv.append(qs.filter(converted_to_student=True).count())

    data = {
        "kpis": {
            "total_leads": total_leads, "converted": converted,
            "conv_rate": conv_rate, "leads_growth": leads_growth,
        },
        "charts": {
            "m_labels": m_labels, "m_leads": m_leads, "m_conv": m_conv,
            "src_labels": [r["manba__nom"] or "Noma'lum" for r in by_source],
            "src_counts": [r["total"] for r in by_source],
            "src_conv": [r["conv"] for r in by_source],
        },
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  7. INVENTAR VA MAHSULOTLAR
# ══════════════════════════════════════════════════════════════════

@login_required
def inventory_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/inventory.html", {
        "center": center,
        "page_title": "Inventar va Mahsulotlar",
        "active_dash": "inventory",
    })


@login_required
def inventory_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_inv:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    products_qs = Product.objects.filter(center=center)
    total_products = products_qs.count()

    # Sale stats: Sale.sana is DateTimeField (auto_now_add)
    sale_qs = Sale.objects.filter(center=center, sana__date__range=(d_from, d_to))
    total_sale_count = sale_qs.count()
    total_sale_rev = int(sale_qs.aggregate(s=Sum(F("qty") * F("narx_som")))["s"] or 0)

    product_list = []
    for p in products_qs[:15]:
        p_sales = sale_qs.filter(product=p)
        qty_sold = p_sales.aggregate(s=Sum("qty"))["s"] or 0
        rev = int(p_sales.aggregate(s=Sum(F("qty") * F("narx_som")))["s"] or 0)
        product_list.append({
            "name": p.nom,
            "price_som": p.narx_som,
            "price_chaqmoq": p.narx_chaqmoq,
            "qty_sold": qty_sold,
            "revenue": rev,
        })
    product_list.sort(key=lambda x: -x["revenue"])

    top8 = product_list[:8]
    data = {
        "kpis": {
            "total_products": total_products,
            "total_sale_count": total_sale_count,
            "total_sale_rev": total_sale_rev,
        },
        "charts": {
            "p_names": [p["name"] for p in top8],
            "p_revs": [p["revenue"] for p in top8],
            "p_qty": [p["qty_sold"] for p in top8],
        },
        "product_list": product_list[:12],
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  8. SISTEMA ANALITIKASI
# ══════════════════════════════════════════════════════════════════

@login_required
def analytics_dashboard(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/analytics.html", {
        "center": center,
        "page_title": "Sistema Analitikasi",
        "active_dash": "analytics",
    })


@login_required
def analytics_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_ana:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    today = timezone.localdate()
    all_users = User.objects.filter(center=center)
    total_users = all_users.count()
    active_today = all_users.filter(last_login__date=today).count()
    active_week = all_users.filter(last_login__date__gte=today - timedelta(days=7)).count()
    active_month = all_users.filter(last_login__date__gte=today.replace(day=1)).count()

    m_labels, m_new, m_act = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_new.append(all_users.filter(date_joined__date__range=(ms, me)).count())
        m_act.append(all_users.filter(last_login__date__range=(ms, me)).count())

    role_map = {
        "director": "Direktor", "manager": "Manager",
        "teacher": "O'qituvchi", "student": "O'quvchi", "parent": "Ota-ona",
    }
    role_dist = list(all_users.values("role").annotate(cnt=Count("id")).order_by("-cnt"))

    data = {
        "kpis": {
            "total_users": total_users, "active_today": active_today,
            "active_week": active_week, "active_month": active_month,
            "students": all_users.filter(role="student", is_archived=False).count(),
            "teachers": all_users.filter(role="teacher").count(),
            "managers": all_users.filter(role="manager").count(),
        },
        "charts": {
            "m_labels": m_labels, "m_new": m_new, "m_act": m_act,
            "role_labels": [role_map.get(r["role"], r["role"]) for r in role_dist],
            "role_counts": [r["cnt"] for r in role_dist],
        },
        "period": {"from": str(d_from), "to": str(d_to)},
    }
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  DASHBOARD HUB
# ══════════════════════════════════════════════════════════════════

@login_required
def dashboard_hub(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/hub.html", {
        "center": center,
        "page_title": "Dashboard Markazi",
        "active_dash": "hub",
    })


# ══════════════════════════════════════════════════════════════════
#  DIRECTOR OVERVIEW — yagona sahifali umumiy dashboard
# ══════════════════════════════════════════════════════════════════

@login_required
def director_overview(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    return render(request, "core/dashboards/overview.html", {
        "center": center,
        "page_title": "Direktor Paneli",
        "active_dash": "overview",
    })
