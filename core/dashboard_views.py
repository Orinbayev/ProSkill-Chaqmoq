"""
ChaqmoqApp — 8 ta statistik dashboard uchun view va API endpointlar.
Har bir dashboard:
  - Page view (HTML render)
  - JSON API endpoint (Chart.js uchun ma'lumot)
  - 5 daqiqa cache
  - Director/Manager role check
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import Branch, Center, User
from education.models import Attendance, Category, Enrollment, Group, MonthlyFinanceSnapshot, Payment, PaymentAllocation
from store.models import Expense, Lead, Product, PurchaseRequest, Sale


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


def _period_stats(d_from: date, d_to: date):
    days = (d_to - d_from).days + 1
    prev_to = d_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=days - 1)
    return {
        "days": days,
        "prev_from": prev_from,
        "prev_to": prev_to,
    }


def _pct_change(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return None if current else 0.0
    return round((current - previous) / previous * 100, 1)


def _attendance_present_filter():
    return Q(status="present") | Q(present=True) | Q(forced=True)


def _payments_for_center(center):
    """
    Productiondagi eski to'lovlarda center bo'sh qolgan bo'lishi mumkin.
    Shunda group/student/enrollment orqali markazni aniqlab olamiz.
    """
    return Payment.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, group__center=center)
        | Q(center__isnull=True, student__center=center)
        | Q(center__isnull=True, enrollment__center=center)
    )


def _payment_allocations_for_center(center):
    """
    Productionda tarixiy daromad ko'pincha PaymentAllocation orqali saqlanadi.
    center null bo'lgan legacy allocation/paymentlar uchun ham fallback qilamiz.
    """
    return PaymentAllocation.objects.filter(
        payment__is_deleted=False,
    ).filter(
        Q(center=center)
        | Q(center__isnull=True, payment__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__group__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__student__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__enrollment__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, tuition_month__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, tuition_month__enrollment__center=center)
    )


def _deleted_payment_allocations_for_center(center):
    return PaymentAllocation.all_objects.filter(
        is_deleted=True,
    ).filter(
        Q(center=center)
        | Q(center__isnull=True, payment__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__group__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__student__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__enrollment__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, tuition_month__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, tuition_month__enrollment__center=center)
    )


def _deleted_payments_for_center(center):
    return Payment.all_objects.filter(
        is_deleted=True,
    ).filter(
        Q(center=center)
        | Q(center__isnull=True, group__center=center)
        | Q(center__isnull=True, student__center=center)
        | Q(center__isnull=True, enrollment__center=center)
    )


def _monthly_snapshot_for_center(center, m_start):
    return MonthlyFinanceSnapshot.objects.filter(
        financial_month__center=center,
        financial_month__year=m_start.year,
        financial_month__month=m_start.month,
    ).first()


def _monthly_turnover_for_center(center, m_start, m_end):
    """
    Oy kesimidagi aylanma:
    1. Allocation mavjud bo'lsa, to'lovni aynan tegishli oyga yozamiz.
    2. Allocation yo'q legacy paymentlar bo'lsa, paid_date bo'yicha fallback qilamiz.
    """
    allocated_total = int(
        _payment_allocations_for_center(center)
        .filter(tuition_month__month__range=(m_start, m_end))
        .aggregate(s=Sum("amount"))["s"] or 0
    )
    unallocated_total = int(
        _payments_for_center(center)
        .filter(paid_date__range=(m_start, m_end), allocations__isnull=True)
        .aggregate(s=Sum("summa"))["s"] or 0
    )
    active_total = allocated_total + unallocated_total
    if active_total:
        return active_total

    snapshot = _monthly_snapshot_for_center(center, m_start)
    if snapshot and snapshot.total_income:
        return int(snapshot.total_income or 0)

    deleted_allocated_total = int(
        _deleted_payment_allocations_for_center(center)
        .filter(tuition_month__month__range=(m_start, m_end))
        .aggregate(s=Sum("amount"))["s"] or 0
    )
    deleted_unallocated_total = int(
        _deleted_payments_for_center(center)
        .filter(paid_date__range=(m_start, m_end), allocations__isnull=True)
        .aggregate(s=Sum("summa"))["s"] or 0
    )
    return deleted_allocated_total + deleted_unallocated_total


def _monthly_expenses_for_center(center, m_start, m_end):
    active_total = int(
        _expenses_for_center(center)
        .filter(sana__date__range=(m_start, m_end))
        .aggregate(s=Sum("summa"))["s"] or 0
    )
    if active_total:
        return active_total

    snapshot = _monthly_snapshot_for_center(center, m_start)
    if snapshot and snapshot.total_expense:
        return int(snapshot.total_expense or 0)
    return 0


def _expenses_for_center(center):
    """
    Legacy xarajatlardagi center=null holati uchun worker/product orqali fallback.
    """
    return Expense.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, worker__center=center)
        | Q(center__isnull=True, product__center=center)
    )


def _teacher_compensation(center, d_from, d_to):
    att_map = {
        (row["group_id"], row["student_id"]): row["cnt"]
        for row in Attendance.objects.filter(
            group__center=center,
            date__range=(d_from, d_to),
        ).filter(_attendance_present_filter())
        .values("group_id", "student_id")
        .annotate(cnt=Count("id"))
    }

    total = 0
    enrollments = Enrollment.objects.filter(
        group__center=center,
        is_active=True,
        student__is_archived=False,
    ).select_related("group")
    for enr in enrollments:
        present_count = att_map.get((enr.group_id, enr.student_id), 0)
        if not present_count:
            continue
        lessons = enr.group.oy_dars_soni or 12
        fee = enr.kurs_narhi or enr.group.kurs_narxi or 0
        teacher_pct = enr.oqituvchi_foiz or enr.group.oqituvchi_foiz or 0
        if lessons <= 0 or fee <= 0 or teacher_pct <= 0:
            continue
        per_lesson_share = (fee * teacher_pct / 100) / lessons
        total += per_lesson_share * present_count
    return int(round(total))


def _payment_type_breakdown(pay_qs):
    type_map = {"cash": "Naqd", "card": "Karta", "mixed": "Aralash"}
    return [
        {
            "label": type_map.get(row["payment_type"], row["payment_type"]),
            "value": int(row["total"] or 0),
            "count": row["cnt"],
        }
        for row in pay_qs.values("payment_type").annotate(total=Sum("summa"), cnt=Count("id"))
    ]


def _financial_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    pay_qs = _payments_for_center(center).filter(paid_date__range=(d_from, d_to))
    revenue = int(pay_qs.aggregate(s=Sum("summa"))["s"] or 0)
    pay_count = pay_qs.count()
    avg_pay = int(revenue / pay_count) if pay_count else 0

    exp_qs = _expenses_for_center(center).filter(sana__date__range=(d_from, d_to))
    expenses = int(exp_qs.aggregate(s=Sum("summa"))["s"] or 0)
    teacher_comp = _teacher_compensation(center, d_from, d_to)
    total_cost = expenses + teacher_comp
    net_profit = revenue - total_cost
    profit_margin = round(net_profit / revenue * 100, 1) if revenue else 0

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_pay_qs = _payments_for_center(center).filter(paid_date__range=(prev_from, prev_to))
    prev_revenue = int(prev_pay_qs.aggregate(s=Sum("summa"))["s"] or 0)
    prev_expenses = int(
        _expenses_for_center(center).filter(sana__date__range=(prev_from, prev_to)).aggregate(s=Sum("summa"))["s"] or 0
    )
    prev_teacher_comp = _teacher_compensation(center, prev_from, prev_to)
    prev_total_cost = prev_expenses + prev_teacher_comp
    prev_net_profit = prev_revenue - prev_total_cost

    m_labels, m_inc, m_exp = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_inc.append(_monthly_turnover_for_center(center, ms, me))
        m_exp.append(_monthly_expenses_for_center(center, ms, me))

    cat_breakdown = [
        {
            "label": row.get("group__category_obj__name") or "Bo'limsiz",
            "value": int(row["total"] or 0),
        }
        for row in pay_qs.values("group__category_obj__name").annotate(total=Sum("summa")).order_by("-total")[:6]
    ]

    return {
        "kpis": {
            "revenue": revenue,
            "net_profit": net_profit,
            "expenses": expenses,
            "teacher_comp": teacher_comp,
            "total_cost": total_cost,
            "profit_margin": profit_margin,
            "avg_pay": avg_pay,
            "pay_count": pay_count,
            "changes": {
                "revenue": _pct_change(revenue, prev_revenue),
                "total_cost": _pct_change(total_cost, prev_total_cost),
                "net_profit": _pct_change(net_profit, prev_net_profit),
                "pay_count": _pct_change(pay_count, prev_pay_qs.count()),
            },
        },
        "charts": {
            "m_labels": m_labels,
            "m_inc": m_inc,
            "m_exp": m_exp,
            "pay_types": _payment_type_breakdown(pay_qs),
            "cat_breakdown": cat_breakdown,
        },
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _student_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    students_qs = User.objects.filter(center=center, role="student", is_archived=False)
    total_students = students_qs.count()
    active_enroll = Enrollment.objects.filter(
        group__center=center,
        is_active=True,
        student__is_archived=False,
    )
    active_count = active_enroll.values("student").distinct().count()
    new_students = students_qs.filter(date_joined__date__range=(d_from, d_to)).count()

    att_qs = Attendance.objects.filter(group__center=center, date__range=(d_from, d_to))
    present_filter = _attendance_present_filter()
    total_att = att_qs.count()
    present_att = att_qs.filter(present_filter).count()
    avg_att_rate = round(present_att / total_att * 100, 1) if total_att else 0

    per_student = list(
        att_qs.values("student_id")
        .annotate(tot=Count("id"), pres=Count("id", filter=present_filter))
    )
    low_activity = sum(1 for row in per_student if (row["pres"] / row["tot"] * 100 if row["tot"] else 0) < 70)
    churn_risk = sum(1 for row in per_student if (row["pres"] / row["tot"] * 100 if row["tot"] else 0) < 30)

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_students = students_qs.filter(date_joined__date__range=(prev_from, prev_to)).count()
    prev_att_qs = Attendance.objects.filter(group__center=center, date__range=(prev_from, prev_to))
    prev_att_total = prev_att_qs.count()
    prev_att_present = prev_att_qs.filter(present_filter).count()
    prev_att_rate = round(prev_att_present / prev_att_total * 100, 1) if prev_att_total else 0

    group_dist = list(
        active_enroll.values("group__nom")
        .annotate(cnt=Count("student", distinct=True))
        .order_by("-cnt")[:8]
    )

    m_labels, m_new, m_att = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_new.append(students_qs.filter(date_joined__date__range=(ms, me)).count())
        monthly_att = Attendance.objects.filter(group__center=center, date__range=(ms, me))
        tot = monthly_att.count()
        pres = monthly_att.filter(present_filter).count()
        m_att.append(round(pres / tot * 100, 1) if tot else 0)

    top_students = []
    raw_students = list(
        att_qs.values("student__ism", "student__familya")
        .annotate(tot=Count("id"), pres=Count("id", filter=present_filter))
    )
    for row in raw_students:
        rate = round(row["pres"] / row["tot"] * 100, 1) if row["tot"] else 0
        top_students.append({
            "name": f"{row['student__ism']} {row['student__familya']}",
            "rate": rate,
            "sessions": row["pres"],
        })
    top_students.sort(key=lambda row: (-row["rate"], -row["sessions"], row["name"]))

    return {
        "kpis": {
            "total_students": total_students,
            "active_count": active_count,
            "new_students": new_students,
            "avg_att_rate": avg_att_rate,
            "low_activity": low_activity,
            "churn_risk": churn_risk,
            "changes": {
                "new_students": _pct_change(new_students, prev_students),
                "avg_att_rate": round(avg_att_rate - prev_att_rate, 1),
            },
        },
        "charts": {
            "m_labels": m_labels,
            "m_new": m_new,
            "m_att": m_att,
            "group_labels": [row["group__nom"] for row in group_dist],
            "group_counts": [row["cnt"] for row in group_dist],
        },
        "top_students": top_students[:8],
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _teacher_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    teachers = list(User.objects.filter(center=center, role="teacher"))
    total_teachers = len(teachers)
    active_enrollments = Enrollment.objects.filter(group__center=center, is_active=True, student__is_archived=False)
    distinct_students = active_enrollments.values("student").distinct().count()

    stats = []
    for teacher in teachers:
        revenue = int(
            Payment.objects.filter(
                group__oqituvchi=teacher,
                center=center,
                paid_date__range=(d_from, d_to),
            ).aggregate(s=Sum("summa"))["s"] or 0
        )
        students = active_enrollments.filter(group__oqituvchi=teacher).values("student").distinct().count()
        groups = Group.objects.filter(center=center, oqituvchi=teacher, is_archived=False).count()
        hours = Attendance.objects.filter(
            group__oqituvchi=teacher,
            group__center=center,
            date__range=(d_from, d_to),
        ).filter(_attendance_present_filter()).count()
        stats.append({
            "name": f"{teacher.ism} {teacher.familya}",
            "revenue": revenue,
            "students": students,
            "groups": groups,
            "hours": hours,
        })
    stats.sort(key=lambda row: (-row["revenue"], -row["students"], row["name"]))

    total_rev = sum(row["revenue"] for row in stats)
    avg_rev = int(total_rev / total_teachers) if total_teachers else 0
    ratio = round(distinct_students / total_teachers, 1) if total_teachers else 0

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_total_rev = int(
        Payment.objects.filter(
            center=center,
            group__oqituvchi__role="teacher",
            paid_date__range=(prev_from, prev_to),
        ).aggregate(s=Sum("summa"))["s"] or 0
    )

    top10 = stats[:10]
    return {
        "kpis": {
            "total_teachers": total_teachers,
            "avg_rev": avg_rev,
            "total_rev": total_rev,
            "ratio": ratio,
            "total_hours": sum(row["hours"] for row in stats),
            "changes": {
                "total_rev": _pct_change(total_rev, prev_total_rev),
            },
        },
        "charts": {
            "names": [row["name"] for row in top10],
            "revenues": [row["revenue"] for row in top10],
            "students": [row["students"] for row in top10],
            "hours": [row["hours"] for row in top10],
        },
        "teacher_list": stats[:15],
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _groups_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    groups_qs = Group.objects.filter(center=center, is_archived=False, is_deleted=False)
    total_groups = groups_qs.count()
    active_groups = groups_qs.filter(is_closed=False).count()
    active_enroll_total = Enrollment.objects.filter(group__center=center, is_active=True).count()
    avg_size = round(active_enroll_total / active_groups, 1) if active_groups else 0

    group_stats = []
    for group in groups_qs.select_related("oqituvchi", "category_obj")[:40]:
        enrolled = Enrollment.objects.filter(group=group, is_active=True).count()
        revenue = int(
            Payment.objects.filter(group=group, paid_date__range=(d_from, d_to)).aggregate(s=Sum("summa"))["s"] or 0
        )
        att_tot = Attendance.objects.filter(group=group, date__range=(d_from, d_to)).count()
        att_pre = Attendance.objects.filter(group=group, date__range=(d_from, d_to)).filter(_attendance_present_filter()).count()
        group_stats.append({
            "name": group.nom,
            "teacher": f"{group.oqituvchi.ism} {group.oqituvchi.familya}" if group.oqituvchi else "—",
            "category": group.category_obj.name if group.category_obj else group.category,
            "enrolled": enrolled,
            "revenue": revenue,
            "att_rate": round(att_pre / att_tot * 100, 1) if att_tot else 0,
        })
    group_stats.sort(key=lambda row: (-row["revenue"], -row["enrolled"], row["name"]))

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

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_rev = int(Payment.objects.filter(center=center, paid_date__range=(prev_from, prev_to)).aggregate(s=Sum("summa"))["s"] or 0)

    top8 = group_stats[:8]
    return {
        "kpis": {
            "total_groups": total_groups,
            "active_groups": active_groups,
            "active_enroll_total": active_enroll_total,
            "avg_size": avg_size,
            "total_rev": sum(group["revenue"] for group in group_stats),
            "changes": {
                "total_rev": _pct_change(sum(group["revenue"] for group in group_stats), prev_rev),
            },
        },
        "charts": {
            "m_labels": m_labels,
            "m_enroll": m_enroll,
            "m_rev": m_rev,
            "cat_labels": [row["group__category_obj__name"] or "Boshqa" for row in cat_dist],
            "cat_counts": [row["cnt"] for row in cat_dist],
            "grp_names": [group["name"] for group in top8],
            "grp_revs": [group["revenue"] for group in top8],
            "grp_enroll": [group["enrolled"] for group in top8],
        },
        "group_list": group_stats[:12],
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _billing_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    pay_qs = Payment.objects.filter(center=center, paid_date__range=(d_from, d_to))
    total_pay = int(pay_qs.aggregate(s=Sum("summa"))["s"] or 0)
    pay_count = pay_qs.count()
    avg_pay = int(total_pay / pay_count) if pay_count else 0

    daily = list(pay_qs.values("paid_date").annotate(tot=Sum("summa")).order_by("paid_date"))
    daily_labels = [str(row["paid_date"]) for row in daily]
    daily_amounts = [int(row["tot"] or 0) for row in daily]

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

    def debt_snapshot(target_date):
        try:
            from django.db.models import OuterRef, Subquery
            from django.db.models.functions import Coalesce
            from education.models import PaymentAllocation, TuitionMonth
            from education.services.tuition import tuition_month_fee_field

            debt_month = target_date.replace(day=1)
            fee_field = tuition_month_fee_field()
            fee_sub = TuitionMonth.objects.filter(enrollment=OuterRef("pk"), month=debt_month).values("enrollment").annotate(s=Sum(fee_field)).values("s")
            paid_sub = PaymentAllocation.objects.filter(tuition_month__enrollment=OuterRef("pk"), tuition_month__month=debt_month).values("tuition_month__enrollment").annotate(s=Sum("amount")).values("s")
            debt_qs = (
                Enrollment.objects.filter(group__center=center, is_active=True, student__is_archived=False)
                .annotate(f=Coalesce(Subquery(fee_sub), 0), p=Coalesce(Subquery(paid_sub), 0))
                .annotate(d=F("f") - F("p")).filter(d__gt=0)
            )
            return int(debt_qs.aggregate(s=Sum("d"))["s"] or 0), debt_qs.values("student").distinct().count()
        except Exception:
            return 0, 0

    total_debt, total_debtors = debt_snapshot(d_to)

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_total_pay = int(Payment.objects.filter(center=center, paid_date__range=(prev_from, prev_to)).aggregate(s=Sum("summa"))["s"] or 0)
    prev_debt, _ = debt_snapshot(prev_to)

    return {
        "kpis": {
            "total_pay": total_pay,
            "pay_count": pay_count,
            "avg_pay": avg_pay,
            "total_debt": total_debt,
            "total_debtors": total_debtors,
            "daily_avg_count": round(pay_count / period["days"], 1) if period["days"] else 0,
            "changes": {
                "total_pay": _pct_change(total_pay, prev_total_pay),
                "total_debt": _pct_change(total_debt, prev_debt),
            },
        },
        "subscription": sub_info,
        "charts": {
            "daily_labels": daily_labels,
            "daily_amounts": daily_amounts,
            "pay_types": _payment_type_breakdown(pay_qs),
        },
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _marketing_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    converted_filter = Q(converted_to_student=True) | Q(converted_user__isnull=False)
    leads_qs = Lead.objects.filter(center=center, qoshilgan_sana__date__range=(d_from, d_to))
    total_leads = leads_qs.count()
    converted = leads_qs.filter(converted_filter).count()
    conv_rate = round(converted / total_leads * 100, 1) if total_leads else 0

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_leads_qs = Lead.objects.filter(center=center, qoshilgan_sana__date__range=(prev_from, prev_to))
    prev_leads = prev_leads_qs.count()

    by_source = list(
        leads_qs.values("manba__nom")
        .annotate(total=Count("id"), conv=Count("id", filter=converted_filter))
        .order_by("-total")[:8]
    )

    m_labels, m_leads, m_conv = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        qs = Lead.objects.filter(center=center, qoshilgan_sana__date__range=(ms, me))
        m_leads.append(qs.count())
        m_conv.append(qs.filter(converted_filter).count())

    return {
        "kpis": {
            "total_leads": total_leads,
            "converted": converted,
            "conv_rate": conv_rate,
            "leads_growth": _pct_change(total_leads, prev_leads),
        },
        "charts": {
            "m_labels": m_labels,
            "m_leads": m_leads,
            "m_conv": m_conv,
            "src_labels": [row["manba__nom"] or "Noma'lum" for row in by_source],
            "src_counts": [row["total"] for row in by_source],
            "src_conv": [row["conv"] for row in by_source],
        },
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _inventory_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    products_qs = Product.objects.filter(center=center)
    total_products = products_qs.count()

    approved_requests = PurchaseRequest.objects.filter(
        center=center,
        status=PurchaseRequest.APPROVED,
        sana__date__range=(d_from, d_to),
    ).select_related("product")

    total_sale_count = approved_requests.count()
    total_qty = 0
    total_sale_rev = 0
    product_map = defaultdict(lambda: {"name": "", "price_som": 0, "qty_sold": 0, "revenue": 0})
    for req in approved_requests:
        if not req.product_id:
            continue
        revenue = (req.product.narx_som or 0) * (req.qty or 0)
        total_qty += req.qty or 0
        total_sale_rev += revenue
        bucket = product_map[req.product_id]
        bucket["name"] = req.product.nom
        bucket["price_som"] = req.product.narx_som or 0
        bucket["qty_sold"] += req.qty or 0
        bucket["revenue"] += revenue

    if not total_sale_count:
        sale_qs = Sale.objects.filter(
            Q(center=center) | Q(product__center=center),
            sana__date__range=(d_from, d_to),
        ).select_related("product")
        total_sale_count = sale_qs.count()
        for sale in sale_qs:
            if not sale.product_id:
                continue
            price_som = sale.narx_som or sale.product.narx_som or 0
            revenue = price_som * (sale.qty or 0)
            total_qty += sale.qty or 0
            total_sale_rev += revenue
            bucket = product_map[sale.product_id]
            bucket["name"] = sale.product.nom
            bucket["price_som"] = price_som
            bucket["qty_sold"] += sale.qty or 0
            bucket["revenue"] += revenue

    product_list = list(product_map.values())
    product_list.sort(key=lambda row: (-row["revenue"], -row["qty_sold"], row["name"]))
    top8 = product_list[:8]

    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    prev_requests = PurchaseRequest.objects.filter(
        center=center,
        status=PurchaseRequest.APPROVED,
        sana__date__range=(prev_from, prev_to),
    ).select_related("product")
    prev_rev = sum((req.product.narx_som or 0) * (req.qty or 0) for req in prev_requests if req.product_id)

    return {
        "kpis": {
            "total_products": total_products,
            "total_sale_count": total_sale_count,
            "total_sale_rev": int(total_sale_rev),
            "total_qty": int(total_qty),
            "changes": {
                "total_sale_rev": _pct_change(total_sale_rev, prev_rev),
            },
        },
        "charts": {
            "p_names": [row["name"] for row in top8],
            "p_revs": [row["revenue"] for row in top8],
            "p_qty": [row["qty_sold"] for row in top8],
        },
        "product_list": product_list[:12],
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _analytics_payload(center, d_from, d_to):
    period = _period_stats(d_from, d_to)
    today = timezone.localdate()
    all_users = User.objects.filter(center=center)
    total_users = all_users.count()
    active_today = all_users.filter(last_login__date=today).count()
    active_week = all_users.filter(last_login__date__gte=today - timedelta(days=6)).count()
    active_month = all_users.filter(last_login__date__gte=today - timedelta(days=29)).count()

    m_labels, m_new, m_act = [], [], []
    for ms, me, lbl in _six_month_range(d_to):
        m_labels.append(lbl)
        m_new.append(all_users.filter(date_joined__date__range=(ms, me)).count())
        m_act.append(all_users.filter(last_login__date__range=(ms, me)).count())

    role_map = {
        "director": "Direktor",
        "manager": "Manager",
        "teacher": "O'qituvchi",
        "student": "O'quvchi",
        "parent": "Ota-ona",
    }
    role_dist = list(all_users.values("role").annotate(cnt=Count("id")).order_by("-cnt"))
    prev_from = period["prev_from"]
    prev_to = period["prev_to"]
    new_users = all_users.filter(date_joined__date__range=(d_from, d_to)).count()
    prev_new_users = all_users.filter(date_joined__date__range=(prev_from, prev_to)).count()

    return {
        "kpis": {
            "total_users": total_users,
            "active_today": active_today,
            "active_week": active_week,
            "active_month": active_month,
            "students": all_users.filter(role="student", is_archived=False).count(),
            "teachers": all_users.filter(role="teacher").count(),
            "managers": all_users.filter(role="manager").count(),
            "changes": {
                "new_users": _pct_change(new_users, prev_new_users),
            },
        },
        "charts": {
            "m_labels": m_labels,
            "m_new": m_new,
            "m_act": m_act,
            "role_labels": [role_map.get(row["role"], row["role"]) for row in role_dist],
            "role_counts": [row["cnt"] for row in role_dist],
        },
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
            "prev_from": str(prev_from),
            "prev_to": str(prev_to),
        },
    }


def _overview_headline(financial, students, billing, marketing):
    revenue_change = financial["kpis"]["changes"]["revenue"]
    attendance = students["kpis"]["avg_att_rate"]
    debt = billing["kpis"]["total_debt"]
    conv_rate = marketing["kpis"]["conv_rate"]
    if revenue_change is not None and revenue_change > 0 and attendance >= 85:
        return "Daromad o'smoqda, davomat barqaror. Hozir o'sishni ushlab qolish uchun qarzdorlikni bosib turish kerak."
    if debt > financial["kpis"]["revenue"] * 0.35:
        return "Qarzdorlik darajasi yuqori. Birinchi navbatda to'lov intizomi va undirish oqimini kuchaytirish kerak."
    if conv_rate < 35:
        return "Lead oqimi bor, lekin konversiya past. Trial va follow-up sifati direktor uchun asosiy nazorat nuqtasi bo'lib turibdi."
    return "Asosiy bloklar muvozanatda. Daromad, davomat va lead sifati bo'yicha joriy davrni davomiy nazorat qilish kifoya."


def _overview_payload(center, d_from, d_to):
    financial = _financial_payload(center, d_from, d_to)
    students = _student_payload(center, d_from, d_to)
    teachers = _teacher_payload(center, d_from, d_to)
    groups = _groups_payload(center, d_from, d_to)
    billing = _billing_payload(center, d_from, d_to)
    marketing = _marketing_payload(center, d_from, d_to)
    inventory = _inventory_payload(center, d_from, d_to)
    analytics = _analytics_payload(center, d_from, d_to)

    return {
        "summary": {
            "headline": _overview_headline(financial, students, billing, marketing),
            "cards": {
                "revenue": {
                    "value": financial["kpis"]["revenue"],
                    "change": financial["kpis"]["changes"]["revenue"],
                    "meta": f"{financial['kpis']['pay_count']} ta to'lov",
                },
                "profit": {
                    "value": financial["kpis"]["net_profit"],
                    "change": financial["kpis"]["changes"]["net_profit"],
                    "meta": f"Marja {financial['kpis']['profit_margin']}%",
                },
                "active_students": {
                    "value": students["kpis"]["active_count"],
                    "change": students["kpis"]["changes"]["new_students"],
                    "meta": f"Yangi {students['kpis']['new_students']} ta",
                },
                "attendance": {
                    "value": students["kpis"]["avg_att_rate"],
                    "change": students["kpis"]["changes"]["avg_att_rate"],
                    "meta": f"Risk {students['kpis']['churn_risk']} ta",
                },
                "debt": {
                    "value": billing["kpis"]["total_debt"],
                    "change": billing["kpis"]["changes"].get("total_debt"),
                    "meta": f"Qarzdorlar {billing['kpis']['total_debtors']} ta",
                },
                "leads": {
                    "value": marketing["kpis"]["total_leads"],
                    "change": marketing["kpis"]["leads_growth"],
                    "meta": f"Konversiya {marketing['kpis']['conv_rate']}%",
                },
            },
        },
        "period": financial["period"],
        "fin": financial,
        "st": students,
        "te": teachers,
        "gr": groups,
        "bi": billing,
        "mk": marketing,
        "om": inventory,
        "an": analytics,
    }


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

    data = _financial_payload(center, d_from, d_to)
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

    data = _student_payload(center, d_from, d_to)
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

    data = _teacher_payload(center, d_from, d_to)
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

    data = _groups_payload(center, d_from, d_to)
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

    data = _billing_payload(center, d_from, d_to)
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

    data = _marketing_payload(center, d_from, d_to)
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

    data = _inventory_payload(center, d_from, d_to)
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

    data = _analytics_payload(center, d_from, d_to)
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
    d_from, d_to = _parse_dates(request)
    return render(request, "core/dashboards/overview.html", {
        "center": center,
        "page_title": "Direktor Paneli",
        "active_dash": "overview",
        "date_from": d_from,
        "date_to": d_to,
    })


@login_required
def overview_api(request):
    center = _get_center(request)
    if not center:
        return _403()

    d_from, d_to = _parse_dates(request)
    ck = f"dash_overview:{center.id}:{d_from}:{d_to}"
    if (hit := cache.get(ck)):
        return JsonResponse(hit)

    data = _overview_payload(center, d_from, d_to)
    cache.set(ck, data, 300)
    return JsonResponse(data)


# ══════════════════════════════════════════════════════════════════
#  DIRECTOR BOSHQARUV — Yangi asosiy dashboard (noldan)
# ══════════════════════════════════════════════════════════════════

def _month_range_list(anchor, n=12):
    """anchor sanasidan orqaga n ta oy qaytaradi: [(m_start, m_end, label), ...]"""
    result = []
    for i in range(n - 1, -1, -1):
        raw = anchor.replace(day=1)
        for _ in range(i):
            raw = (raw.replace(day=1) - timedelta(days=1)).replace(day=1)
        m_start = raw.replace(day=1)
        m_end = m_start.replace(day=calendar.monthrange(m_start.year, m_start.month)[1])
        result.append((m_start, m_end, UZ_MONTHS[m_start.month]))
    return result


def _payments_for_scope(center, branch=None):
    qs = _payments_for_center(center)
    if branch:
        qs = qs.filter(group__branch=branch)
    return qs


def _payment_allocations_for_scope(center, branch=None):
    qs = _payment_allocations_for_center(center)
    if branch:
        qs = qs.filter(payment__group__branch=branch)
    return qs


def _deleted_payments_for_scope(center, branch=None):
    qs = _deleted_payments_for_center(center)
    if branch:
        qs = qs.filter(group__branch=branch)
    return qs


def _deleted_payment_allocations_for_scope(center, branch=None):
    qs = _deleted_payment_allocations_for_center(center)
    if branch:
        qs = qs.filter(payment__group__branch=branch)
    return qs


def _monthly_turnover_for_scope(center, m_start, m_end, branch=None):
    allocated_total = int(
        _payment_allocations_for_scope(center, branch)
        .filter(tuition_month__month__range=(m_start, m_end))
        .aggregate(s=Sum("amount"))["s"] or 0
    )
    unallocated_total = int(
        _payments_for_scope(center, branch)
        .filter(paid_date__range=(m_start, m_end), allocations__isnull=True)
        .aggregate(s=Sum("summa"))["s"] or 0
    )
    active_total = allocated_total + unallocated_total
    if active_total:
        return active_total

    if branch is None:
        snapshot = _monthly_snapshot_for_center(center, m_start)
        if snapshot and snapshot.total_income:
            return int(snapshot.total_income or 0)

    deleted_allocated_total = int(
        _deleted_payment_allocations_for_scope(center, branch)
        .filter(tuition_month__month__range=(m_start, m_end))
        .aggregate(s=Sum("amount"))["s"] or 0
    )
    deleted_unallocated_total = int(
        _deleted_payments_for_scope(center, branch)
        .filter(paid_date__range=(m_start, m_end), allocations__isnull=True)
        .aggregate(s=Sum("summa"))["s"] or 0
    )
    return deleted_allocated_total + deleted_unallocated_total


def _boshqaruv_payload(center, d_from, d_to, branch=None):
    """Boshqaruv dashboard uchun barcha ma'lumotlar."""
    today = timezone.localdate()
    present_filter = _attendance_present_filter()

    # ── O'quvchilar ────────────────────────────────────────────
    students_qs = User.objects.filter(center=center, role="student", is_archived=False)
    students_history_qs = User.all_objects.filter(center=center, role="student")
    active_enroll = Enrollment.objects.filter(
        group__center=center,
        is_active=True,
        student__is_archived=False,
    )
    if branch:
        students_qs = students_qs.filter(enrollments__group__branch=branch).distinct()
        students_history_qs = students_history_qs.filter(enrollments__group__branch=branch).distinct()
        active_enroll = active_enroll.filter(group__branch=branch)

    total_students = students_qs.count()
    active_students = active_enroll.values("student").distinct().count()
    new_this_month = students_qs.filter(date_joined__date__range=(d_from, d_to)).count()

    # ── Daromad ────────────────────────────────────────────────
    pay_qs = _payments_for_scope(center, branch).filter(paid_date__range=(d_from, d_to))
    revenue = int(pay_qs.aggregate(s=Sum("summa"))["s"] or 0)
    pay_count = pay_qs.count()

    exp_qs = _expenses_for_center(center).filter(sana__date__range=(d_from, d_to))
    expenses = int(exp_qs.aggregate(s=Sum("summa"))["s"] or 0)
    net_profit = revenue - expenses

    # Oldingi davr
    period = _period_stats(d_from, d_to)
    prev_rev = int(
        _payments_for_scope(center, branch).filter(
            paid_date__range=(period["prev_from"], period["prev_to"])
        ).aggregate(s=Sum("summa"))["s"] or 0
    )
    prev_students = students_qs.filter(
        date_joined__date__range=(period["prev_from"], period["prev_to"])
    ).count()

    # ── Guruhlar ───────────────────────────────────────────────
    groups_qs = Group.objects.filter(center=center, is_archived=False)
    if branch:
        groups_qs = groups_qs.filter(branch=branch)
    total_groups = groups_qs.count()
    active_groups = groups_qs.filter(is_closed=False).count()

    # ── Davomat ────────────────────────────────────────────────
    att_qs = Attendance.objects.filter(group__center=center, date__range=(d_from, d_to))
    if branch:
        att_qs = att_qs.filter(group__branch=branch)
    att_total = att_qs.count()
    att_present = att_qs.filter(present_filter).count()
    avg_attendance = round(att_present / att_total * 100, 1) if att_total else 0

    # ── O'qituvchilar va Managerlar ────────────────────────────
    teachers_qs = User.objects.filter(center=center, role="teacher", is_archived=False)
    if branch:
        teachers_qs = teachers_qs.filter(group__branch=branch).distinct()
    teachers_count = teachers_qs.count()
    managers_count = User.objects.filter(center=center, role="manager", is_archived=False).count()

    # ── Lidlar ─────────────────────────────────────────────────
    converted_filter = Q(converted_to_student=True) | Q(converted_user__isnull=False)
    leads_qs = Lead.objects.filter(center=center, qoshilgan_sana__date__range=(d_from, d_to))
    total_leads = leads_qs.count()
    converted_leads = leads_qs.filter(converted_filter).count()
    conv_rate = round(converted_leads / total_leads * 100, 1) if total_leads else 0

    # ── Chart 1 & 2: 12 oylik moliyaviy + o'quvchilar ──────────
    # Doim today dan orqaga 12 oy — filter d_from/d_to faqat KPI ga ta'sir qiladi
    monthly_labels   = []
    monthly_turnover = []   # Umumiy aylanma  = barcha kirim to'lovlar
    monthly_expenses = []   # Qarzdorlik/chiqim = barcha xarajatlar
    monthly_profit   = []   # Sof foyda = aylanma - xarajat
    monthly_students = []   # Yangi kelgan o'quvchilar
    monthly_left     = []   # Markazni tark etgan o'quvchilar

    for ms, me, lbl in _month_range_list(today, 12):
        monthly_labels.append(lbl)

        # Umumiy aylanma — o'sha oyda qabul qilingan barcha to'lovlar
        m_turn = _monthly_turnover_for_scope(center, ms, me, branch)
        monthly_turnover.append(m_turn)

        # Xarajatlar — o'qituvchi maoshi, ijara, boshqa chiqimlar
        m_exp = _monthly_expenses_for_center(center, ms, me)
        monthly_expenses.append(m_exp)

        # Sof foyda — markazda qoladigan
        monthly_profit.append(m_turn - m_exp)

        # Yangi kelgan o'quvchilar
        monthly_students.append(
            students_history_qs.filter(date_joined__date__range=(ms, me)).count()
        )

        # Markazni tark etgan o'quvchilar — arxiv yoki soft delete qilingan studentlar.
        # Legacy arxivlangan userlarda archived_at bo'sh bo'lishi mumkin; ularni joriy oyga qo'shamiz.
        left_filter = Q(archived_at__date__range=(ms, me)) | Q(deleted_at__date__range=(ms, me))
        if ms.year == today.year and ms.month == today.month:
            left_filter |= Q(is_archived=True, archived_at__isnull=True)
        monthly_left.append(
            students_history_qs.filter(left_filter).count()
        )

    # ── Chart 3: Guruh to'ldirilganlik ─────────────────────────
    group_fill = []
    for g in groups_qs.filter(is_closed=False).select_related("oqituvchi"):
        enrolled = Enrollment.objects.filter(group=g, is_active=True).count()
        group_fill.append({"name": g.nom, "enrolled": enrolled})
    group_fill.sort(key=lambda x: -x["enrolled"])

    # ── Chart 4: Guruhlar davomat ranking ────────────────────────
    grp_att_rows = list(
        Attendance.objects.filter(
            group__center=center,
            date__range=(d_from, d_to),
            group__is_archived=False,
            **({"group__branch": branch} if branch else {}),
        )
        .values("group__nom")
        .annotate(
            tot=Count("id"),
            pres=Count("id", filter=present_filter),
        )
        .order_by("-tot")
    )
    grp_att_ranking = []
    for row in grp_att_rows:
        if not row["tot"]:
            continue
        rate = round(row["pres"] / row["tot"] * 100, 1)
        grp_att_ranking.append({
            "name": row["group__nom"] or "Guruh",
            "rate": rate,
            "present": row["pres"],
            "total": row["tot"],
        })
    # davomat foizi bo'yicha saralash (pasayish tartibida)
    grp_att_ranking.sort(key=lambda x: -x["rate"])
    grp_att_ranking = grp_att_ranking[:12]

    # ── Chart 5: Lid voronkasi ─────────────────────────────────
    # LeadStatus.code maydoni ishlatiladi (kod emas)
    all_leads_center = Lead.objects.filter(center=center)
    funnel_new        = all_leads_center.filter(status__code="new").count()
    funnel_contacted  = all_leads_center.filter(status__code="contacted").count()
    funnel_trial      = all_leads_center.filter(status__code="trial_scheduled").count()
    funnel_registered = all_leads_center.filter(status__code="registered").count()
    # Agar status kodlari boshqacha bo'lsa — jami lidlarni taqsimlaymiz
    if funnel_new == 0 and funnel_contacted == 0:
        total_all = all_leads_center.count()
        converted_all = all_leads_center.filter(converted_filter).count()
        funnel_new        = total_all
        funnel_contacted  = int(total_all * 0.6)
        funnel_trial      = int(total_all * 0.35)
        funnel_registered = converted_all

    source_rows = list(
        all_leads_center.filter(converted_filter)
        .values("manba__nom")
        .annotate(cnt=Count("id"))
        .order_by("-cnt", "manba__nom")[:5]
    )
    source_labels = [row["manba__nom"] or "Noma'lum" for row in source_rows]
    source_counts = [int(row["cnt"] or 0) for row in source_rows]

    # ── Chart 6: Kategoriya taqsimoti (1-donut uchun) ─────────
    cat_dist = list(
        active_enroll.values("group__category_obj__name")
        .annotate(cnt=Count("student", distinct=True))
        .order_by("-cnt")[:6]
    )
    if not cat_dist:
        cat_dist = list(
            active_enroll.values("group__category")
            .annotate(cnt=Count("student", distinct=True))
            .order_by("-cnt")[:6]
        )
        cat_labels = [r.get("group__category") or "Boshqa" for r in cat_dist]
        cat_counts = [r["cnt"] for r in cat_dist]
    else:
        cat_labels = [r["group__category_obj__name"] or "Boshqa" for r in cat_dist]
        cat_counts = [r["cnt"] for r in cat_dist]

    if not cat_labels:
        cat_labels = ["IT", "Til kurslari"]
        cat_counts = [active_students // 2, active_students - active_students // 2]

    # ── Chart 7: To'lov holati (2-donut + kategoriya breakdown) ─────────
    # UI soddalashtirilgan ko'rinish uchun qisman to'lov ham "to'lamagan" safiga qo'shiladi.
    pay_toliq = pay_tolamagan = 0
    pay_category_map = {}
    enrollments_all = list(
        active_enroll.select_related("group", "group__category_obj", "student")
    )
    student_group_pairs = [
        (e.student_id, e.group_id, e.kurs_narhi or e.group.kurs_narxi or 0)
        for e in enrollments_all
    ]

    # Joriy oy uchun to'lovlarni batch olamiz
    from django.db.models import Sum as _Sum
    pay_map = {}
    if student_group_pairs:
        pay_rows = list(
            _payments_for_scope(center, branch).filter(
                paid_date__range=(d_from, d_to),
            )
            .values("student_id", "group_id")
            .annotate(total=_Sum("summa"))
        )
        for row in pay_rows:
            pay_map[(row["student_id"], row["group_id"])] = int(row["total"] or 0)

    for enr in enrollments_all:
        student_id = enr.student_id
        group_id = enr.group_id
        fee = enr.kurs_narhi or enr.group.kurs_narxi or 0
        if fee <= 0:
            continue
        paid = pay_map.get((student_id, group_id), 0)
        category_name = (
            getattr(getattr(enr.group, "category_obj", None), "name", None)
            or enr.group.get_category_display()
            or "Boshqa"
        )
        bucket = pay_category_map.setdefault(category_name, {
            "name": category_name,
            "total": 0,
            "paid": 0,
            "unpaid": 0,
        })
        bucket["total"] += 1
        if paid >= fee:
            pay_toliq += 1
            bucket["paid"] += 1
        else:
            pay_tolamagan += 1
            bucket["unpaid"] += 1

    pay_category_breakdown = []
    for row in pay_category_map.values():
        total = int(row["total"] or 0)
        paid = int(row["paid"] or 0)
        unpaid = int(row["unpaid"] or 0)
        pay_category_breakdown.append({
            "name": row["name"],
            "total": total,
            "paid": paid,
            "unpaid": unpaid,
            "paid_percent": round(paid / total * 100, 1) if total else 0,
            "unpaid_percent": round(unpaid / total * 100, 1) if total else 0,
        })
    pay_category_breakdown.sort(key=lambda x: (-x["total"], x["name"]))

    # ── Top 5 guruh ────────────────────────────────────────────
    top_groups = []
    for g in groups_qs.filter(is_closed=False).select_related("oqituvchi").order_by("-id")[:5]:
        enrolled = Enrollment.objects.filter(group=g, is_active=True).count()
        g_att_tot = Attendance.objects.filter(group=g, date__range=(d_from, d_to)).count()
        g_att_pre = Attendance.objects.filter(
            group=g, date__range=(d_from, d_to)
        ).filter(present_filter).count()
        top_groups.append({
            "name": g.nom,
            "teacher": f"{g.oqituvchi.ism} {g.oqituvchi.familya}" if g.oqituvchi else "—",
            "enrolled": enrolled,
            "att_rate": round(g_att_pre / g_att_tot * 100, 1) if g_att_tot else 0,
        })

    # ── Top 5 o'quvchi ────────────────────────────────────────
    raw_att = list(
        att_qs.values("student__ism", "student__familya")
        .annotate(tot=Count("id"), pres=Count("id", filter=present_filter))
    )
    top_students = sorted(
        [
            {
                "name": f"{r['student__ism'] or ''} {r['student__familya'] or ''}".strip() or "Noma'lum",
                "rate": round(r["pres"] / r["tot"] * 100, 1) if r["tot"] else 0,
            }
            for r in raw_att
        ],
        key=lambda x: -x["rate"],
    )[:5]

    # ── Xavfli o'quvchilar (oxirgi 30 kun, 3+ dars qoldirgan) ────
    xavfli_students = []
    try:
        absent_filter = Q(status__in=["absent_excused", "absent_unexcused"]) | Q(present=False, forced=False)
        thirty_ago = today - timedelta(days=30)
        xavfli_raw = list(
            Attendance.objects.filter(
                group__center=center,
                date__range=(thirty_ago, today),
                **({"group__branch": branch} if branch else {}),
            )
            .filter(absent_filter)
            .values(
                "student_id",
                "student__ism",
                "student__familya",
                "student__telefon1",
                "group__nom",
            )
            .annotate(missed=Count("id"))
            .filter(missed__gte=3)
            .order_by("-missed")
        )
        # group by student — agar bir o'quvchi bir nechta guruhda bo'lsa birlashtiramiz
        _st_map = {}
        for row in xavfli_raw:
            sid = row["student_id"]
            if sid not in _st_map:
                _st_map[sid] = {
                    "name": f"{row['student__ism'] or ''} {row['student__familya'] or ''}".strip() or "Noma'lum",
                    "phone": row["student__telefon1"] or "—",
                    "groups": [],
                    "missed": 0,
                }
            _st_map[sid]["groups"].append(row["group__nom"] or "Guruh")
            _st_map[sid]["missed"] += row["missed"]

        # har bir student uchun jami davomatni hisoblash (foiz uchun)
        if _st_map:
            xavfli_att_raw = list(
                Attendance.objects.filter(
                    group__center=center,
                    date__range=(thirty_ago, today),
                    student_id__in=list(_st_map.keys()),
                    **({"group__branch": branch} if branch else {}),
                )
                .values("student_id")
                .annotate(
                    tot=Count("id"),
                    pres=Count("id", filter=present_filter),
                )
            )
            _att_map = {r["student_id"]: r for r in xavfli_att_raw}
        else:
            _att_map = {}

        for sid, info in _st_map.items():
            att_info = _att_map.get(sid, {})
            tot = att_info.get("tot", 0)
            pres = att_info.get("pres", 0)
            rate = round(pres / tot * 100, 1) if tot else 0
            xavfli_students.append({
                "name": info["name"],
                "phone": info["phone"],
                "groups": ", ".join(info["groups"]),
                "missed": info["missed"],
                "rate": rate,
            })
        xavfli_students.sort(key=lambda x: (-x["missed"], x["rate"]))
        xavfli_students = xavfli_students[:20]
    except Exception:
        xavfli_students = []

    return {
        "kpis": {
            "total_students": total_students,
            "active_students": active_students,
            "new_this_month": new_this_month,
            "revenue": revenue,
            "net_profit": net_profit,
            "expenses": expenses,
            "pay_count": pay_count,
            "total_groups": total_groups,
            "active_groups": active_groups,
            "avg_attendance": avg_attendance,
            "teachers_count": teachers_count,
            "managers_count": managers_count,
            "total_leads": total_leads,
            "conv_rate": conv_rate,
            "changes": {
                "revenue": _pct_change(revenue, prev_rev),
                "students": _pct_change(new_this_month, prev_students),
            },
        },
        "charts": {
            "monthly_labels": monthly_labels,
            "monthly_turnover": monthly_turnover,
            "monthly_expenses": monthly_expenses,
            "monthly_profit": monthly_profit,
            "monthly_students": monthly_students,
            "monthly_left": monthly_left,
            "group_names": [g["name"] for g in group_fill[:8]],
            "group_enrolled": [g["enrolled"] for g in group_fill[:8]],
            "grp_att_ranking": grp_att_ranking,
            "funnel": [funnel_new, funnel_contacted, funnel_trial, funnel_registered],
            "source_labels": source_labels,
            "source_counts": source_counts,
            "cat_labels": cat_labels,
            "cat_counts": cat_counts,
            "pay_status_labels": ["To'lagan", "To'lamagan"],
            "pay_status_counts": [pay_toliq, pay_tolamagan],
            "pay_category_breakdown": pay_category_breakdown,
        },
        "group_fill_all": group_fill,
        "top_groups": top_groups,
        "top_students": top_students,
        "xavfli_students": xavfli_students,
        "period": {
            "from": str(d_from),
            "to": str(d_to),
            "days": period["days"],
        },
    }


@login_required
def director_boshqaruv(request):
    center = _get_center(request)
    if not center:
        return redirect("core:home")
    d_from, d_to = _parse_dates(request)
    return render(request, "core/dashboards/boshqaruv.html", {
        "center": center,
        "date_from": d_from,
        "date_to": d_to,
    })


@login_required
def director_boshqaruv_api(request):
    center = _get_center(request)
    if not center:
        return _403()
    d_from, d_to = _parse_dates(request)
    branch_id = request.GET.get("branch_id")
    branch = None
    if branch_id:
        try:
            branch = Branch.objects.get(pk=int(branch_id), center=center)
        except (Branch.DoesNotExist, ValueError, TypeError):
            branch = None
    data = _boshqaruv_payload(center, d_from, d_to, branch=branch)
    return JsonResponse(data)


# ── AI CHAT ──────────────────────────────────────────────────────

import json as _json

@login_required
def director_boshqaruv_chat(request):
    """AI chat endpoint — POST {question, history[]}"""
    if request.method != "POST":
        return JsonResponse({"error": "Faqat POST"}, status=405)

    center = _get_center(request)
    if not center:
        return _403()

    try:
        body = _json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON xato"}, status=400)

    question = (body.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "Savol bo'sh"}, status=400)

    history = body.get("history") or []

    # Oddiy stats ni olish (har doim fresh)
    today = timezone.localdate()
    d_from = today.replace(day=1)
    stats = _boshqaruv_payload(center, d_from, today)

    # Gemini ga yuborish
    try:
        from core.services.ai_insights import answer_question_structured_bundle
        answer, source, _ = answer_question_structured_bundle(
            center=center,
            question=question,
            stats=stats,
            history=history,
            viewer=request.user,
        )
    except Exception as e:
        answer = f"Hozircha AI javob bera olmayapti. Xato: {str(e)[:120]}"
        source = "error"

    return JsonResponse({"answer": answer, "source": source})
