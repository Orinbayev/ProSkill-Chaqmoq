from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import Center, User
from education.models import Attendance, Enrollment, Group, Payment, TeacherIncome
from store.models import Expense, Lead, Product, PurchaseRequest, Sale, TrialLesson


def _coerce_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _period(date_from=None, date_to=None) -> tuple[date, date]:
    """
    Sana berilmasa avtomatik joriy oy oralig'ini qaytaradi.
    """
    today = timezone.localdate()
    start = _coerce_date(date_from)
    end = _coerce_date(date_to)

    if start and not end:
        end = start
    if end and not start:
        start = end

    if not start and not end:
        start = today.replace(day=1)
        end = today

    if start and end and start > end:
        start, end = end, start

    return start, end


def _safe_sum(qs, field: str) -> int:
    return int(qs.aggregate(total=Sum(field)).get("total") or 0)


def _user_phone(user: User) -> str:
    return (
        user.telefon1
        or user.phone_number
        or user.telefon2
        or ""
    ).strip()


def _full_name(obj) -> str:
    full_name = getattr(obj, "full_name", None)
    if callable(full_name):
        return full_name()
    if isinstance(full_name, str) and full_name.strip():
        return full_name.strip()
    return " ".join(
        part for part in [
            getattr(obj, "ism", ""),
            getattr(obj, "familya", ""),
            getattr(obj, "otchestvo", ""),
        ] if part
    ).strip()


def get_center_finance_context(center: Center, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)

    payments_qs = Payment.objects.filter(center=center, paid_date__range=(start, end))
    expenses_qs = Expense.objects.filter(center=center, sana__date__range=(start, end))
    teacher_income_qs = TeacherIncome.objects.filter(center=center, attendance__date__range=(start, end))

    revenue = _safe_sum(payments_qs, "summa")
    expenses_total = _safe_sum(expenses_qs, "summa")
    teacher_payout = _safe_sum(teacher_income_qs, "amount")
    profit = revenue - expenses_total - teacher_payout

    daily_revenue = [
        {
            "day": row["paid_date"].isoformat(),
            "amount": int(row["amount"] or 0),
        }
        for row in payments_qs.values("paid_date").annotate(amount=Sum("summa")).order_by("paid_date")
    ]

    monthly_revenue = [
        {
            "month": row["month"].date().isoformat() if hasattr(row["month"], "date") else row["month"].isoformat(),
            "amount": int(row["amount"] or 0),
        }
        for row in (
            Payment.objects.filter(
                center=center,
                paid_date__gte=end - timedelta(days=365),
                paid_date__lte=end,
            )
            .annotate(month=TruncMonth("paid_date"))
            .values("month")
            .annotate(amount=Sum("summa"))
            .order_by("month")
        )
    ]

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "revenue": revenue,
            "expenses": expenses_total,
            "teacher_payout": teacher_payout,
            "profit": profit,
            "payments_count": payments_qs.count(),
            "expense_count": expenses_qs.count(),
        },
        "daily_revenue": daily_revenue,
        "monthly_revenue": monthly_revenue,
    }


def get_center_students_context(center: Center, query: str | None = None, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    students_qs = User.objects.filter(center=center, role="student", is_archived=False).order_by("ism", "familya")

    if query:
        students_qs = students_qs.filter(
            Q(ism__icontains=query)
            | Q(familya__icontains=query)
            | Q(telefon1__icontains=query)
            | Q(telefon2__icontains=query)
            | Q(phone_number__icontains=query)
        )

    students = list(students_qs[:limit])
    student_ids = [student.id for student in students]

    group_map: dict[int, list[str]] = defaultdict(list)
    for enrollment in (
        Enrollment.objects.filter(center=center, student_id__in=student_ids, is_active=True)
        .select_related("group")
        .order_by("group__nom")
    ):
        if enrollment.group_id and enrollment.group:
            group_map[enrollment.student_id].append(enrollment.group.nom)

    payment_map = {
        row["student_id"]: int(row["total"] or 0)
        for row in (
            Payment.objects.filter(center=center, student_id__in=student_ids, paid_date__range=(start, end))
            .values("student_id")
            .annotate(total=Sum("summa"))
        )
    }

    attendance_map = {
        row["student_id"]: {
            "present": int(row["present"] or 0),
            "absent": int(row["absent"] or 0),
        }
        for row in (
            Attendance.objects.filter(center=center, student_id__in=student_ids, date__range=(start, end))
            .values("student_id")
            .annotate(
                present=Count("id", filter=Q(status="present") | Q(present=True) | Q(forced=True)),
                absent=Count("id", filter=Q(status__in=["absent_excused", "absent_unexcused"])),
            )
        )
    }

    items = []
    for student in students:
        attendance = attendance_map.get(student.id, {"present": 0, "absent": 0})
        items.append(
            {
                "id": student.id,
                "full_name": _full_name(student),
                "phone": _user_phone(student),
                "chaqmoq": int(student.chaqmoq or 0),
                "groups": group_map.get(student.id, []),
                "groups_count": len(group_map.get(student.id, [])),
                "paid_in_period": payment_map.get(student.id, 0),
                "attendance_present": attendance["present"],
                "attendance_absent": attendance["absent"],
            }
        )

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_students": User.objects.filter(center=center, role="student", is_archived=False).count(),
            "active_students": Enrollment.objects.filter(center=center, is_active=True).values("student_id").distinct().count(),
            "returned_count": len(items),
        },
        "items": items,
    }


def get_center_teachers_context(center: Center, query: str | None = None, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    teachers_qs = User.objects.filter(center=center, role="teacher", is_archived=False).order_by("ism", "familya")

    if query:
        teachers_qs = teachers_qs.filter(
            Q(ism__icontains=query)
            | Q(familya__icontains=query)
            | Q(telefon1__icontains=query)
            | Q(phone_number__icontains=query)
        )

    teachers = list(teachers_qs[:limit])
    teacher_ids = [teacher.id for teacher in teachers]

    group_counts = {
        row["oqituvchi_id"]: int(row["groups"] or 0)
        for row in (
            Group.objects.filter(center=center, oqituvchi_id__in=teacher_ids, is_archived=False)
            .values("oqituvchi_id")
            .annotate(groups=Count("id"))
        )
    }

    student_counts = {
        row["group__oqituvchi_id"]: int(row["students"] or 0)
        for row in (
            Enrollment.objects.filter(center=center, is_active=True, group__oqituvchi_id__in=teacher_ids)
            .values("group__oqituvchi_id")
            .annotate(students=Count("student_id", distinct=True))
        )
    }

    income_map = {
        row["teacher_id"]: int(row["total"] or 0)
        for row in (
            TeacherIncome.objects.filter(center=center, teacher_id__in=teacher_ids, attendance__date__range=(start, end))
            .values("teacher_id")
            .annotate(total=Sum("amount"))
        )
    }

    items = []
    for teacher in teachers:
        items.append(
            {
                "id": teacher.id,
                "full_name": _full_name(teacher),
                "phone": _user_phone(teacher),
                "group_count": group_counts.get(teacher.id, 0),
                "student_count": student_counts.get(teacher.id, 0),
                "income_in_period": income_map.get(teacher.id, 0),
                "share_percent": int(teacher.oqituvchi_foizi or 0),
            }
        )

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_teachers": User.objects.filter(center=center, role="teacher", is_archived=False).count(),
            "returned_count": len(items),
        },
        "items": items,
    }


def get_center_groups_context(center: Center, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    groups = list(
        Group.objects.filter(center=center, is_archived=False)
        .select_related("oqituvchi")
        .order_by("nom")[:limit]
    )
    group_ids = [group.id for group in groups]

    student_counts = {
        row["group_id"]: int(row["students"] or 0)
        for row in (
            Enrollment.objects.filter(center=center, is_active=True, group_id__in=group_ids)
            .values("group_id")
            .annotate(students=Count("student_id", distinct=True))
        )
    }

    payment_map = {
        row["group_id"]: int(row["total"] or 0)
        for row in (
            Payment.objects.filter(center=center, group_id__in=group_ids, paid_date__range=(start, end))
            .values("group_id")
            .annotate(total=Sum("summa"))
        )
    }

    attendance_map = {
        row["group_id"]: int(row["present"] or 0)
        for row in (
            Attendance.objects.filter(center=center, group_id__in=group_ids, date__range=(start, end))
            .values("group_id")
            .annotate(present=Count("id", filter=Q(status="present") | Q(present=True) | Q(forced=True)))
        )
    }

    items = []
    for group in groups:
        teacher_name = _full_name(group.oqituvchi) if group.oqituvchi_id and group.oqituvchi else ""
        items.append(
            {
                "id": group.id,
                "name": group.nom,
                "teacher": teacher_name,
                "course_price": int(group.kurs_narxi or 0),
                "teacher_share_percent": int(group.oqituvchi_foiz or 0),
                "students": student_counts.get(group.id, 0),
                "revenue_in_period": payment_map.get(group.id, 0),
                "attended_lessons_in_period": attendance_map.get(group.id, 0),
            }
        )

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_groups": Group.objects.filter(center=center, is_archived=False).count(),
            "returned_count": len(items),
        },
        "items": items,
    }


def get_center_leads_context(center: Center, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    leads_qs = Lead.objects.filter(center=center, is_archived=False)
    period_qs = leads_qs.filter(qoshilgan_sana__date__range=(start, end))

    top_sources = [
        {"name": row["manba__nom"] or "Noma'lum", "count": int(row["count"] or 0)}
        for row in (
            period_qs.values("manba__nom")
            .annotate(count=Count("id"))
            .order_by("-count", "manba__nom")[:5]
        )
    ]

    top_directions = [
        {"name": row["yonalish__nom"] or "Noma'lum", "count": int(row["count"] or 0)}
        for row in (
            period_qs.values("yonalish__nom")
            .annotate(count=Count("id"))
            .order_by("-count", "yonalish__nom")[:5]
        )
    ]

    latest_items = []
    for lead in (
        period_qs.select_related("manba", "yonalish", "status", "assigned_manager")
        .order_by("-qoshilgan_sana")[:limit]
    ):
        latest_items.append(
            {
                "id": lead.id,
                "full_name": lead.full_name,
                "phone": lead.telefon1,
                "source": lead.manba.nom if lead.manba_id and lead.manba else "",
                "direction": lead.yonalish.nom if lead.yonalish_id and lead.yonalish else "",
                "status": lead.status.nom if lead.status_id and lead.status else "",
                "manager": _full_name(lead.assigned_manager) if lead.assigned_manager_id and lead.assigned_manager else "",
                "converted": bool(lead.converted_to_student),
                "created_at": lead.qoshilgan_sana.isoformat(),
            }
        )

    trial_count = TrialLesson.objects.filter(center=center, scheduled_at__date__range=(start, end)).count()

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_leads": leads_qs.count(),
            "period_leads": period_qs.count(),
            "converted_in_period": period_qs.filter(converted_to_student=True).count(),
            "trial_lessons_in_period": trial_count,
        },
        "top_sources": top_sources,
        "top_directions": top_directions,
        "items": latest_items,
    }


def get_center_store_context(center: Center, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)

    sales_qs = Sale.objects.filter(center=center, sana__date__range=(start, end))
    requests_qs = PurchaseRequest.objects.filter(center=center, sana__date__range=(start, end))

    top_products = [
        {
            "name": row["product__nom"] or "Noma'lum",
            "qty": int(row["qty"] or 0),
            "amount": int(row["amount"] or 0),
        }
        for row in (
            sales_qs.values("product__nom")
            .annotate(qty=Sum("qty"), amount=Sum("narx_som"))
            .order_by("-qty", "-amount")[:5]
        )
    ]

    latest_products = [
        {
            "id": product.id,
            "name": product.nom,
            "price_som": int(product.narx_som or 0),
            "price_chaqmoq": int(product.narx_chaqmoq or 0),
            "sold_count": int(product.sotilgan_soni or 0),
        }
        for product in Product.objects.filter(center=center).order_by("-yaratilgan")[:limit]
    ]

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "products_count": Product.objects.filter(center=center).count(),
            "sales_count": sales_qs.count(),
            "sales_amount": _safe_sum(sales_qs, "narx_som"),
            "requests_count": requests_qs.count(),
            "pending_requests": requests_qs.filter(status=PurchaseRequest.PENDING).count(),
        },
        "top_products": top_products,
        "items": latest_products,
    }


def build_center_ai_context(
    center: Center,
    *,
    question: str = "",
    date_from=None,
    date_to=None,
    query: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Bu servis HECH NARSANI qo'lda saqlamaydi.
    U faqat hozir ulangan Django DB dan tenant-safe context yig'adi.

    Foydalanish:
        from accounts.models import Center
        from core.services.center_ai_context import build_center_ai_context
        center = Center.objects.get(slug="test")
        ctx = build_center_ai_context(center, question="Bugungi daromad qancha?")
    """
    start, end = _period(date_from, date_to)

    return {
        "center": {
            "id": center.id,
            "name": center.name,
            "slug": center.slug,
            "plan": center.plan,
        },
        "question": question.strip(),
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "finance": get_center_finance_context(center, start, end),
        "students": get_center_students_context(center, query=query, limit=limit, date_from=start, date_to=end),
        "teachers": get_center_teachers_context(center, query=query, limit=limit, date_from=start, date_to=end),
        "groups": get_center_groups_context(center, limit=limit, date_from=start, date_to=end),
        "leads": get_center_leads_context(center, limit=limit, date_from=start, date_to=end),
        "store": get_center_store_context(center, limit=limit, date_from=start, date_to=end),
    }


def build_center_ai_prompt_context(
    center: Center,
    *,
    question: str = "",
    date_from=None,
    date_to=None,
    query: str | None = None,
    limit: int = 10,
) -> str:
    """
    Gemini yoki boshqa LLM ga berish uchun qisqa matnli context.
    """
    ctx = build_center_ai_context(
        center,
        question=question,
        date_from=date_from,
        date_to=date_to,
        query=query,
        limit=limit,
    )
    finance = ctx["finance"]["summary"]
    students = ctx["students"]["summary"]
    teachers = ctx["teachers"]["summary"]
    groups = ctx["groups"]["summary"]
    leads = ctx["leads"]["summary"]
    store = ctx["store"]["summary"]

    return "\n".join(
        [
            f"Markaz: {ctx['center']['name']} ({ctx['center']['slug']})",
            f"Savol: {ctx['question'] or '—'}",
            f"Davr: {ctx['period']['date_from']} dan {ctx['period']['date_to']} gacha",
            f"Daromad: {finance['revenue']} so'm",
            f"Xarajat: {finance['expenses']} so'm",
            f"Ustoz ulushi: {finance['teacher_payout']} so'm",
            f"Foyda: {finance['profit']} so'm",
            f"Jami o'quvchi: {students['total_students']}",
            f"Faol o'quvchi: {students['active_students']}",
            f"Jami ustoz: {teachers['total_teachers']}",
            f"Jami guruh: {groups['total_groups']}",
            f"Jami lead: {leads['total_leads']}",
            f"Bu davr leadi: {leads['period_leads']}",
            f"Mahsulotlar: {store['products_count']}",
            f"Sotuvlar: {store['sales_count']}",
            f"So'rovlar: {store['requests_count']}",
        ]
    )
