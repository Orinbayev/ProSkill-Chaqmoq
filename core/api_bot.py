from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import timedelta
from functools import wraps

from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts.api_auth import _require_api_secret
from accounts.models import User
from chaqmoq.models import Ledger
from core.models import ChurnRisk, NotificationPreference
from education.models import (
    Attendance,
    CertificateRecord,
    Enrollment,
    Group,
    Payment,
    SalaryPayout,
    TuitionMonth,
)
from education.services.attendance_service import toggle_attendance
from education.services.expected_income_service import calculate_expected_income
from education.services.ranking_service import build_group_internal_ranking
from store.models import Expense, Lead, Product, PurchaseRequest

logger = logging.getLogger(__name__)

PRESENT_FILTER = Q(status="present") | Q(present=True) | Q(forced=True)


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def _safe_api(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception:
            logger.exception("Bot API xatosi: %s", view_func.__name__)
            return _json_error("Ichki xatolik yuz berdi", status=500)

    return wrapper


def _parse_json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}


def _money(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_money(value) -> str:
    return f"{_money(value):,}".replace(",", " ")


def _fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        return value.strftime("%d.%m.%Y")
    except Exception:
        return str(value)


def _notification_enabled(user: User) -> bool:
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return all([
        pref.receive_coin,
        pref.receive_broadcast,
        pref.receive_purchase,
        pref.receive_system,
    ])


def _linked_user(request, *, allowed_roles: tuple[str, ...] | None = None) -> User | None:
    tg_id = str(request.GET.get("telegram_id") or request.POST.get("telegram_id") or "").strip()
    email = str(request.GET.get("email") or request.POST.get("email") or "").strip()
    return _linked_user_from_values(tg_id=tg_id, email=email, allowed_roles=allowed_roles)


def _linked_user_from_values(*, tg_id: str, email: str = "", allowed_roles: tuple[str, ...] | None = None) -> User | None:
    if not tg_id:
        return None

    qs = User.objects.filter(
        telegram_id=tg_id,
        is_telegram_linked=True,
    ).select_related("center")
    if email:
        qs = qs.filter(email=email)
    elif allowed_roles:
        qs = qs.filter(Q(role__in=allowed_roles) | Q(is_superuser=True))

    user = qs.first()
    if not user:
        return None
    if allowed_roles and not user.is_superuser and user.role not in allowed_roles:
        return None
    return user


def _present_status_label(status: str) -> str:
    mapping = {
        "present": "Keldi",
        "absent": "Kelmadi",
        "absent_excused": "Sababli kelmadi",
        "absent_unexcused": "Kelmadi",
        "none": "Belgilanmagan",
    }
    return mapping.get(status or "none", status or "Belgilanmagan")


def _resolve_center(user: User):
    return getattr(user, "center", None)


def _student_debt_breakdown(student: User, center) -> tuple[int, list[dict]]:
    current_month = timezone.localdate().replace(day=1)
    enrollments = (
        Enrollment.objects.filter(student=student, group__center=center)
        .select_related("group")
        .prefetch_related("tuition_months__allocations")
        .order_by("group__nom")
    )

    total = 0
    items: list[dict] = []
    for enrollment in enrollments:
        tuition = enrollment.tuition_months.filter(month=current_month).first()
        fee = _money(tuition.fee_amount) if tuition else _money(enrollment.kurs_narhi)
        paid = 0
        if tuition:
            paid = _money(tuition.allocations.aggregate(total=Sum("amount"))["total"])
        elif enrollment.is_active:
            paid = _money(enrollment.jami_tolangan)
        debt = max(0, fee - paid)
        total += debt
        items.append(
            {
                "group_id": enrollment.group_id,
                "group_name": enrollment.group.nom,
                "fee": fee,
                "paid": paid,
                "debt": debt,
                "is_active": bool(enrollment.is_active),
            }
        )
    return total, items


def _student_last_payment(student: User, center):
    return (
        Payment.objects.filter(student=student, center=center)
        .select_related("group")
        .order_by("-paid_date", "-id")
        .first()
    )


def _student_payments(student: User, center, limit: int = 5) -> list[dict]:
    payments = (
        Payment.objects.filter(student=student, center=center)
        .select_related("group")
        .order_by("-paid_date", "-id")[:limit]
    )
    return [
        {
            "id": payment.id,
            "group_name": payment.group.nom if payment.group else "—",
            "amount": _money(payment.summa),
            "paid_date": _fmt_date(payment.paid_date),
            "payment_type": payment.payment_type,
            "note": payment.note or "",
        }
        for payment in payments
    ]


def _student_attendance_payload(student: User, center, *, days: int = 30) -> dict:
    start_date = timezone.localdate() - timedelta(days=max(0, days - 1))
    qs = (
        Attendance.objects.filter(student=student)
        .filter(Q(center=center) | Q(group__center=center))
        .select_related("group")
        .order_by("-date", "-id")
    )
    recent_qs = qs.filter(date__gte=start_date)
    total = recent_qs.count()
    present = recent_qs.filter(PRESENT_FILTER).count()
    all_total = qs.count()
    all_present = qs.filter(PRESENT_FILTER).count()
    return {
        "recent_total": total,
        "recent_present": present,
        "recent_rate": round((present / total) * 100, 1) if total else 0,
        "total_lessons": all_total,
        "present_lessons": all_present,
        "attendance_rate": round((all_present / all_total) * 100, 1) if all_total else 0,
        "items": [
            {
                "date": _fmt_date(item.date),
                "group_name": item.group.nom if item.group else "—",
                "status": item.status or ("present" if item.present else "absent_unexcused"),
                "status_label": _present_status_label(item.status or ("present" if item.present else "absent_unexcused")),
            }
            for item in recent_qs[:30]
        ],
    }


def _student_active_enrollments(student: User, center):
    return (
        Enrollment.objects.filter(student=student, group__center=center, is_active=True)
        .select_related("group", "group__oqituvchi")
        .order_by("group__nom")
    )


def _group_schedule_items(student: User, center) -> list[dict]:
    items: list[dict] = []
    for enrollment in _student_active_enrollments(student, center):
        group = enrollment.group
        teacher = getattr(group, "oqituvchi", None)
        items.append(
            {
                "group_id": group.id,
                "group_name": group.nom,
                "teacher_name": teacher.get_full_name() if teacher else "Belgilanmagan",
                "teacher_phone": teacher.telefon1 or teacher.phone_number if teacher else "",
                "lessons_per_week": group.lessons_per_week or 0,
                "weekday_label": f"Haftasiga {group.lessons_per_week or 0} marta",
                "time_label": "Vaqt kiritilmagan",
                "estimated_end_date": _fmt_date(group.estimated_end_date),
            }
        )
    return items


def _fallback_group_ranking(group: Group, student: User) -> dict:
    student_ids = list(
        Enrollment.objects.filter(group=group, is_active=True)
        .values_list("student_id", flat=True)
        .distinct()
    )
    students = list(
        User.objects.filter(id__in=student_ids)
        .order_by("-chaqmoq", "ism", "familya", "id")
        .only("id", "ism", "familya", "chaqmoq")
    )
    top = []
    position = None
    for index, item in enumerate(students, start=1):
        if item.id == student.id:
            position = index
        if index <= 5:
            top.append(
                {
                    "position": index,
                    "student_id": item.id,
                    "full_name": item.get_full_name(),
                    "score": _money(item.chaqmoq),
                }
            )
    return {
        "group_id": group.id,
        "group_name": group.nom,
        "rank_position": position,
        "total_students": len(students),
        "top5": top,
    }


def _group_ranking_payload(group: Group, student: User) -> dict:
    try:
        rows = build_group_internal_ranking(group=group, on_date=timezone.localdate(), persist=False)
    except Exception:
        rows = []

    if not rows:
        return _fallback_group_ranking(group, student)

    top5 = []
    position = None
    for row in rows:
        rank_position = int(row.get("rank_position") or 0)
        row_student = row.get("student")
        student_id = getattr(row_student, "id", row.get("student_id"))
        if student_id == student.id:
            position = rank_position
        if rank_position <= 5:
            top5.append(
                {
                    "position": rank_position,
                    "student_id": student_id,
                    "full_name": row_student.get_full_name() if row_student else "—",
                    "score": float(row.get("total_internal_score") or 0),
                }
            )

    return {
        "group_id": group.id,
        "group_name": group.nom,
        "rank_position": position,
        "total_students": len(rows),
        "top5": top5,
    }


def _student_balance_payload(student: User, center) -> dict:
    balance = Ledger.student_balansi(student.id, center=center)
    first_enrollment = _student_active_enrollments(student, center).first()
    ranking = _group_ranking_payload(first_enrollment.group, student) if first_enrollment else {
        "group_id": None,
        "group_name": "Faol guruh yo'q",
        "rank_position": None,
        "total_students": 0,
        "top5": [],
    }
    return {
        "current_balance": balance,
        "group_ranking": ranking,
    }


def _student_store_payload(student: User, center) -> dict:
    products = (
        Product.objects.filter(center=center, is_deleted=False)
        .order_by("-yaratilgan")[:20]
    )
    purchase_requests = (
        PurchaseRequest.objects.filter(student=student, center=center)
        .select_related("product", "manager")
        .order_by("-sana")[:10]
    )
    return {
        "products": [
            {
                "id": product.id,
                "name": product.nom,
                "price_chaqmoq": _money(product.narx_chaqmoq),
                "price_som": _money(product.narx_som),
                "description": product.izoh or "",
            }
            for product in products
        ],
        "purchase_requests": [
            {
                "id": item.id,
                "product_name": item.product.nom if item.product else "Mahsulot o'chirilgan",
                "qty": item.qty,
                "status": item.status,
                "created_at": timezone.localtime(item.sana).strftime("%d.%m.%Y %H:%M"),
            }
            for item in purchase_requests
        ],
    }


def _student_dashboard(user: User, center) -> dict:
    debt_total, debt_items = _student_debt_breakdown(user, center)
    last_payment = _student_last_payment(user, center)
    attendance = _student_attendance_payload(user, center)
    balance = _student_balance_payload(user, center)
    schedule = _group_schedule_items(user, center)
    return {
        "status": {
            "attendance_rate": attendance["recent_rate"],
            "present_lessons": attendance["recent_present"],
            "total_lessons": attendance["recent_total"],
            "debt": debt_total,
            "active_groups": [item["group_name"] for item in schedule],
        },
        "balance": balance,
        "schedule": schedule,
        "payment": {
            "debt": debt_total,
            "payment_day": getattr(center, "payment_day", None),
            "last_payment_date": _fmt_date(getattr(last_payment, "paid_date", None)),
            "items": debt_items,
            "recent_payments": _student_payments(user, center),
        },
        "ranking": balance["group_ranking"],
        "store": _student_store_payload(user, center),
        "settings": {
            "notifications_enabled": _notification_enabled(user),
        },
        "attendance": attendance,
    }


def _teacher_contact_payload(student: User, center) -> dict:
    enrollment = _student_active_enrollments(student, center).first()
    teacher = getattr(getattr(enrollment, "group", None), "oqituvchi", None)
    return {
        "group_name": enrollment.group.nom if enrollment else "—",
        "teacher_name": teacher.get_full_name() if teacher else "Belgilanmagan",
        "teacher_phone": (teacher.telefon1 or teacher.phone_number) if teacher else "",
    }


def _parent_dashboard(parent: User, center, child_id: str | None = None) -> dict:
    children_qs = parent.children.filter(role="student").select_related("center").order_by("ism", "familya")
    if child_id:
        selected_child = get_object_or_404(children_qs, pk=child_id)
    else:
        selected_child = children_qs.first()

    children = []
    for child in children_qs:
        groups = [item["group_name"] for item in _group_schedule_items(child, center)]
        children.append(
            {
                "id": child.id,
                "full_name": child.get_full_name(),
                "groups": groups,
            }
        )

    child_payload = None
    if selected_child:
        student_dashboard = _student_dashboard(selected_child, center)
        child_payload = {
            "id": selected_child.id,
            "full_name": selected_child.get_full_name(),
            "attendance": student_dashboard["attendance"],
            "payment": student_dashboard["payment"],
            "balance": student_dashboard["balance"],
            "teacher": _teacher_contact_payload(selected_child, center),
        }

    return {
        "children": children,
        "selected_child_id": selected_child.id if selected_child else None,
        "child": child_payload,
    }


def _attendance_rate_for_group(group: Group, *, days: int = 30) -> float:
    start_date = timezone.localdate() - timedelta(days=max(0, days - 1))
    qs = Attendance.objects.filter(group=group, date__gte=start_date)
    total = qs.count()
    present = qs.filter(PRESENT_FILTER).count()
    return round((present / total) * 100, 1) if total else 0.0


def _teacher_group_list(teacher: User, center) -> list[dict]:
    groups = (
        Group.objects.filter(center=center, oqituvchi=teacher, is_archived=False)
        .order_by("nom")
    )
    today = timezone.localdate()
    return [
        {
            "id": group.id,
            "name": group.nom,
            "student_count": Enrollment.objects.filter(group=group, is_active=True).count(),
            "today_attendance_count": Attendance.objects.filter(group=group, date=today).count(),
            "average_attendance_rate": _attendance_rate_for_group(group),
        }
        for group in groups
    ]


def _teacher_attendance_sheet(group: Group, *, date_value=None) -> dict:
    date_value = date_value or timezone.localdate()
    enrollments = (
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    students = []
    for enrollment in enrollments:
        student = enrollment.student
        recent = _student_attendance_payload(student, group.center, days=30)
        attendance = Attendance.objects.filter(group=group, student=student, date=date_value).first()
        current_status = "none"
        if attendance:
            current_status = attendance.status or ("present" if attendance.present else "absent_unexcused")
        students.append(
            {
                "id": student.id,
                "full_name": student.get_full_name(),
                "attendance_rate": recent["recent_rate"],
                "today_status": current_status,
                "today_status_label": _present_status_label(current_status),
            }
        )

    return {
        "date": _fmt_date(date_value),
        "group": {
            "id": group.id,
            "name": group.nom,
        },
        "students": students,
    }


def _teacher_students_payload(group: Group) -> list[dict]:
    rows = []
    for enrollment in (
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    ):
        student = enrollment.student
        attendance = _student_attendance_payload(student, group.center, days=30)
        debt, _ = _student_debt_breakdown(student, group.center)
        rows.append(
            {
                "id": student.id,
                "full_name": student.get_full_name(),
                "attendance_rate": attendance["recent_rate"],
                "balance": Ledger.student_balansi(student.id, center=group.center),
                "debt": debt,
            }
        )
    return rows


def _teacher_real_income(teacher: User, center) -> dict:
    """
    Oyning 1-sanasidan BUGUNGA qadar o'qituvchining daromadini
    SAYT bilan bir xil formula bo'yicha hisoblaydi:
      daromad = round(kurs_narhi / oy_dars_soni * foiz / 100) * o'tilgan_darslar
    """
    today = timezone.localdate()
    month_start = today.replace(day=1)

    # O'qituvchining barcha faol guruhlari (kurs narxi va dars soni bilan)
    teacher_groups = list(
        Group.objects
        .filter(oqituvchi=teacher, center=center, is_archived=False)
        .order_by("nom")
    )
    group_ids = [g.id for g in teacher_groups]

    if not group_ids:
        return {
            "month_start": str(month_start),
            "today": str(today),
            "breakdown": [],
            "total_received": 0,
            "teacher_share": 0,
        }

    # Faol o'quvchilar soni (har bir guruh uchun)
    enrollment_counts = dict(
        Enrollment.objects
        .filter(group_id__in=group_ids, is_active=True)
        .values("group_id")
        .annotate(cnt=Count("student_id", distinct=True))
        .values_list("group_id", "cnt")
    )

    # Enrollment: har bir (group_id, student_id) uchun kurs_narhi va foiz
    # Barcha faol enrollmentlarni olamiz
    enrollments_qs = (
        Enrollment.objects
        .filter(group_id__in=group_ids, is_active=True)
        .values("group_id", "student_id", "kurs_narhi", "oqituvchi_foiz")
    )
    # enr_map[group_id][student_id] = (kurs_narhi, foiz)
    enr_map: dict[int, dict[int, tuple[int, int]]] = {}
    for e in enrollments_qs:
        gid = e["group_id"]
        sid = e["student_id"]
        foiz_enr = getattr(teacher, "oqituvchi_foizi", 0) or e["oqituvchi_foiz"] or 0
        enr_map.setdefault(gid, {})[sid] = (e["kurs_narhi"] or 0, foiz_enr)

    # Bu oy davomati: (group_id, student_id) → o'tilgan darslar soni
    att_qs = (
        Attendance.objects
        .filter(
            group_id__in=group_ids,
            date__gte=month_start,
            date__lte=today,
        )
        .filter(PRESENT_FILTER)
        .values("group_id", "student_id")
        .annotate(cnt=Count("id"))
    )
    # att_map[group_id][student_id] = cnt
    att_map: dict[int, dict[int, int]] = {}
    for row in att_qs:
        att_map.setdefault(row["group_id"], {})[row["student_id"]] = row["cnt"]

    # Guruh meta-ma'lumotlari
    group_meta = {g.id: g for g in teacher_groups}

    breakdown = []
    teacher_share_total = 0

    for g in teacher_groups:
        oy_dars_soni = g.oy_dars_soni or 12
        if oy_dars_soni <= 0:
            oy_dars_soni = 12

        group_teacher_total = 0
        g_atts = att_map.get(g.id, {})

        for sid, lessons in g_atts.items():
            kurs_narhi, foiz = enr_map.get(g.id, {}).get(sid, (0, 0))
            if kurs_narhi > 0 and foiz > 0:
                per_lesson = round((kurs_narhi / oy_dars_soni) * (foiz / 100))
                group_teacher_total += per_lesson * lessons

        students = enrollment_counts.get(g.id, 0)
        # Guruh foizi (display uchun)
        foiz_display = getattr(teacher, "oqituvchi_foizi", None) or g.oqituvchi_foiz or 40

        teacher_share_total += group_teacher_total
        breakdown.append({
            "group_name": g.nom,
            "students": students,
            "group_total": group_teacher_total,   # bu yerda faqat o'qituvchi ulushi
            "teacher_part": group_teacher_total,
            "foiz": foiz_display,
        })

    return {
        "month_start": str(month_start),
        "today": str(today),
        "breakdown": breakdown,
        "total_received": teacher_share_total,
        "teacher_share": teacher_share_total,
    }


def _teacher_dashboard(teacher: User, center, group_id: str | None = None) -> dict:
    groups = _teacher_group_list(teacher, center)
    selected_group = None
    if group_id:
        selected_group = get_object_or_404(Group, pk=group_id, center=center, oqituvchi=teacher, is_archived=False)
    elif groups:
        selected_group = Group.objects.filter(pk=groups[0]["id"]).first()

    all_group_ids = [item["id"] for item in groups]
    all_attendance = Attendance.objects.filter(group_id__in=all_group_ids)
    all_total = all_attendance.count()
    all_present = all_attendance.filter(PRESENT_FILTER).count()
    total_students = (
        Enrollment.objects.filter(group_id__in=all_group_ids, is_active=True)
        .values("student_id")
        .distinct()
        .count()
    )

    monthly_payout = (
        SalaryPayout.objects.filter(
            teacher=teacher,
            center=center,
            period_year=timezone.localdate().year,
            period_month=timezone.localdate().month,
        )
        .order_by("-paid_at")
        .first()
    )

    real_income = _teacher_real_income(teacher, center)

    return {
        "groups": groups,
        "selected_group_id": selected_group.id if selected_group else None,
        "attendance_sheet": _teacher_attendance_sheet(selected_group) if selected_group else None,
        "students": _teacher_students_payload(selected_group) if selected_group else [],
        "monthly_income": {
            "paid_out": _money(getattr(monthly_payout, "amount", 0)),
            "real_income": real_income,
        },
        "statistics": {
            "groups_count": len(groups),
            "students_count": total_students,
            "average_attendance_rate": round((all_present / all_total) * 100, 1) if all_total else 0,
        },
    }


def _month_bounds(today):
    month_start = today.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    return month_start, month_end


def _ensure_churn(center):
    if not center:
        return
    if ChurnRisk.objects.filter(center=center).exists():
        return
    try:
        from core.churn_service import run_churn_assessment

        run_churn_assessment(center, notify_managers=False)
    except Exception:
        logger.exception("Churn hisoblash muvaffaqiyatsiz: center=%s", getattr(center, "id", None))


def _management_dashboard(user: User, center) -> dict:
    today = timezone.localdate()
    month_start, month_end = _month_bounds(today)
    _ensure_churn(center)

    today_payments_qs = Payment.objects.filter(center=center, paid_date=today)
    today_arrivals_qs = Attendance.objects.filter(center=center, date=today).filter(PRESENT_FILTER)
    leads_qs = Lead.objects.filter(center=center, qoshilgan_sana__date=today, is_archived=False).order_by("-qoshilgan_sana")
    risky_qs = (
        ChurnRisk.objects.filter(center=center, risk_level=ChurnRisk.HIGH)
        .select_related("student")
        .order_by("-risk_score")[:10]
    )

    month_revenue = _money(
        Payment.objects.filter(center=center, paid_date__gte=month_start, paid_date__lt=month_end)
        .aggregate(total=Sum("summa"))["total"]
    )
    month_expense = _money(
        Expense.objects.filter(center=center, sana__date__gte=month_start, sana__date__lt=month_end)
        .aggregate(total=Sum("summa"))["total"]
    )

    return {
        "daily_report": {
            "today_payments": _money(today_payments_qs.aggregate(total=Sum("summa"))["total"]),
            "payment_count": today_payments_qs.count(),
            "arrivals_count": today_arrivals_qs.values("student_id").distinct().count(),
        },
        "risky_students": [
            {
                "student_id": item.student_id,
                "full_name": item.student.get_full_name(),
                "risk_score": item.risk_score,
                "attendance_percent": item.att_pct,
                "debt_amount": _money(item.debt_amount),
                "reasons": item.reasons or [],
            }
            for item in risky_qs
        ],
        "new_leads": [
            {
                "id": lead.id,
                "full_name": lead.full_name,
                "phone": lead.telefon1,
                "status": lead.status.nom if lead.status else "—",
                "created_at": timezone.localtime(lead.qoshilgan_sana).strftime("%d.%m.%Y %H:%M"),
            }
            for lead in leads_qs[:10]
        ],
        "finance": {
            "month_revenue": month_revenue,
            "month_expense": month_expense,
            "difference": month_revenue - month_expense,
        },
        "staff": {
            "teachers_count": User.objects.filter(center=center, role="teacher", is_archived=False).count(),
            "managers_count": User.objects.filter(center=center, role="manager", is_archived=False).count(),
            "directors_count": User.objects.filter(center=center, role="director", is_archived=False).count(),
        },
        "broadcast_audiences": ["students", "teachers"],
    }


def _group_accessible_for_user(group: Group, user: User) -> bool:
    if user.is_superuser:
        return True
    if user.role in ("manager", "director"):
        return group.center_id == user.center_id
    if user.role == "teacher":
        return group.oqituvchi_id == user.id
    if user.role == "student":
        return Enrollment.objects.filter(group=group, student=user, is_active=True).exists()
    if user.role == "parent":
        return Enrollment.objects.filter(group=group, student__in=user.children.all(), is_active=True).exists()
    return False


def _certificate_accessible_for_user(certificate: CertificateRecord, user: User) -> bool:
    if user.is_superuser:
        return True
    if user.role in ("manager", "director"):
        return certificate.center_id == user.center_id
    if user.role == "teacher":
        return certificate.group.oqituvchi_id == user.id
    if user.role == "student":
        return certificate.student_id == user.id
    if user.role == "parent":
        return user.children.filter(pk=certificate.student_id).exists()
    return False


def _dedupe_messages(messages: list[dict]) -> list[dict]:
    seen = set()
    items = []
    for item in messages:
        key = (str(item.get("chat_id")), item.get("text"))
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items


@csrf_exempt
@require_GET
@_safe_api
def bot_dashboard(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    user = _linked_user(request)
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    center = _resolve_center(user)
    child_id = str(request.GET.get("child_id") or "").strip()
    group_id = str(request.GET.get("group_id") or "").strip()

    payload = {
        "ok": True,
        "role": user.role,
        "full_name": user.get_full_name(),
        "center_name": getattr(center, "name", ""),
    }

    if user.role == "student":
        payload["student"] = _student_dashboard(user, center)
    elif user.role == "parent":
        payload["parent"] = _parent_dashboard(user, center, child_id=child_id or None)
    elif user.role == "teacher":
        payload["teacher"] = _teacher_dashboard(user, center, group_id=group_id or None)
    elif user.role in ("manager", "director"):
        payload["management"] = _management_dashboard(user, center)
    else:
        return _json_error("Bu rol uchun menyu mavjud emas", status=403)

    return JsonResponse(payload)


@csrf_exempt
@require_POST
@_safe_api
def bot_notification_settings(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    data = _parse_json_body(request)
    tg_id = str(data.get("telegram_id") or "").strip()
    email = str(data.get("email") or "").strip()
    enabled = bool(data.get("enabled"))

    user = _linked_user_from_values(
        tg_id=tg_id,
        email=email,
        allowed_roles=("student", "parent", "teacher", "manager", "director"),
    )
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    pref.receive_coin = enabled
    pref.receive_broadcast = enabled
    pref.receive_purchase = enabled
    pref.receive_system = enabled
    pref.save(update_fields=["receive_coin", "receive_broadcast", "receive_purchase", "receive_system", "updated_at"])

    return JsonResponse({"ok": True, "enabled": enabled})


@csrf_exempt
@require_POST
@_safe_api
def bot_store_purchase_request_create(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    data = _parse_json_body(request)
    tg_id = str(data.get("telegram_id") or "").strip()
    email = str(data.get("email") or "").strip()
    product_id = data.get("product_id")
    qty = max(_money(data.get("qty") or 1), 1)

    user = _linked_user_from_values(tg_id=tg_id, email=email, allowed_roles=("student",))
    if not user:
        return _json_error("O'quvchi topilmadi", status=404)

    product = get_object_or_404(Product.objects.filter(center=user.center, is_deleted=False), pk=product_id)
    purchase = PurchaseRequest.objects.create(
        center=user.center,
        student=user,
        product=product,
        qty=qty,
    )
    return JsonResponse(
        {
            "ok": True,
            "id": purchase.id,
            "status": purchase.status,
            "product_name": product.nom,
        },
        status=201,
    )


@csrf_exempt
@require_GET
@_safe_api
def bot_group_attendance_sheet(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    user = _linked_user(request, allowed_roles=("teacher", "manager", "director"))
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    group_id = request.GET.get("group_id")
    if not group_id:
        return _json_error("group_id majburiy")

    group = get_object_or_404(Group, pk=group_id, center=user.center, is_archived=False)
    if user.role == "teacher" and group.oqituvchi_id != user.id:
        return _json_error("Bu guruh sizga tegishli emas", status=403)

    return JsonResponse({"ok": True, "sheet": _teacher_attendance_sheet(group)})


@csrf_exempt
@require_POST
@_safe_api
def bot_group_attendance_mark(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    data = _parse_json_body(request)
    tg_id = str(data.get("telegram_id") or "").strip()
    email = str(data.get("email") or "").strip()
    group_id = data.get("group_id")
    student_id = data.get("student_id")
    target_status = str(data.get("status") or "").strip()

    user = _linked_user_from_values(
        tg_id=tg_id,
        email=email,
        allowed_roles=("teacher", "manager", "director"),
    )
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    group = get_object_or_404(Group, pk=group_id, center=user.center, is_archived=False)
    if user.role == "teacher" and group.oqituvchi_id != user.id:
        return _json_error("Bu guruh sizga tegishli emas", status=403)

    student = get_object_or_404(
        User.objects.filter(role="student"),
        pk=student_id,
    )
    if not Enrollment.objects.filter(group=group, student=student, is_active=True).exists():
        return _json_error("O'quvchi guruhda topilmadi", status=404)

    if target_status not in {"present", "absent"}:
        return _json_error("status noto'g'ri")

    new_status = toggle_attendance(
        group=group,
        student=student,
        date_value=timezone.localdate(),
        target_status=target_status,
        current_status="none",
    )
    attendance = Attendance.objects.filter(group=group, student=student, date=timezone.localdate()).first()
    if attendance:
        update_fields = []
        if attendance.center_id != group.center_id:
            attendance.center = group.center
            update_fields.append("center")
        if attendance.created_by_id != user.id:
            attendance.created_by = user
            update_fields.append("created_by")
        if attendance.teacher_id != group.oqituvchi_id:
            attendance.teacher = group.oqituvchi
            update_fields.append("teacher")
        if update_fields:
            attendance.save(update_fields=update_fields)

    return JsonResponse(
        {
            "ok": True,
            "status": new_status,
            "status_label": _present_status_label(new_status),
            "student_name": student.get_full_name(),
        }
    )


@csrf_exempt
@require_GET
@_safe_api
def bot_broadcast_audience(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    user = _linked_user(request, allowed_roles=("manager", "director"))
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    audience = str(request.GET.get("audience") or "").strip().lower()
    if audience not in {"students", "teachers"}:
        return _json_error("audience noto'g'ri")

    role = "student" if audience == "students" else "teacher"
    candidates = User.objects.filter(
        center=user.center,
        role=role,
        is_telegram_linked=True,
        telegram_id__isnull=False,
        is_archived=False,
    ).order_by("id")

    tg_ids = []
    for candidate in candidates:
        if NotificationPreference.wants_notification(candidate, "broadcast"):
            tg_ids.append(str(candidate.telegram_id))

    return JsonResponse({"ok": True, "tg_ids": sorted(set(tg_ids))})


@csrf_exempt
@require_GET
@_safe_api
def bot_inline_student_search(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    user = _linked_user(request, allowed_roles=("manager", "director"))
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    query = str(request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"ok": True, "items": []})

    students = (
        User.objects.filter(center=user.center, role="student", is_archived=False)
        .filter(Q(ism__icontains=query) | Q(familya__icontains=query) | Q(telefon1__icontains=query) | Q(phone_number__icontains=query))
        .order_by("ism", "familya")[:10]
    )
    items = []
    for student in students:
        debt, _ = _student_debt_breakdown(student, user.center)
        attendance = _student_attendance_payload(student, user.center, days=30)
        enrollment = _student_active_enrollments(student, user.center).first()
        items.append(
            {
                "id": student.id,
                "full_name": student.get_full_name(),
                "group_name": enrollment.group.nom if enrollment else "Guruhsiz",
                "attendance_rate": attendance["recent_rate"],
                "debt": debt,
            }
        )
    return JsonResponse({"ok": True, "items": items})


@csrf_exempt
@require_GET
@_safe_api
def bot_deep_link(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    user = _linked_user(request)
    if not user:
        return _json_error("Foydalanuvchi topilmadi", status=404)

    param = str(request.GET.get("param") or "").strip()
    if not param:
        return _json_error("param majburiy")

    if param == "pay_reminder":
        if user.role == "parent":
            parent_payload = _parent_dashboard(user, user.center)
            child_payload = parent_payload.get("child") or {}
            return JsonResponse({"ok": True, "type": "pay_reminder", "payload": child_payload.get("payment")})
        if user.role == "student":
            return JsonResponse({"ok": True, "type": "pay_reminder", "payload": _student_dashboard(user, user.center)["payment"]})
        return _json_error("Bu deep link sizga mos emas", status=403)

    if param.startswith("group_"):
        group_id = param.split("_", 1)[1]
        group = get_object_or_404(Group, pk=group_id)
        if not _group_accessible_for_user(group, user):
            return _json_error("Guruhga ruxsat yo'q", status=403)
        return JsonResponse(
            {
                "ok": True,
                "type": "group",
                "payload": {
                    "id": group.id,
                    "name": group.nom,
                    "teacher_name": group.oqituvchi.get_full_name() if group.oqituvchi else "Belgilanmagan",
                    "monthly_price": _money(group.kurs_narxi),
                    "lessons_per_week": _money(group.lessons_per_week),
                    "estimated_end_date": _fmt_date(group.estimated_end_date),
                    "student_count": Enrollment.objects.filter(group=group, is_active=True).count(),
                },
            }
        )

    if param.startswith("cert_"):
        cert_id = param.split("_", 1)[1]
        certificate = get_object_or_404(CertificateRecord, pk=cert_id)
        if not _certificate_accessible_for_user(certificate, user):
            return _json_error("Sertifikatga ruxsat yo'q", status=403)
        return JsonResponse(
            {
                "ok": True,
                "type": "certificate",
                "payload": {
                    "id": certificate.id,
                    "certificate_number": certificate.certificate_number,
                    "student_name": certificate.student.get_full_name(),
                    "group_name": certificate.group.nom,
                    "issue_date": _fmt_date(certificate.issue_date),
                    "status": certificate.status,
                },
            }
        )

    return _json_error("Noma'lum deep link")


@csrf_exempt
@require_GET
@_safe_api
def bot_scheduler_payment_reminders(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    messages = []
    parent_bucket: dict[str, list[str]] = defaultdict(list)
    for student in User.objects.filter(role="student", is_archived=False).select_related("center"):
        center = student.center
        if not center:
            continue
        debt, _ = _student_debt_breakdown(student, center)
        if debt <= 0:
            continue

        due_date = timezone.localdate().replace(day=min(max(int(center.payment_day or 5), 1), 28))
        text = (
            f"💰 Eslatma: {_fmt_money(debt)} so'm to'lovingiz kutilmoqda.\n"
            f"To'lov sanasi: {_fmt_date(due_date)}.\n"
            f"Markaz: {center.name}."
        )
        if student.is_telegram_linked and student.telegram_id and NotificationPreference.wants_notification(student, "system"):
            messages.append({"chat_id": str(student.telegram_id), "text": text})

        for parent in student.parents.filter(is_telegram_linked=True, telegram_id__isnull=False):
            if not NotificationPreference.wants_notification(parent, "system"):
                continue
            parent_bucket[str(parent.telegram_id)].append(
                f"• {student.get_full_name()} — {_fmt_money(debt)} so'm. To'lov sanasi: {_fmt_date(due_date)}."
            )

    for tg_id, lines in parent_bucket.items():
        text = "💰 Farzandingiz bo'yicha to'lov eslatmasi\n\n" + "\n".join(lines)
        messages.append({"chat_id": tg_id, "text": text})

    return JsonResponse({"ok": True, "items": _dedupe_messages(messages)})


@csrf_exempt
@require_GET
@_safe_api
def bot_scheduler_parent_attendance(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    today = timezone.localdate()
    parent_bucket: dict[str, list[str]] = defaultdict(list)
    attendance_qs = Attendance.objects.filter(date=today).select_related("student", "group")
    for record in attendance_qs:
        student = record.student
        if record.status == "present" or record.present:
            line = f"✅ {student.get_full_name()} bugun darsga keldi. Guruh: {record.group.nom}"
        else:
            line = f"❌ {student.get_full_name()} bugun darsga kelmadi. Guruh: {record.group.nom}"
        for parent in student.parents.filter(is_telegram_linked=True, telegram_id__isnull=False):
            if not NotificationPreference.wants_notification(parent, "system"):
                continue
            parent_bucket[str(parent.telegram_id)].append(line)

    messages = [
        {"chat_id": tg_id, "text": "\n".join(lines)}
        for tg_id, lines in parent_bucket.items()
        if lines
    ]
    return JsonResponse({"ok": True, "items": _dedupe_messages(messages)})


def _current_week_bounds():
    today = timezone.localdate()
    start = today - timedelta(days=today.weekday())
    end = today
    return start, end


@csrf_exempt
@require_GET
@_safe_api
def bot_scheduler_weekly_reports(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    week_start, week_end = _current_week_bounds()
    messages = []

    for teacher in User.objects.filter(role="teacher", is_archived=False, is_telegram_linked=True).select_related("center"):
        center = teacher.center
        if not center or not NotificationPreference.wants_notification(teacher, "system"):
            continue
        groups = Group.objects.filter(center=center, oqituvchi=teacher, is_archived=False)
        attendance_qs = Attendance.objects.filter(group__in=groups, date__gte=week_start, date__lte=week_end)
        total = attendance_qs.count()
        present = attendance_qs.filter(PRESENT_FILTER).count()
        student_count = Enrollment.objects.filter(group__in=groups, is_active=True).values("student_id").distinct().count()

        estimated_salary = 0
        for group in groups:
            per_lesson = group.dars_boshiga_tolov()
            group_present = Attendance.objects.filter(group=group, date__gte=week_start, date__lte=week_end).filter(PRESENT_FILTER).count()
            estimated_salary += int(round(per_lesson * group_present))

        text = (
            "📊 Haftalik hisobot\n\n"
            f"Davr: {_fmt_date(week_start)} - {_fmt_date(week_end)}\n"
            f"Davomat: {round((present / total) * 100, 1) if total else 0}%\n"
            f"O'quvchilar soni: {student_count}\n"
            f"Hisoblangan maosh: {_fmt_money(estimated_salary)} so'm"
        )
        messages.append({"chat_id": str(teacher.telegram_id), "text": text})

    for director in User.objects.filter(role="director", is_archived=False, is_telegram_linked=True).select_related("center"):
        center = director.center
        if not center or not NotificationPreference.wants_notification(director, "system"):
            continue
        _ensure_churn(center)
        weekly_revenue = _money(
            Payment.objects.filter(center=center, paid_date__gte=week_start, paid_date__lte=week_end)
            .aggregate(total=Sum("summa"))["total"]
        )
        new_students = User.objects.filter(
            center=center,
            role="student",
            date_joined__date__gte=week_start,
            date_joined__date__lte=week_end,
            is_archived=False,
        ).count()
        churn_count = ChurnRisk.objects.filter(center=center, risk_level=ChurnRisk.HIGH).count()
        text = (
            "📈 Direktor haftalik hisobot\n\n"
            f"Davr: {_fmt_date(week_start)} - {_fmt_date(week_end)}\n"
            f"Haftalik daromad: {_fmt_money(weekly_revenue)} so'm\n"
            f"Yangi o'quvchilar: {new_students}\n"
            f"Churn xavfi yuqori o'quvchilar: {churn_count}"
        )
        messages.append({"chat_id": str(director.telegram_id), "text": text})

    return JsonResponse({"ok": True, "items": _dedupe_messages(messages)})


@csrf_exempt
@require_GET
@_safe_api
def bot_scheduler_month_end_reminders(request):
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    messages = []
    for student in User.objects.filter(role="student", is_archived=False, is_telegram_linked=True).select_related("center"):
        center = student.center
        if not center or not student.telegram_id:
            continue
        debt, _ = _student_debt_breakdown(student, center)
        if debt <= 0 or not NotificationPreference.wants_notification(student, "system"):
            continue
        messages.append(
            {
                "chat_id": str(student.telegram_id),
                "text": f"⚠️ Oy tugashiga 5 kun qoldi. {_fmt_money(debt)} so'm to'lovingiz bor.",
            }
        )
    return JsonResponse({"ok": True, "items": _dedupe_messages(messages)})
