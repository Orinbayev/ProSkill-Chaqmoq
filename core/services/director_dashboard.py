from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone

from accounts.models import Center, User
from education.models import (
    Attendance,
    Category,
    Enrollment,
    Group,
    GroupClosureWorkflow,
    Payment,
    PaymentAllocation,
    StudentGroupHistory,
    TuitionMonth,
)
from store.models import Expense, Lead, LeadStatus, Manba, TrialLesson


PRESET_LABELS = {
    "today": "Bugun",
    "yesterday": "Kecha",
    "this_week": "Bu hafta",
    "this_month": "Bu oy",
    "last_month": "O'tgan oy",
    "this_quarter": "Bu chorak",
    "custom": "Ixtiyoriy sana oralig'i",
}

PAYMENT_TYPE_LABELS = {
    "cash": "Naqd",
    "card": "Karta",
    "mixed": "Aralash",
}

INSIGHT_SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def percent(numerator: float, denominator: float) -> float:
    return round(safe_div(numerator, denominator) * 100, 1)


def growth_pct(current: float, previous: float) -> float:
    if not previous:
        return 100.0 if current > 0 else 0.0
    return round(((float(current) - float(previous)) / float(previous)) * 100, 1)


def month_start(d: date) -> date:
    return d.replace(day=1)


def parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_csv_ints(raw: str | Iterable[str] | None) -> tuple[int, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        values = raw.split(",")
    else:
        values = list(raw)
    out: list[int] = []
    for value in values:
        value = str(value or "").strip()
        if not value:
            continue
        if value.isdigit():
            out.append(int(value))
    return tuple(dict.fromkeys(out))


def parse_csv_strings(raw: str | Iterable[str] | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        values = raw.split(",")
    else:
        values = list(raw)
    out: list[str] = []
    for value in values:
        value = str(value or "").strip()
        if value:
            out.append(value)
    return tuple(dict.fromkeys(out))


@dataclass(frozen=True)
class DashboardFilters:
    preset: str
    date_from: date
    date_to: date
    previous_from: date
    previous_to: date
    category_ids: tuple[int, ...]
    group_ids: tuple[int, ...]
    teacher_ids: tuple[int, ...]
    payment_types: tuple[str, ...]
    source_ids: tuple[int, ...]
    student_cycle: str
    student_status: str
    debt_status: str
    branch_ids: tuple[int, ...]


def resolve_dashboard_filters(center: Center, params) -> DashboardFilters:
    today = timezone.localdate()
    preset = (params.get("preset") or params.get("period") or "this_month").strip().lower()

    date_from = parse_iso_date(params.get("date_from"))
    date_to = parse_iso_date(params.get("date_to"))

    if date_from and date_to and date_from <= date_to:
        preset = "custom"
    else:
        if preset == "today":
            date_from = date_to = today
        elif preset == "yesterday":
            date_from = date_to = today - timedelta(days=1)
        elif preset == "this_week":
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif preset == "last_month":
            first_this = today.replace(day=1)
            date_to = first_this - timedelta(days=1)
            date_from = date_to.replace(day=1)
        elif preset == "this_quarter":
            quarter_month = ((today.month - 1) // 3) * 3 + 1
            date_from = today.replace(month=quarter_month, day=1)
            date_to = today
        else:
            preset = "this_month"
            date_from = today.replace(day=1)
            date_to = today

    delta_days = (date_to - date_from).days + 1
    previous_to = date_from - timedelta(days=1)
    previous_from = previous_to - timedelta(days=delta_days - 1)

    category_ids = parse_csv_ints(params.get("category") or params.get("category_ids"))
    group_ids = parse_csv_ints(params.get("group") or params.get("group_ids"))
    teacher_ids = parse_csv_ints(params.get("teacher") or params.get("teacher_ids"))
    payment_types = parse_csv_strings(params.get("payment_type") or params.get("payment_types"))
    source_ids = parse_csv_ints(params.get("source") or params.get("source_ids"))
    branch_ids = parse_csv_ints(params.get("branch") or params.get("branch_ids")) or (center.id,)

    student_cycle = (params.get("student_cycle") or "all").strip().lower()
    if student_cycle not in {"all", "new", "returning"}:
        student_cycle = "all"

    student_status = (params.get("student_status") or "all").strip().lower()
    if student_status not in {"all", "active", "inactive", "dropped"}:
        student_status = "all"

    debt_status = (params.get("debt_status") or "all").strip().lower()
    if debt_status not in {"all", "debtor", "clear"}:
        debt_status = "all"

    return DashboardFilters(
        preset=preset,
        date_from=date_from,
        date_to=date_to,
        previous_from=previous_from,
        previous_to=previous_to,
        category_ids=category_ids,
        group_ids=group_ids,
        teacher_ids=teacher_ids,
        payment_types=payment_types,
        source_ids=source_ids,
        student_cycle=student_cycle,
        student_status=student_status,
        debt_status=debt_status,
        branch_ids=branch_ids,
    )


class DirectorDashboardService:
    def __init__(self, *, center: Center, filters: DashboardFilters):
        self.center = center
        self.filters = filters
        self.today = timezone.localdate()
        self.snapshot_date = filters.date_to
        self.snapshot_month = month_start(filters.date_to)
        self.previous_snapshot_date = filters.previous_to

        self.all_students_qs = User.objects.filter(center=center, role="student").select_related("center")
        self.non_archived_students_qs = self.all_students_qs.filter(is_archived=False)
        self.archived_students_qs = self.all_students_qs.filter(is_archived=True)
        self.teachers_qs = User.objects.filter(center=center, role="teacher", is_archived=False)
        self.groups_qs = Group.objects.filter(center=center, is_archived=False).select_related("oqituvchi", "category_obj")

        if filters.category_ids:
            self.groups_qs = self.groups_qs.filter(category_obj_id__in=filters.category_ids)
        if filters.teacher_ids:
            self.groups_qs = self.groups_qs.filter(oqituvchi_id__in=filters.teacher_ids)
        if filters.group_ids:
            self.groups_qs = self.groups_qs.filter(id__in=filters.group_ids)

        self.group_list = list(self.groups_qs)
        self.group_ids = [group.id for group in self.group_list]
        self.group_map = {group.id: group for group in self.group_list}
        self.all_group_ids = list(Group.objects.filter(center=center, is_archived=False).values_list("id", flat=True))
        self.group_scope_restricted = bool(filters.category_ids or filters.group_ids or filters.teacher_ids)
        self.group_scope_ids = self.group_ids if self.group_scope_restricted else self.all_group_ids

        all_student_ids = set(self.all_students_qs.values_list("id", flat=True))
        self.all_student_ids = list(all_student_ids)
        if self.group_ids and (filters.category_ids or filters.teacher_ids or filters.group_ids):
            group_related_students = set(
                Enrollment.objects.filter(center=center, group_id__in=self.group_ids).values_list("student_id", flat=True)
            )
        else:
            group_related_students = set(all_student_ids)

        self.relevant_leads_qs = self._build_lead_scope()
        source_student_ids = {
            student_id for student_id in self.relevant_leads_qs.values_list("converted_user_id", flat=True) if student_id
        }

        self.first_payment_map = dict(
            Payment.objects.filter(center=center)
            .values("student_id")
            .annotate(first=Min("paid_date"))
            .values_list("student_id", "first")
        )

        active_student_ids = set(
            Enrollment.objects.filter(
                center=center,
                is_active=True,
                student__is_archived=False,
                group__is_archived=False,
                created_at__date__lte=self.snapshot_date,
            ).values_list("student_id", flat=True)
        )
        non_archived_student_ids = set(self.non_archived_students_qs.values_list("id", flat=True))
        inactive_student_ids = non_archived_student_ids - active_student_ids
        dropped_student_ids = set(self.archived_students_qs.values_list("id", flat=True))

        candidate_student_ids = set(all_student_ids) & group_related_students
        if filters.source_ids:
            candidate_student_ids &= source_student_ids
        if filters.student_cycle == "new":
            candidate_student_ids &= {
                student_id
                for student_id, first_date in self.first_payment_map.items()
                if first_date and filters.date_from <= first_date <= filters.date_to
            }
        elif filters.student_cycle == "returning":
            candidate_student_ids &= {
                student_id
                for student_id, first_date in self.first_payment_map.items()
                if first_date and first_date < filters.date_from
            }
        if filters.student_status == "active":
            candidate_student_ids &= active_student_ids
        elif filters.student_status == "inactive":
            candidate_student_ids &= inactive_student_ids
        elif filters.student_status == "dropped":
            candidate_student_ids &= dropped_student_ids

        self.student_scope_restricted = bool(
            self.group_scope_restricted or filters.source_ids or filters.student_cycle != "all" or filters.student_status != "all"
        )
        self._debt_snapshot = self._build_debt_snapshot(candidate_student_ids)
        self.debtor_student_ids = {
            student_id for student_id, amount in self._debt_snapshot["student_open_debt"].items() if amount > 0
        }
        if filters.debt_status == "debtor":
            candidate_student_ids &= self.debtor_student_ids
        elif filters.debt_status == "clear":
            candidate_student_ids -= self.debtor_student_ids

        self.student_scope_restricted = bool(
            self.group_scope_restricted
            or filters.source_ids
            or filters.student_cycle != "all"
            or filters.student_status != "all"
            or filters.debt_status != "all"
        )
        self.student_scope_ids = candidate_student_ids
        self.student_scope_qs = self.all_students_qs.filter(id__in=self.student_scope_ids)

        self.payments_period_qs = self._build_payment_scope(filters.date_from, filters.date_to)
        self.payments_previous_qs = self._build_payment_scope(filters.previous_from, filters.previous_to)

        self.total_center_active_students = Enrollment.objects.filter(
            center=center,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            created_at__date__lte=self.snapshot_date,
        ).values("student_id").distinct().count()
        self.filtered_active_students = Enrollment.objects.filter(
            center=center,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            created_at__date__lte=self.snapshot_date,
            student_id__in=self.student_scope_ids,
            group_id__in=self.group_scope_ids,
        ).values("student_id").distinct().count()

        self.actual_operating_expense = int(
            Expense.objects.filter(center=center, sana__date__range=(filters.date_from, filters.date_to)).aggregate(
                total=Sum("summa")
            )["total"]
            or 0
        )
        self.actual_operating_expense_previous = int(
            Expense.objects.filter(center=center, sana__date__range=(filters.previous_from, filters.previous_to)).aggregate(
                total=Sum("summa")
            )["total"]
            or 0
        )

    def _scope_groups(self, qs, field_name: str = "group_id"):
        if not self.group_scope_ids:
            return qs.none()
        return qs.filter(**{f"{field_name}__in": self.group_scope_ids})

    def _scope_students(self, qs, field_name: str = "student_id"):
        if self.student_scope_restricted:
            if not self.student_scope_ids:
                return qs.none()
            return qs.filter(**{f"{field_name}__in": self.student_scope_ids})
        return qs

    def _attendance_tuple_map(self, rows, key_field: str = "group_id"):
        mapped = {}
        for row in rows:
            mapped[row[key_field]] = (int(row["present"] or 0), int(row["total"] or 0))
        return mapped

    def _attendance_rate_for_range(self, start_date: date, end_date: date) -> float | None:
        qs = self._scope_students(
            self._scope_groups(
                Attendance.objects.filter(
                    center=self.center,
                    date__range=(start_date, end_date),
                )
            )
        )
        total = qs.count()
        if not total:
            return None
        present = qs.filter(Q(present=True) | Q(forced=True) | Q(status="present")).count()
        return round(percent(present, total), 1)

    def _bucket_label(self, bucket_value, use_daily: bool) -> str:
        return bucket_value.strftime("%d.%m") if use_daily else bucket_value.strftime("%b %Y")

    def _build_lead_scope(self):
        qs = Lead.objects.filter(center=self.center, is_archived=False).select_related(
            "manba",
            "status",
            "converted_user",
            "yonalish",
        )
        if self.filters.source_ids:
            qs = qs.filter(manba_id__in=self.filters.source_ids)
        if self.group_scope_restricted and not self.group_scope_ids:
            return qs.none()
        if self.group_ids or self.filters.teacher_ids or self.filters.category_ids:
            lead_group_filter = Q()
            if self.group_ids:
                lead_group_filter |= Q(trial_lessons__group_id__in=self.group_ids)
                lead_group_filter |= Q(converted_user__enrollments__group_id__in=self.group_ids)
            if self.filters.teacher_ids:
                lead_group_filter |= Q(trial_lessons__teacher_id__in=self.filters.teacher_ids)
                lead_group_filter |= Q(converted_user__enrollments__group__oqituvchi_id__in=self.filters.teacher_ids)
            if self.filters.category_ids:
                lead_group_filter |= Q(trial_lessons__group__category_obj_id__in=self.filters.category_ids)
                lead_group_filter |= Q(converted_user__enrollments__group__category_obj_id__in=self.filters.category_ids)
            qs = qs.filter(lead_group_filter).distinct()
        return qs

    def _build_payment_scope(self, start_date: date, end_date: date):
        qs = Payment.objects.filter(center=self.center, paid_date__range=(start_date, end_date))
        qs = self._scope_students(qs)
        qs = self._scope_groups(qs)
        if self.filters.payment_types:
            qs = qs.filter(payment_type__in=self.filters.payment_types)
        return qs

    def _build_debt_snapshot(self, scoped_student_ids: set[int]):
        scoped_group_ids = set(self.group_scope_ids)
        if not scoped_group_ids:
            return {
                "enrollments": [],
                "enrollment_open_debt": {},
                "open_months_by_enrollment": {},
                "student_open_debt": {},
                "group_open_debt": {},
                "group_debtors": {},
                "aging": {"0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0},
                "payment_discipline_by_group": {},
                "top_debtors": [],
            }

        enrollments = list(
            Enrollment.objects.filter(
                center=self.center,
                is_active=True,
                group__is_archived=False,
                created_at__date__lte=self.snapshot_date,
                group_id__in=scoped_group_ids,
            )
            .select_related("group", "student")
            .order_by("group_id", "student_id", "id")
        )

        if self.student_scope_restricted:
            enrollments = [enrollment for enrollment in enrollments if enrollment.student_id in scoped_student_ids]

        enrollment_ids = [enrollment.id for enrollment in enrollments]
        tuition_rows = list(
            TuitionMonth.objects.filter(
                enrollment_id__in=enrollment_ids,
                month__lte=self.snapshot_month,
            )
            .order_by("enrollment_id", "month")
            .values("id", "enrollment_id", "month", "fee_amount")
        )
        tuition_ids = [row["id"] for row in tuition_rows]

        allocation_rows = list(
            PaymentAllocation.objects.filter(
                tuition_month_id__in=tuition_ids,
                payment__paid_date__lte=self.snapshot_date,
            ).values("tuition_month_id", "amount")
        )

        payment_totals_by_enrollment = dict(
            Payment.objects.filter(
                enrollment_id__in=enrollment_ids,
                paid_date__lte=self.snapshot_date,
            )
            .values("enrollment_id")
            .annotate(total=Sum("summa"))
            .values_list("enrollment_id", "total")
        )

        allocations_by_month = defaultdict(int)
        for row in allocation_rows:
            allocations_by_month[row["tuition_month_id"]] += int(row["amount"] or 0)

        months_by_enrollment: dict[int, list[dict]] = defaultdict(list)
        for row in tuition_rows:
            months_by_enrollment[row["enrollment_id"]].append(
                {
                    "month": row["month"],
                    "fee": int(row["fee_amount"] or 0),
                    "paid": allocations_by_month.get(row["id"], 0),
                }
            )

        student_open_debt = defaultdict(int)
        group_open_debt = defaultdict(int)
        debtors_by_group = defaultdict(int)
        aging = {"0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        enrollment_open_debt: dict[int, int] = {}
        open_months_by_enrollment: dict[int, int] = {}
        payment_discipline_by_group = defaultdict(lambda: {"debtors": 0, "students": 0})

        for enrollment in enrollments:
            months = months_by_enrollment.get(enrollment.id, [])
            if not months:
                months = [{"month": self.snapshot_month, "fee": int(enrollment.kurs_narhi or 0), "paid": 0}]

            has_real_allocations = any(month["paid"] > 0 for month in months)
            if has_real_allocations:
                month_balances = [(month["month"], max(month["fee"] - month["paid"], 0)) for month in months]
            else:
                remaining_paid = int(payment_totals_by_enrollment.get(enrollment.id, 0) or 0)
                month_balances = []
                for month in months:
                    fee = int(month["fee"] or 0)
                    covered = min(fee, remaining_paid)
                    remaining_paid = max(remaining_paid - covered, 0)
                    month_balances.append((month["month"], max(fee - covered, 0)))

            enrollment_debt = sum(balance for _, balance in month_balances)
            enrollment_open_debt[enrollment.id] = int(enrollment_debt)
            open_months_by_enrollment[enrollment.id] = sum(1 for _, balance in month_balances if balance > 0)

            payment_discipline_by_group[enrollment.group_id]["students"] += 1
            if enrollment_debt > 0:
                payment_discipline_by_group[enrollment.group_id]["debtors"] += 1
                student_open_debt[enrollment.student_id] += int(enrollment_debt)
                group_open_debt[enrollment.group_id] += int(enrollment_debt)
                debtors_by_group[enrollment.group_id] += 1

            for month_value, balance in month_balances:
                if balance <= 0:
                    continue
                age_days = (self.snapshot_date - month_value).days
                if age_days <= 30:
                    aging["0_30"] += int(balance)
                elif age_days <= 60:
                    aging["31_60"] += int(balance)
                elif age_days <= 90:
                    aging["61_90"] += int(balance)
                else:
                    aging["90_plus"] += int(balance)

        top_debtors = []
        student_name_map = {
            user.id: user.get_full_name() or user.email
            for user in self.all_students_qs.filter(id__in=student_open_debt.keys())
        }
        for student_id, total_debt in sorted(student_open_debt.items(), key=lambda item: item[1], reverse=True)[:10]:
            student_groups = sorted(
                {
                    enrollment.group.nom
                    for enrollment in enrollments
                    if enrollment.student_id == student_id and enrollment_open_debt.get(enrollment.id, 0) > 0
                }
            )
            top_debtors.append(
                {
                    "student_id": student_id,
                    "student_name": student_name_map.get(student_id, "Noma'lum"),
                    "debt": int(total_debt),
                    "groups": student_groups,
                }
            )

        return {
            "enrollments": enrollments,
            "enrollment_open_debt": enrollment_open_debt,
            "open_months_by_enrollment": open_months_by_enrollment,
            "student_open_debt": dict(student_open_debt),
            "group_open_debt": dict(group_open_debt),
            "group_debtors": dict(debtors_by_group),
            "aging": aging,
            "payment_discipline_by_group": dict(payment_discipline_by_group),
            "top_debtors": top_debtors,
        }

    def _build_filter_options(self):
        categories = list(
            Category.objects.filter(center=self.center, is_deleted=False).order_by("name").values("id", "name")
        )
        groups = [
            {"id": group.id, "name": group.nom}
            for group in Group.objects.filter(center=self.center, is_archived=False).order_by("nom")
        ]
        teachers = [
            {"id": teacher.id, "name": teacher.get_full_name() or teacher.email}
            for teacher in self.teachers_qs.order_by("ism", "familya")
        ]
        sources = list(Manba.objects.filter(center=self.center).order_by("nom").values("id", "nom"))
        return {
            "branches": [{"id": self.center.id, "name": self.center.name}],
            "categories": categories,
            "groups": groups,
            "teachers": teachers,
            "sources": [{"id": row["id"], "name": row["nom"]} for row in sources],
            "payment_types": [{"id": key, "name": value} for key, value in PAYMENT_TYPE_LABELS.items()],
            "student_cycles": [
                {"id": "all", "name": "Barchasi"},
                {"id": "new", "name": "Yangi"},
                {"id": "returning", "name": "Qayta"},
            ],
            "student_statuses": [
                {"id": "all", "name": "Barchasi"},
                {"id": "active", "name": "Aktiv"},
                {"id": "inactive", "name": "Noaktiv"},
                {"id": "dropped", "name": "Tark etgan"},
            ],
            "debt_statuses": [
                {"id": "all", "name": "Barchasi"},
                {"id": "debtor", "name": "Qarzdor"},
                {"id": "clear", "name": "Qarzsiz"},
            ],
        }

    def _build_plans_stats(self, finance_summary, student_summary, marketing_summary):
        configured_targets = ((self.center.features or {}).get("dashboard_targets") or {})

        rolling_income = list(
            Payment.objects.filter(center=self.center)
            .annotate(bucket=TruncMonth("paid_date"))
            .values("bucket")
            .annotate(total=Sum("summa"))
            .order_by("-bucket")[:3]
        )
        avg_recent_income = round(sum(int(row["total"] or 0) for row in rolling_income) / len(rolling_income), 0) if rolling_income else 0
        benchmark_income = max(
            int(finance_summary["income_previous"] or 0),
            int(avg_recent_income or 0),
            int(finance_summary["income"] or 0),
            1,
        )
        benchmark_students = max(
            int(student_summary["active_students_previous"] or 0),
            int(student_summary["active_students"] or 0),
            max(round(self.center.effective_student_limit * 0.8), 1),
        )
        benchmark_leads = max(
            int(marketing_summary["total_leads_previous"] or 0),
            int(marketing_summary["total_leads"] or 0),
            1,
        )

        def stat(current: int, configured_key: str, benchmark_value: int):
            configured = configured_targets.get(configured_key)
            mode = "configured" if configured else "benchmark"
            target = int(configured or benchmark_value or 1)
            return {
                "mode": mode,
                "target": target,
                "current": int(current or 0),
                "pct": min(round(percent(current, target)), 100) if target else 0,
                "rem": max(target - int(current or 0), 0),
            }

        return {
            "finance": stat(finance_summary["income"], "income", benchmark_income),
            "students": stat(student_summary["active_students"], "active_students", benchmark_students),
            "marketing": stat(marketing_summary["total_leads"], "leads", benchmark_leads),
        }

    def _bucket_labels(self, start: date, end: date):
        use_daily = (end - start).days <= 45
        bucket_fn = TruncDay if use_daily else TruncMonth
        labels: list[str] = []
        cursor = start
        if use_daily:
            while cursor <= end:
                labels.append(cursor.strftime("%d.%m"))
                cursor += timedelta(days=1)
        else:
            cursor = month_start(start)
            end_month = month_start(end)
            while cursor <= end_month:
                labels.append(cursor.strftime("%b %Y"))
                if cursor.month == 12:
                    cursor = cursor.replace(year=cursor.year + 1, month=1)
                else:
                    cursor = cursor.replace(month=cursor.month + 1)
        return use_daily, bucket_fn, labels

    def _build_finance_and_charts(self):
        filters = self.filters
        period_income = int(self.payments_period_qs.aggregate(total=Sum("summa"))["total"] or 0)
        previous_income = int(self.payments_previous_qs.aggregate(total=Sum("summa"))["total"] or 0)

        student_revenue_share = safe_div(self.filtered_active_students, self.total_center_active_students or 1)
        if student_revenue_share <= 0 and period_income:
            total_unfiltered_period_income = int(
                Payment.objects.filter(center=self.center, paid_date__range=(filters.date_from, filters.date_to)).aggregate(
                    total=Sum("summa")
                )["total"]
                or 0
            )
            student_revenue_share = safe_div(period_income, total_unfiltered_period_income or 1)

        has_slice_filters = any(
            [
                self.filters.category_ids,
                self.filters.group_ids,
                self.filters.teacher_ids,
                self.filters.source_ids,
                self.filters.student_cycle != "all",
                self.filters.student_status != "all",
                self.filters.debt_status != "all",
            ]
        )
        allocated_operating_expense = (
            round(self.actual_operating_expense * student_revenue_share) if has_slice_filters else self.actual_operating_expense
        )
        allocated_operating_expense_previous = (
            round(self.actual_operating_expense_previous * student_revenue_share)
            if has_slice_filters
            else self.actual_operating_expense_previous
        )

        teacher_cost_period = 0
        teacher_cost_previous = 0
        group_attendance_cost = defaultdict(int)
        group_attendance_cost_previous = defaultdict(int)

        def attendance_cost(range_start: date, range_end: date, store):
            rows = (
                self._scope_groups(
                    Attendance.objects.filter(
                        center=self.center,
                        date__range=(range_start, range_end),
                    )
                )
                .filter(Q(present=True) | Q(forced=True) | Q(status="present"))
                .values("group_id", "student_id")
                .annotate(count=Count("id"))
            )
            total_cost = 0
            for row in rows:
                if self.student_scope_restricted and row["student_id"] not in self.student_scope_ids:
                    continue
                group = self.group_map.get(row["group_id"])
                if not group:
                    continue
                lesson_cost = float(group.dars_boshiga_tolov())
                amount = round(row["count"] * lesson_cost)
                store[row["group_id"]] += amount
                total_cost += amount
            return total_cost

        teacher_cost_period = attendance_cost(filters.date_from, filters.date_to, group_attendance_cost)
        teacher_cost_previous = attendance_cost(filters.previous_from, filters.previous_to, group_attendance_cost_previous)

        total_expense = int(allocated_operating_expense + teacher_cost_period)
        total_expense_previous = int(allocated_operating_expense_previous + teacher_cost_previous)
        profit = int(period_income - total_expense)
        previous_profit = int(previous_income - total_expense_previous)

        breakdown_by_category = list(
            self.payments_period_qs.values("group__category_obj__name").annotate(total=Sum("summa")).order_by("-total")
        )
        breakdown_by_teacher = list(
            self.payments_period_qs.values("group__oqituvchi__ism", "group__oqituvchi__familya").annotate(
                total=Sum("summa")
            ).order_by("-total")
        )
        breakdown_by_type_raw = list(
            self.payments_period_qs.values("payment_type").annotate(total=Sum("summa")).order_by("-total")
        )
        breakdown_by_type = [
            {"name": PAYMENT_TYPE_LABELS.get(row["payment_type"], row["payment_type"]), "value": int(row["total"] or 0)}
            for row in breakdown_by_type_raw
        ]

        new_revenue = 0
        returning_revenue = 0
        for row in self.payments_period_qs.values("student_id").annotate(total=Sum("summa")):
            first_payment = self.first_payment_map.get(row["student_id"])
            if first_payment and filters.date_from <= first_payment <= filters.date_to:
                new_revenue += int(row["total"] or 0)
            else:
                returning_revenue += int(row["total"] or 0)

        open_debt = sum(self._debt_snapshot["student_open_debt"].get(student_id, 0) for student_id in self.student_scope_ids)
        debtors_count = len(
            [student_id for student_id in self.student_scope_ids if self._debt_snapshot["student_open_debt"].get(student_id, 0) > 0]
        )
        recurring_share = percent(returning_revenue, period_income)
        debt_ratio = percent(open_debt, period_income or 1)
        profit_margin = percent(profit, period_income) if period_income else 0
        income_quality_score = round(
            (
                clamp(recurring_share) * 0.35
                + clamp(100 - debt_ratio) * 0.30
                + clamp(profit_margin + 50, 0, 100) * 0.20
                + clamp(100 - percent(debtors_count, max(self.filtered_active_students, 1))) * 0.15
            ),
            1,
        )

        use_daily, bucket_fn, labels = self._bucket_labels(filters.date_from, filters.date_to)
        payment_rows = list(
            self.payments_period_qs.annotate(bucket=bucket_fn("paid_date"))
            .values("bucket")
            .annotate(total=Sum("summa"))
            .order_by("bucket")
        )
        payment_bucket_map = {}
        for row in payment_rows:
            label = row["bucket"].strftime("%d.%m") if use_daily else row["bucket"].strftime("%b %Y")
            payment_bucket_map[label] = int(row["total"] or 0)

        expense_rows = list(
            Expense.objects.filter(center=self.center, sana__date__range=(filters.date_from, filters.date_to))
            .annotate(bucket=bucket_fn("sana"))
            .values("bucket")
            .annotate(total=Sum("summa"))
            .order_by("bucket")
        )
        expense_bucket_map = {}
        for row in expense_rows:
            label = row["bucket"].strftime("%d.%m") if use_daily else row["bucket"].strftime("%b %Y")
            raw_total = int(row["total"] or 0)
            expense_bucket_map[label] = round(raw_total * student_revenue_share) if has_slice_filters else raw_total

        debt_series = []
        if use_daily:
            debt_series = [int(open_debt) for _ in labels]
        else:
            debt_series = [0 for _ in labels]
            monthly_debt = defaultdict(int)
            for enrollment in self._debt_snapshot["enrollments"]:
                if self.student_scope_restricted and enrollment.student_id not in self.student_scope_ids:
                    continue
                monthly_debt[month_start(filters.date_to).strftime("%b %Y")] += self._debt_snapshot["enrollment_open_debt"].get(
                    enrollment.id, 0
                )
            debt_series = [monthly_debt.get(label, 0) for label in labels]

        cashflow = [payment_bucket_map.get(label, 0) - expense_bucket_map.get(label, 0) for label in labels]

        finance_summary = {
            "income": int(period_income),
            "income_previous": int(previous_income),
            "income_prev_diff": int(period_income - previous_income),
            "income_growth": growth_pct(period_income, previous_income),
            "expense": int(total_expense),
            "operating_expense": int(allocated_operating_expense),
            "teacher_shares": int(teacher_cost_period),
            "profit": int(profit),
            "profit_growth": growth_pct(profit, previous_profit),
            "avg_payment": round(period_income / max(self.payments_period_qs.count(), 1)) if period_income else 0,
            "profit_margin": profit_margin,
            "open_debt": int(open_debt),
            "debt_ratio": debt_ratio,
            "debtors_count": debtors_count,
            "recurring_share": recurring_share,
            "income_quality_score": income_quality_score,
            "expense_mode": "allocated" if has_slice_filters else "actual",
            "debt_aging": {key: int(value) for key, value in self._debt_snapshot["aging"].items()},
            "top_debtors": self._debt_snapshot["top_debtors"],
            "breakdown": {
                "by_category": breakdown_by_category,
                "by_teacher": breakdown_by_teacher,
                "by_type": breakdown_by_type,
                "new_vs_returning": [
                    {"name": "Yangi talabalar", "value": int(new_revenue)},
                    {"name": "Qayta to'lovlar", "value": int(returning_revenue)},
                ],
            },
        }
        chart_payload = {
            "labels": labels,
            "income": [payment_bucket_map.get(label, 0) for label in labels],
            "expenses": [expense_bucket_map.get(label, 0) for label in labels],
            "debt_series": debt_series,
            "cashflow": cashflow,
            "new_students": [],
            "income_students": [],
            "debt_students": [],
        }
        return finance_summary, chart_payload, group_attendance_cost, group_attendance_cost_previous

    def _build_group_and_teacher_metrics(self, finance_summary, group_attendance_cost, group_attendance_cost_previous):
        filters = self.filters
        group_payment_rows = list(
            self.payments_period_qs.values("group_id").annotate(
                revenue=Sum("summa"),
                payments=Count("id"),
                unique_students=Count("student_id", distinct=True),
            )
        )
        group_payment_prev_rows = dict(
            self.payments_previous_qs.values("group_id").annotate(revenue=Sum("summa")).values_list("group_id", "revenue")
        )

        attendance_rows = list(
            self._scope_groups(
                Attendance.objects.filter(
                    center=self.center,
                    date__range=(filters.date_from, filters.date_to),
                )
            )
            .values("group_id")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(present=True) | Q(forced=True) | Q(status="present")),
                days=Count("date", distinct=True),
            )
        )
        recent_start = self.snapshot_date - timedelta(days=29)
        previous_recent_start = self.snapshot_date - timedelta(days=59)
        previous_recent_end = self.snapshot_date - timedelta(days=30)

        recent_attendance_rows = self._attendance_tuple_map(
            self._scope_groups(
                Attendance.objects.filter(
                    center=self.center,
                    date__range=(recent_start, self.snapshot_date),
                )
            )
            .values("group_id")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(present=True) | Q(forced=True) | Q(status="present")),
            )
        )
        previous_attendance_rows = self._attendance_tuple_map(
            self._scope_groups(
                Attendance.objects.filter(
                    center=self.center,
                    date__range=(previous_recent_start, previous_recent_end),
                )
            )
            .values("group_id")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(present=True) | Q(forced=True) | Q(status="present")),
            )
        )

        history_rows = list(
            self._scope_groups(
                StudentGroupHistory.objects.filter(center=self.center),
                field_name="group_id",
            ).values("group_id", "student_id", "start_date", "end_date")
        )
        history_index = defaultdict(list)
        for row in history_rows:
            if self.student_scope_restricted and row["student_id"] not in self.student_scope_ids:
                continue
            history_index[(row["group_id"], row["student_id"])].append((row["start_date"], row["end_date"]))

        def is_active_on(intervals, check_date):
            return any(start <= check_date and (end is None or end >= check_date) for start, end in intervals)

        history_stats = defaultdict(lambda: {"current": 0, "previous": 0, "cohort": 0, "retained": 0})
        for (group_id, student_id), intervals in history_index.items():
            if is_active_on(intervals, self.snapshot_date):
                history_stats[group_id]["current"] += 1
            if is_active_on(intervals, self.previous_snapshot_date):
                history_stats[group_id]["previous"] += 1
            if is_active_on(intervals, filters.date_from):
                history_stats[group_id]["cohort"] += 1
                if is_active_on(intervals, self.snapshot_date):
                    history_stats[group_id]["retained"] += 1

        if not history_rows:
            active_counts = (
                self._scope_students(
                    self._scope_groups(
                        Enrollment.objects.filter(
                            center=self.center,
                            is_active=True,
                            student__is_archived=False,
                            group__is_archived=False,
                        )
                    )
                )
                .values("group_id")
                .annotate(students=Count("student_id", distinct=True))
            )
            for row in active_counts:
                history_stats[row["group_id"]]["current"] = row["students"]

        payment_map = {row["group_id"]: row for row in group_payment_rows}
        attendance_map = {row["group_id"]: row for row in attendance_rows}
        total_operating_expense = finance_summary["operating_expense"]
        total_active = sum(max(history_stats[group.id]["current"], 0) for group in self.group_list) or 1
        default_group_capacity = max(8, round(self.center.effective_student_limit / max(len(self.group_list), 1)))

        group_metrics = []
        teacher_rollup = defaultdict(
            lambda: {
                "teacher_id": None,
                "teacher_name": "Ustoz biriktirilmagan",
                "revenue": 0,
                "soft_profit": 0,
                "teacher_cost": 0,
                "allocated_overhead": 0,
                "students": 0,
                "groups": 0,
                "attendance_total": 0,
                "attendance_present": 0,
                "open_debt": 0,
                "debtors": 0,
                "retained": 0,
                "cohort": 0,
                "health_scores": [],
                "growth_values": [],
            }
        )

        for group in self.group_list:
            payment_data = payment_map.get(group.id, {})
            attendance_data = attendance_map.get(group.id, {})
            active_students = int(history_stats[group.id]["current"] or 0)
            previous_students = int(history_stats[group.id]["previous"] or 0)
            cohort_students = int(history_stats[group.id]["cohort"] or 0)
            retained_students = int(history_stats[group.id]["retained"] or 0)
            revenue = int(payment_data.get("revenue") or 0)
            revenue_prev = int(group_payment_prev_rows.get(group.id) or 0)
            open_debt = int(self._debt_snapshot["group_open_debt"].get(group.id, 0))
            debtors = int(self._debt_snapshot["group_debtors"].get(group.id, 0))
            teacher_cost = int(group_attendance_cost.get(group.id, 0))
            teacher_cost_prev = int(group_attendance_cost_previous.get(group.id, 0))
            attendance_total = int(attendance_data.get("total") or 0)
            attendance_present = int(attendance_data.get("present") or 0)
            attendance_rate = percent(attendance_present, attendance_total) if attendance_total else None
            recent_present, recent_total = recent_attendance_rows.get(group.id, (0, 0))
            prev_present, prev_total = previous_attendance_rows.get(group.id, (0, 0))
            recent_attendance = percent(recent_present, recent_total) if recent_total else None
            previous_attendance = percent(prev_present, prev_total) if prev_total else None
            attendance_trend = (
                round(float(recent_attendance) - float(previous_attendance), 1)
                if recent_attendance is not None and previous_attendance is not None
                else 0.0
            )
            payment_discipline = round(
                100 - percent(
                    self._debt_snapshot["payment_discipline_by_group"].get(group.id, {}).get("debtors", 0),
                    max(self._debt_snapshot["payment_discipline_by_group"].get(group.id, {}).get("students", 0), 1),
                ),
                1,
            )
            retention_rate = percent(retained_students, cohort_students) if cohort_students else 100.0
            fill_rate = percent(active_students, default_group_capacity)
            stability_target_lessons = max(
                round((group.oy_dars_soni or 12) * ((filters.date_to - filters.date_from).days + 1) / 30),
                1,
            )
            schedule_stability = (
                percent(attendance_data.get("days") or 0, stability_target_lessons) if attendance_total else None
            )
            debt_ratio = percent(open_debt, max(revenue, 1))
            soft_profit_before_overhead = revenue - teacher_cost
            allocated_overhead = round(total_operating_expense * safe_div(active_students, total_active))
            soft_profit = int(soft_profit_before_overhead - allocated_overhead)
            soft_profit_margin = percent(soft_profit, max(revenue, 1))
            revenue_growth = growth_pct(revenue, revenue_prev)
            student_growth = growth_pct(active_students, previous_students)
            avg_revenue_per_student = round(revenue / active_students) if active_students else 0

            profit_score = clamp(soft_profit_margin + 50)
            attendance_score = clamp(attendance_rate if attendance_rate is not None else 70)
            debt_score = clamp(100 - debt_ratio)
            fill_score = clamp(fill_rate)
            retention_score = clamp(retention_rate)
            growth_score = clamp(revenue_growth + 50)
            discipline_score = clamp(payment_discipline)
            stability_score = clamp(schedule_stability if schedule_stability is not None else 70)

            health_score = round(
                (
                    profit_score * 0.22
                    + attendance_score * 0.15
                    + debt_score * 0.15
                    + fill_score * 0.10
                    + retention_score * 0.10
                    + growth_score * 0.10
                    + discipline_score * 0.10
                    + stability_score * 0.08
                ),
                1,
            )
            churn_risk = round(
                100
                - (
                    attendance_score * 0.35
                    + retention_score * 0.25
                    + discipline_score * 0.20
                    + clamp(student_growth + 50) * 0.20
                ),
                1,
            )

            health_label = "Strong"
            if health_score < 35:
                health_label = "Close Candidate"
            elif health_score < 50:
                health_label = "Weak"
            elif health_score < 65:
                health_label = "Risky"
            elif health_score < 80:
                health_label = "Stable"

            close_workflow = getattr(group, "closure_workflow", None)
            workflow_status = close_workflow.status if close_workflow else GroupClosureWorkflow.STATUS_OPEN
            primary_action = "Kuzatish kerak"
            action_type = "monitor"
            action_tags: list[str] = []

            if workflow_status == GroupClosureWorkflow.STATUS_CLOSED:
                primary_action = "Yopilgan"
                action_type = "stop"
            elif health_score < 35 and (soft_profit < 0 or active_students < 4 or fill_rate < 45):
                primary_action = "Yopish tavsiya etiladi"
                action_type = "stop"
            elif debt_ratio >= 35:
                primary_action = "Qarzdorlikni yig'ish kerak"
                action_type = "fix"
            elif attendance_rate is not None and attendance_rate < 65 and active_students >= 4:
                primary_action = "Ustoz almashtirish kerak"
                action_type = "fix"
            elif attendance_rate is not None and attendance_rate < 75:
                primary_action = "Davomat ustida ishlash kerak"
                action_type = "fix"
            elif soft_profit_margin < 10 and fill_rate >= 80:
                primary_action = "Narxni qayta ko'rib chiqish kerak"
                action_type = "fix"
            elif fill_rate < 65 and (attendance_rate is None or attendance_rate >= 80) and soft_profit >= 0:
                primary_action = "Reklama kuchaytirilsin"
                action_type = "grow"
            elif health_score >= 75 and fill_rate < 90:
                primary_action = "Potensiali yuqori, e'tibor berilsin"
                action_type = "grow"

            if debt_ratio >= 20:
                action_tags.append("qarz")
            if attendance_rate is not None and attendance_rate < 75:
                action_tags.append("davomat")
            if fill_rate < 65:
                action_tags.append("marketing")
            if soft_profit < 0:
                action_tags.append("foyda")

            metric = {
                "group_id": group.id,
                "group_name": group.nom,
                "teacher_id": group.oqituvchi_id,
                "teacher_name": group.oqituvchi.get_full_name() if group.oqituvchi_id else "Biriktirilmagan",
                "category_name": getattr(group.category_obj, "name", "Noma'lum"),
                "active_students": active_students,
                "attendance_rate": round(attendance_rate, 1) if attendance_rate is not None else None,
                "attendance_trend": attendance_trend,
                "revenue": revenue,
                "revenue_previous": revenue_prev,
                "revenue_growth": round(revenue_growth, 1),
                "open_debt": open_debt,
                "debt_ratio": round(debt_ratio, 1),
                "teacher_cost": teacher_cost,
                "allocated_overhead": allocated_overhead,
                "soft_profit": soft_profit,
                "soft_profit_margin": round(soft_profit_margin, 1),
                "avg_revenue_per_student": int(avg_revenue_per_student),
                "capacity_target": int(default_group_capacity),
                "fill_rate": round(fill_rate, 1),
                "payment_discipline": round(payment_discipline, 1),
                "retention_rate": round(retention_rate, 1),
                "stability_score": round(stability_score, 1),
                "student_growth": round(student_growth, 1),
                "churn_risk": round(churn_risk, 1),
                "health_score": health_score,
                "health_label": health_label,
                "primary_action": primary_action,
                "action_type": action_type,
                "action_tags": action_tags,
                "workflow_status": workflow_status,
            }
            group_metrics.append(metric)

            teacher_key = group.oqituvchi_id or 0
            teacher_bucket = teacher_rollup[teacher_key]
            teacher_bucket["teacher_id"] = group.oqituvchi_id
            teacher_bucket["teacher_name"] = metric["teacher_name"]
            teacher_bucket["revenue"] += revenue
            teacher_bucket["soft_profit"] += soft_profit
            teacher_bucket["teacher_cost"] += teacher_cost
            teacher_bucket["allocated_overhead"] += allocated_overhead
            teacher_bucket["students"] += active_students
            teacher_bucket["groups"] += 1
            teacher_bucket["attendance_total"] += attendance_total
            teacher_bucket["attendance_present"] += attendance_present
            teacher_bucket["open_debt"] += open_debt
            teacher_bucket["debtors"] += debtors
            teacher_bucket["retained"] += retained_students
            teacher_bucket["cohort"] += cohort_students
            teacher_bucket["health_scores"].append(health_score)
            teacher_bucket["growth_values"].append(revenue_growth)

        relevant_groups = []
        for metric in group_metrics:
            if any(
                [
                    metric["revenue"] > 0,
                    metric["open_debt"] > 0,
                    metric["active_students"] > 0,
                    self.filters.group_ids,
                ]
            ):
                relevant_groups.append(metric)
        if not relevant_groups:
            relevant_groups = group_metrics

        relevant_groups.sort(key=lambda item: (-item["health_score"], -item["soft_profit"], -item["revenue"]))
        profit_sorted = sorted(relevant_groups, key=lambda item: item["soft_profit"], reverse=True)
        debt_sorted = sorted(relevant_groups, key=lambda item: item["open_debt"], reverse=True)
        weak_sorted = sorted(relevant_groups, key=lambda item: (item["health_score"], item["soft_profit"]))

        teacher_metrics = []
        for teacher_id, teacher_bucket in teacher_rollup.items():
            attendance_rate = (
                percent(teacher_bucket["attendance_present"], teacher_bucket["attendance_total"])
                if teacher_bucket["attendance_total"]
                else None
            )
            debt_ratio = percent(teacher_bucket["open_debt"], max(teacher_bucket["revenue"], 1))
            retention_rate = percent(teacher_bucket["retained"], teacher_bucket["cohort"]) if teacher_bucket["cohort"] else 100.0
            avg_revenue_per_student = (
                round(teacher_bucket["revenue"] / teacher_bucket["students"]) if teacher_bucket["students"] else 0
            )
            avg_health = round(sum(teacher_bucket["health_scores"]) / len(teacher_bucket["health_scores"]), 1) if teacher_bucket["health_scores"] else 0
            avg_growth = round(sum(teacher_bucket["growth_values"]) / len(teacher_bucket["growth_values"]), 1) if teacher_bucket["growth_values"] else 0
            health_score = round(
                (
                    clamp(avg_health) * 0.40
                    + clamp(attendance_rate if attendance_rate is not None else 70) * 0.20
                    + clamp(100 - debt_ratio) * 0.15
                    + clamp(retention_rate) * 0.15
                    + clamp(avg_growth + 50) * 0.10
                ),
                1,
            )
            teacher_metrics.append(
                {
                    "teacher_id": teacher_bucket["teacher_id"],
                    "teacher_name": teacher_bucket["teacher_name"],
                    "revenue": int(teacher_bucket["revenue"]),
                    "soft_profit": int(teacher_bucket["soft_profit"]),
                    "teacher_cost": int(teacher_bucket["teacher_cost"]),
                    "allocated_overhead": int(teacher_bucket["allocated_overhead"]),
                    "groups": int(teacher_bucket["groups"]),
                    "students": int(teacher_bucket["students"]),
                    "attendance_rate": round(attendance_rate, 1) if attendance_rate is not None else None,
                    "retention_rate": round(retention_rate, 1),
                    "debt_ratio": round(debt_ratio, 1),
                    "churn_risk": round(
                        100
                        - (
                            ((attendance_rate if attendance_rate is not None else 70) * 0.5)
                            + (retention_rate * 0.3)
                            + ((100 - debt_ratio) * 0.2)
                        ),
                        1,
                    ),
                    "avg_revenue_per_student": int(avg_revenue_per_student),
                    "health_score": health_score,
                    "revenue_growth": avg_growth,
                }
            )

        teacher_metrics.sort(key=lambda item: (-item["health_score"], -item["revenue"]))

        teacher_compat = [
            {
                "name": metric["teacher_name"],
                "revenue": metric["revenue"],
                "students": metric["students"],
                "groups": metric["groups"],
                "course": "O'qituvchi",
                "rating": round(metric["health_score"] / 20, 1),
                "img": "",
            }
            for metric in teacher_metrics
        ]
        groups_compat = [
            {"name": metric["group_name"], "revenue": metric["revenue"], "debt": metric["open_debt"]}
            for metric in sorted(relevant_groups, key=lambda item: item["revenue"], reverse=True)
        ]

        group_payload = {
            "total_count": len(relevant_groups),
            "top_5_income": groups_compat[:5],
            "bottom_5_income": list(reversed(sorted(groups_compat, key=lambda item: item["revenue"])[:5])),
            "most_indebted": debt_sorted[0] if debt_sorted else None,
            "plan_fulfillment": 0,
            "profitability": relevant_groups,
            "top_profitable": profit_sorted[:5],
            "least_profitable": sorted(relevant_groups, key=lambda item: item["soft_profit"])[:5],
            "close_candidates": [metric for metric in weak_sorted if metric["primary_action"] == "Yopish tavsiya etiladi"][:5],
            "promotion_candidates": [metric for metric in relevant_groups if metric["primary_action"] in {"Reklama kuchaytirilsin", "Potensiali yuqori, e'tibor berilsin"}][:5],
            "health_summary": {
                "strong": len([metric for metric in relevant_groups if metric["health_label"] == "Strong"]),
                "stable": len([metric for metric in relevant_groups if metric["health_label"] == "Stable"]),
                "risky": len([metric for metric in relevant_groups if metric["health_label"] == "Risky"]),
                "weak": len([metric for metric in relevant_groups if metric["health_label"] == "Weak"]),
                "close_candidate": len([metric for metric in relevant_groups if metric["health_label"] == "Close Candidate"]),
            },
        }
        teacher_payload = {
            "total_count": len(teacher_metrics),
            "best": teacher_compat[:5],
            "low": list(reversed(sorted(teacher_compat, key=lambda item: item["revenue"])[:5])),
            "top": teacher_compat[:3],
            "ranking": teacher_metrics,
            "at_risk": [metric for metric in teacher_metrics if metric["health_score"] < 55][:5],
        }
        return group_payload, teacher_payload

    def _build_student_metrics(self, finance_summary):
        filters = self.filters
        non_archived_scope = self.non_archived_students_qs.filter(id__in=self.student_scope_ids)
        active_student_ids = set(
            self._scope_students(
                Enrollment.objects.filter(
                    center=self.center,
                    is_active=True,
                    student__is_archived=False,
                    group__is_archived=False,
                    created_at__date__lte=self.snapshot_date,
                )
            ).values_list("student_id", flat=True)
        )
        active_students_previous = (
            self._scope_students(
                Enrollment.objects.filter(
                    center=self.center,
                    is_active=True,
                    student__is_archived=False,
                    group__is_archived=False,
                    created_at__date__lte=self.previous_snapshot_date,
                )
            )
            .values("student_id")
            .distinct()
            .count()
        )
        total_students = non_archived_scope.count()
        active_students = len(active_student_ids)
        dropouts = self.archived_students_qs.filter(id__in=self.student_scope_ids).count()
        inactive_students = max(total_students - active_students, 0)

        created_period = non_archived_scope.filter(date_joined__date__range=(filters.date_from, filters.date_to)).count()
        debt_amount = sum(self._debt_snapshot["student_open_debt"].get(student_id, 0) for student_id in self.student_scope_ids)
        debtor_ids = {student_id for student_id in self.student_scope_ids if self._debt_snapshot["student_open_debt"].get(student_id, 0) > 0}
        debtors_count = len(debtor_ids)

        risk_rows = []
        attendance_recent_rows = self._attendance_tuple_map(
            self._scope_students(
                Attendance.objects.filter(
                    center=self.center,
                    date__range=(self.snapshot_date - timedelta(days=29), self.snapshot_date),
                ),
                field_name="student_id",
            )
            .values("student_id")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(present=True) | Q(forced=True) | Q(status="present")),
            ),
            key_field="student_id",
        )
        attendance_prev_rows = self._attendance_tuple_map(
            self._scope_students(
                Attendance.objects.filter(
                    center=self.center,
                    date__range=(self.snapshot_date - timedelta(days=59), self.snapshot_date - timedelta(days=30)),
                ),
                field_name="student_id",
            )
            .values("student_id")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(present=True) | Q(forced=True) | Q(status="present")),
            ),
            key_field="student_id",
        )
        current_group_names = defaultdict(list)
        for enrollment in self._debt_snapshot["enrollments"]:
            if enrollment.student_id in self.student_scope_ids:
                current_group_names[enrollment.student_id].append(enrollment.group.nom)

        for student in self.all_students_qs.filter(id__in=self.student_scope_ids).order_by("ism", "familya"):
            recent_present, recent_total = attendance_recent_rows.get(student.id, (0, 0))
            prev_present, prev_total = attendance_prev_rows.get(student.id, (0, 0))
            recent_pct = percent(recent_present, recent_total) if recent_total else None
            prev_pct = percent(prev_present, prev_total) if prev_total else None
            debt_value = int(self._debt_snapshot["student_open_debt"].get(student.id, 0))
            has_group = bool(current_group_names.get(student.id))
            inactivity_days = (timezone.now() - student.last_login).days if student.last_login else 999
            risk_score = round(
                clamp(
                    (((100 - recent_pct) * 0.45) if recent_pct is not None else 0)
                    + (
                        max(prev_pct - recent_pct, 0) * 0.20
                        if prev_pct is not None and recent_pct is not None
                        else 0
                    )
                    + clamp(percent(debt_value, max(finance_summary["income"], 1))) * 0.20
                    + (0 if has_group else 15)
                    + (10 if inactivity_days > 14 else 0),
                    0,
                    100,
                ),
                1,
            )
            reasons = []
            if recent_pct is not None and recent_pct < 65:
                reasons.append(f"Davomat {recent_pct}%")
            if prev_pct is not None and recent_pct is not None and prev_pct - recent_pct >= 20:
                reasons.append("Davomat keskin pasaygan")
            if debt_value > 0:
                reasons.append("To'lov kechikmoqda")
            if not has_group:
                reasons.append("Guruhsiz")
            if inactivity_days > 14:
                reasons.append("Platformaga kirmagan")
            if not reasons:
                continue
            risk_rows.append(
                {
                    "student_id": student.id,
                    "name": student.get_full_name() or student.email,
                    "course": ", ".join(current_group_names.get(student.id, [])) or "Guruhsiz",
                    "attendance_pct": f"{round(recent_pct)}%" if recent_pct is not None else "Ma'lumot yo'q",
                    "attendance_value": round(recent_pct, 1) if recent_pct is not None else None,
                    "debt": debt_value,
                    "risk_score": risk_score,
                    "reason": ", ".join(reasons[:3]),
                    "status": round(risk_score, 1),
                    "img": "",
                }
            )

        risk_rows.sort(
            key=lambda item: (
                -item["risk_score"],
                -item["debt"],
                item["attendance_value"] if item["attendance_value"] is not None else 101,
            )
        )
        low_activity = risk_rows[:20]
        reengagement = [row for row in risk_rows if row["course"] == "Guruhsiz" or row["risk_score"] >= 70][:20]

        return {
            "total": total_students,
            "active_students": active_students,
            "active_students_previous": active_students_previous,
            "inactive_students": inactive_students,
            "new_count": created_period,
            "growth": active_students - active_students_previous,
            "growth_pct": growth_pct(active_students, active_students_previous),
            "debt_amount": int(debt_amount),
            "debtors_count": debtors_count,
            "low_activity": low_activity,
            "risk_students": risk_rows[:50],
            "reengagement_candidates": reengagement,
            "dropouts": dropouts,
        }

    def _build_marketing_metrics(self):
        filters = self.filters
        leads_period = self.relevant_leads_qs.filter(qoshilgan_sana__date__range=(filters.date_from, filters.date_to)).distinct()
        leads_previous = self.relevant_leads_qs.filter(
            qoshilgan_sana__date__range=(filters.previous_from, filters.previous_to)
        ).distinct()

        sources = []
        lead_source_rows = list(
            leads_period.values("manba_id", "manba__nom").annotate(total=Count("id")).order_by("-total")
        )
        for row in lead_source_rows:
            source_leads = leads_period.filter(manba_id=row["manba_id"])
            converted_ids = list(
                source_leads.filter(converted_to_student=True, converted_user_id__isnull=False).values_list(
                    "converted_user_id", flat=True
                )
            )
            trial_scheduled = source_leads.filter(
                Q(trial_lessons__isnull=False) | Q(status__code=LeadStatus.Code.TRIAL_SCHEDULED)
            ).distinct().count()
            trial_attended = source_leads.filter(
                Q(trial_lessons__result_status__in=[TrialLesson.ResultStatus.ATTENDED, TrialLesson.ResultStatus.CONVERTED])
                | Q(status__code__in=[LeadStatus.Code.TRIAL_ATTENDED, LeadStatus.Code.REGISTERED])
            ).distinct().count()
            paid_revenue = int(
                Payment.objects.filter(
                    center=self.center,
                    student_id__in=converted_ids,
                    paid_date__range=(filters.date_from, filters.date_to),
                ).aggregate(total=Sum("summa"))["total"]
                or 0
            )
            active_students = (
                Enrollment.objects.filter(
                    center=self.center,
                    is_active=True,
                    student_id__in=converted_ids,
                    student__is_archived=False,
                    group__is_archived=False,
                    created_at__date__lte=self.snapshot_date,
                )
                .values("student_id")
                .distinct()
                .count()
            )
            conversion = percent(len(set(converted_ids)), max(row["total"], 1))
            source_efficiency = round(
                clamp(conversion * 0.5 + percent(paid_revenue, max(sum(int(r["total"] or 0) for r in lead_source_rows), 1)) * 0.3 + percent(active_students, max(row["total"], 1)) * 0.2),
                1,
            )
            sources.append(
                {
                    "source_id": row["manba_id"],
                    "name": row["manba__nom"] or "Noma'lum",
                    "count": int(row["total"] or 0),
                    "value": int(row["total"] or 0),
                    "conversion": round(conversion, 1),
                    "revenue": paid_revenue,
                    "trial_scheduled": int(trial_scheduled),
                    "trial_attended": int(trial_attended),
                    "active_students": int(active_students),
                    "source_efficiency_score": source_efficiency,
                }
            )

        sources.sort(key=lambda item: (-item["source_efficiency_score"], -item["revenue"], -item["count"]))
        total_leads = leads_period.count()
        total_leads_previous = leads_previous.count()
        contacted = leads_period.filter(
            Q(status__code__in=[LeadStatus.Code.CONTACTED, LeadStatus.Code.TRIAL_SCHEDULED, LeadStatus.Code.TRIAL_ATTENDED, LeadStatus.Code.REGISTERED])
            | Q(activities__action__in=["status_changed", "trial_scheduled", "converted"])
        ).distinct().count()
        trial_scheduled = leads_period.filter(
            Q(trial_lessons__isnull=False) | Q(status__code=LeadStatus.Code.TRIAL_SCHEDULED)
        ).distinct().count()
        trial_attended = leads_period.filter(
            Q(trial_lessons__result_status__in=[TrialLesson.ResultStatus.ATTENDED, TrialLesson.ResultStatus.CONVERTED])
            | Q(status__code__in=[LeadStatus.Code.TRIAL_ATTENDED, LeadStatus.Code.REGISTERED])
        ).distinct().count()
        paid_students = leads_period.filter(converted_to_student=True, converted_user_id__isnull=False).distinct().count()
        active_students = (
            Enrollment.objects.filter(
                center=self.center,
                is_active=True,
                student__is_archived=False,
                group__is_archived=False,
                student_id__in=leads_period.filter(converted_user_id__isnull=False).values("converted_user_id"),
                created_at__date__lte=self.snapshot_date,
            )
            .values("student_id")
            .distinct()
            .count()
        )

        funnel = [
            {"stage": "Lid", "count": total_leads},
            {"stage": "Bog'lanildi", "count": contacted},
            {"stage": "Sinov dars", "count": trial_scheduled},
            {"stage": "Qatnashdi", "count": trial_attended},
            {"stage": "To'lov qildi", "count": paid_students},
            {"stage": "Faol o'quvchi", "count": active_students},
        ]

        best_source = sources[0] if sources else None
        worst_source = sources[-1] if sources else None
        return {
            "sources": sources,
            "funnel": funnel,
            "total_leads": total_leads,
            "total_leads_previous": total_leads_previous,
            "paid_students": paid_students,
            "active_students": active_students,
            "conversion_rate": round(percent(active_students, max(total_leads, 1)), 1),
            "best_source": best_source,
            "worst_source": worst_source,
            "cac": None,
        }

    def _build_insights(self, finance_summary, group_payload, teacher_payload, marketing_payload, student_summary):
        insights = []
        top_profitable = group_payload["top_profitable"][0] if group_payload["top_profitable"] else None
        close_candidate = group_payload["close_candidates"][0] if group_payload["close_candidates"] else None
        risky_teacher = teacher_payload["at_risk"][0] if teacher_payload["at_risk"] else None
        best_source = marketing_payload.get("best_source")
        worst_source = marketing_payload.get("worst_source")

        if finance_summary["income_growth"] >= 0:
            driver = top_profitable["group_name"] if top_profitable else "asosiy guruhlar"
            insights.append(
                {
                    "severity": "low",
                    "action_type": "grow",
                    "title": "Daromad ijobiy trendda",
                    "text": f"Daromad oldingi davrga nisbatan {abs(finance_summary['income_growth'])}% oshdi. O'sishga eng katta hissa {driver} tomonidan qo'shilgan.",
                }
            )
        else:
            insights.append(
                {
                    "severity": "high",
                    "action_type": "fix",
                    "title": "Daromad pasaydi",
                    "text": f"Daromad oldingi davrga nisbatan {abs(finance_summary['income_growth'])}% kamaydi. Qaysi guruh va qaysi kanal tushib ketganini birinchi navbatda tekshirish kerak.",
                }
            )

        if finance_summary["debt_ratio"] >= 20:
            insights.append(
                {
                    "severity": "critical" if finance_summary["debt_ratio"] >= 35 else "high",
                    "action_type": "fix",
                    "title": "Qarzdorlik xavfi oshgan",
                    "text": f"Ochiq qarz {finance_summary['open_debt']:,} so'm. Qarzdorlik darajasi daromadga nisbatan {finance_summary['debt_ratio']}% bo'lib, undirish jarayonini kuchaytirish kerak.",
                }
            )

        if close_candidate:
            insights.append(
                {
                    "severity": "high",
                    "action_type": "stop",
                    "title": f"{close_candidate['group_name']} yopish nomzodi",
                    "text": f"Guruh holat bahosi {close_candidate['health_score']}, sof foyda {close_candidate['soft_profit']:,} so'm. Faol o'quvchi kam va rentabellik past.",
                }
            )

        if top_profitable and top_profitable["fill_rate"] < 70 and (
            top_profitable["attendance_rate"] is None or top_profitable["attendance_rate"] >= 80
        ):
            insights.append(
                {
                    "severity": "medium",
                    "action_type": "grow",
                    "title": f"{top_profitable['group_name']} o'sish uchun tayyor",
                    "text": f"Guruh sof foyda bo'yicha kuchli, davomat {top_profitable['attendance_rate']}%, lekin sig'im bandligi {top_profitable['fill_rate']}%. Reklama yoki tavsiyalar oqimini shu guruhga yo'naltirish foydali.",
                }
            )

        if risky_teacher:
            attendance_note = (
                f"{risky_teacher['attendance_rate']}%"
                if risky_teacher["attendance_rate"] is not None
                else "Ma'lumot yo'q"
            )
            insights.append(
                {
                    "severity": "medium",
                    "action_type": "monitor",
                    "title": f"{risky_teacher['teacher_name']} kuzatuvga tushdi",
                    "text": f"O'qituvchi holat bahosi {risky_teacher['health_score']}. Davomat {attendance_note} va qarz ulushi {risky_teacher['debt_ratio']}% bo'lgani uchun mentorlik yoki guruh tahlili kerak.",
                }
            )

        if best_source and worst_source and best_source["source_id"] != worst_source["source_id"]:
            insights.append(
                {
                    "severity": "medium",
                    "action_type": "grow",
                    "title": "Lid manbalari samaradorligi farqli",
                    "text": f"{best_source['name']} eng yaxshi ishlayapti: konversiya {best_source['conversion']}%, daromad {best_source['revenue']:,} so'm. {worst_source['name']} esa past samarada qolgan.",
                }
            )

        if student_summary["risk_students"]:
            most_risky = student_summary["risk_students"][0]
            insights.append(
                {
                    "severity": "high" if most_risky["risk_score"] >= 75 else "medium",
                    "action_type": "fix",
                    "title": f"{most_risky['name']} xavf zonada",
                    "text": f"Xavf bahosi {most_risky['risk_score']}. Sabab: {most_risky['reason']}. Tark etishni oldini olish uchun individual qayta aloqa tavsiya etiladi.",
                }
            )

        insights.sort(key=lambda item: (-INSIGHT_SEVERITY_ORDER[item["severity"]], item["title"]))
        return insights[:7]

    def _build_executive_summary(
        self,
        *,
        finance_summary: dict,
        group_payload: dict,
        teacher_payload: dict,
        marketing_payload: dict,
        student_summary: dict,
    ) -> dict:
        today_income = int(self._build_payment_scope(self.today, self.today).aggregate(total=Sum("summa"))["total"] or 0)
        today_new_students = self._scope_students(
            self.non_archived_students_qs.filter(date_joined__date=self.today),
            field_name="id",
        ).count()
        today_leads = self.relevant_leads_qs.filter(qoshilgan_sana__date=self.today).distinct().count()
        high_risk_students = len([row for row in student_summary["risk_students"] if row["risk_score"] >= 70])
        risky_groups = len(
            [
                row
                for row in group_payload["profitability"]
                if row["health_label"] in {"Risky", "Weak", "Close Candidate"}
            ]
        )
        risky_teachers = len([row for row in teacher_payload["ranking"] if row["health_score"] < 60])
        promotion_groups = len(group_payload.get("promotion_candidates") or [])

        signal_window_days = 21
        recent_start = self.snapshot_date - timedelta(days=signal_window_days - 1)
        previous_end = recent_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=signal_window_days - 1)

        recent_attendance = self._attendance_rate_for_range(recent_start, self.snapshot_date)
        previous_attendance = self._attendance_rate_for_range(previous_start, previous_end)
        attendance_diff = (
            round(float(recent_attendance) - float(previous_attendance), 1)
            if recent_attendance is not None and previous_attendance is not None
            else None
        )

        best_source = marketing_payload.get("best_source")
        close_candidate = group_payload["close_candidates"][0] if group_payload["close_candidates"] else None
        top_risk_student = student_summary["risk_students"][0] if student_summary["risk_students"] else None

        trend_signal = {
            "tone": "neutral",
            "title": "Holat barqaror",
            "text": "Asosiy ko'rsatkichlar keskin og'ishsiz ishlayapti. Rentabellik va davomat dinamikasini reja asosida kuzatishda davom eting.",
            "chips": [],
        }

        if attendance_diff is not None and attendance_diff <= -4:
            trend_signal = {
                "tone": "warning",
                "title": "Davomat pasaymoqda",
                "text": f"Oxirgi {signal_window_days} kunlik davomat oldingi {signal_window_days} kunga nisbatan {abs(attendance_diff)} punktga pasaydi. Guruh va ustozlar kesimida zudlik bilan tekshiruv kerak.",
                "chips": [
                    {"label": "Joriy davomat", "value": recent_attendance, "kind": "pct"},
                    {"label": "Oldingi davr", "value": previous_attendance, "kind": "pct"},
                    {"label": "Xavfli guruhlar", "value": risky_groups, "kind": "number"},
                ],
            }
        elif finance_summary["debt_ratio"] >= 20:
            trend_signal = {
                "tone": "danger",
                "title": "Qarzdorlik bosimi oshgan",
                "text": f"Ochiq qarz daromadga nisbatan {finance_summary['debt_ratio']}% ga yetgan. Undirish oqimi va to'lov intizomini kuchaytirish kerak.",
                "chips": [
                    {"label": "Ochiq qarz", "value": finance_summary["open_debt"], "kind": "money"},
                    {"label": "Qarzdorlar", "value": finance_summary["debtors_count"], "kind": "number"},
                    {"label": "Qayta to'lov ulushi", "value": finance_summary["recurring_share"], "kind": "pct"},
                ],
            }
        elif finance_summary["income_growth"] >= 10 and promotion_groups:
            trend_signal = {
                "tone": "success",
                "title": "Daromad o'sish rejimida",
                "text": f"Daromad oldingi davrga nisbatan {finance_summary['income_growth']}% oshdi. O'sishni kuchaytirish uchun sig'imi to'lmagan kuchli guruhlarni reklama bilan to'ldirish mumkin.",
                "chips": [
                    {"label": "Daromad o'sishi", "value": finance_summary["income_growth"], "kind": "pct_signed"},
                    {"label": "O'sishga tayyor guruhlar", "value": promotion_groups, "kind": "number"},
                    {"label": "Foyda marjasi", "value": finance_summary["profit_margin"], "kind": "pct"},
                ],
            }
        elif best_source:
            trend_signal = {
                "tone": "info",
                "title": "Marketingda aniq lider bor",
                "text": f"{best_source['name']} hozir eng samarali manba. Shu kanalga ko'proq budjet yoki tezkor qayta aloqani yo'naltirish foyda beradi.",
                "chips": [
                    {"label": "Konversiya", "value": best_source["conversion"], "kind": "pct"},
                    {"label": "Daromad", "value": best_source["revenue"], "kind": "money"},
                    {"label": "Faol o'quvchi", "value": best_source["active_students"], "kind": "number"},
                ],
            }
        elif close_candidate:
            trend_signal = {
                "tone": "warning",
                "title": f"{close_candidate['group_name']} kuzatuv markazida",
                "text": f"Guruh holat bahosi {close_candidate['health_score']}. Rentabellik pasaygan va sig'im yetarli to'lmagan. Qisqa muddatli tuzatish rejasini ishga tushirish kerak.",
                "chips": [
                    {"label": "Holat bahosi", "value": close_candidate["health_score"], "kind": "number"},
                    {"label": "Sof foyda", "value": close_candidate["soft_profit"], "kind": "money"},
                    {"label": "Davomat", "value": close_candidate["attendance_rate"], "kind": "pct"},
                ],
            }
        elif top_risk_student:
            trend_signal = {
                "tone": "warning",
                "title": "O'quvchi churn xavfi mavjud",
                "text": f"{top_risk_student['name']} eng yuqori xavf qatlamida turibdi. Individual aloqa va to'lov nazoratini kechiktirmaslik kerak.",
                "chips": [
                    {"label": "Risk ball", "value": top_risk_student["risk_score"], "kind": "number"},
                    {"label": "Qarz", "value": top_risk_student["debt"], "kind": "money"},
                    {"label": "Davomat", "value": top_risk_student["attendance_value"], "kind": "pct"},
                ],
            }

        return {
            "today_strip": [
                {
                    "label": "Yangi o'quvchilar",
                    "value": today_new_students,
                    "kind": "number",
                    "detail": "Bugun qo'shilgan",
                    "tone": "info",
                },
                {
                    "label": "Bugungi to'lovlar",
                    "value": today_income,
                    "kind": "money",
                    "detail": "Bugun qabul qilingan tushum",
                    "tone": "success",
                },
                {
                    "label": "Bugungi lidlar",
                    "value": today_leads,
                    "kind": "number",
                    "detail": "Bugungi marketing oqimi",
                    "tone": "accent",
                },
                {
                    "label": "Jiddiy xavf",
                    "value": high_risk_students,
                    "kind": "number",
                    "detail": "Zudlik bilan aloqa kerak",
                    "tone": "warning",
                },
            ],
            "trend_signal": trend_signal,
            "problem_hub": [
                {
                    "label": "Qarzdorlar",
                    "value": finance_summary["debtors_count"],
                    "kind": "number",
                    "detail": finance_summary["open_debt"],
                    "detail_kind": "money",
                    "tone": "danger",
                },
                {
                    "label": "Xavfli guruhlar",
                    "value": risky_groups,
                    "kind": "number",
                    "detail": len(group_payload.get("close_candidates") or []),
                    "detail_kind": "number",
                    "detail_prefix": "Yopish nomzodi",
                    "tone": "warning",
                },
                {
                    "label": "Kuzatuvdagi ustozlar",
                    "value": risky_teachers,
                    "kind": "number",
                    "detail": len(teacher_payload.get("at_risk") or []),
                    "detail_kind": "number",
                    "detail_prefix": "Past baho",
                    "tone": "info",
                },
            ],
        }

    def build(self):
        finance_summary, chart_payload, group_attendance_cost, group_attendance_cost_previous = self._build_finance_and_charts()
        group_payload, teacher_payload = self._build_group_and_teacher_metrics(
            finance_summary,
            group_attendance_cost,
            group_attendance_cost_previous,
        )
        student_summary = self._build_student_metrics(finance_summary)
        marketing_payload = self._build_marketing_metrics()
        chart_payload["marketing"] = marketing_payload["sources"]
        use_daily, bucket_fn, labels = self._bucket_labels(self.filters.date_from, self.filters.date_to)
        new_student_rows = list(
            self._scope_students(
                self.non_archived_students_qs.filter(date_joined__date__range=(self.filters.date_from, self.filters.date_to)),
                field_name="id",
            )
            .annotate(bucket=bucket_fn("date_joined"))
            .values("bucket")
            .annotate(total=Count("id"))
            .order_by("bucket")
        )
        new_student_map = {self._bucket_label(row["bucket"], use_daily): int(row["total"] or 0) for row in new_student_rows}
        paying_student_rows = list(
            self._scope_students(
                Payment.objects.filter(center=self.center, paid_date__range=(self.filters.date_from, self.filters.date_to))
            )
            .annotate(bucket=bucket_fn("paid_date"))
            .values("bucket")
            .annotate(total=Count("student_id", distinct=True))
            .order_by("bucket")
        )
        paying_student_map = {
            self._bucket_label(row["bucket"], use_daily): int(row["total"] or 0) for row in paying_student_rows
        }
        chart_payload["new_students"] = [new_student_map.get(label, 0) for label in labels]
        chart_payload["income_students"] = [paying_student_map.get(label, 0) for label in labels]
        chart_payload["debt_students"] = [student_summary["debtors_count"] for _ in labels]

        plans_payload = self._build_plans_stats(finance_summary, student_summary, marketing_payload)
        insights = self._build_insights(
            finance_summary,
            group_payload,
            teacher_payload,
            marketing_payload,
            student_summary,
        )
        executive_summary = self._build_executive_summary(
            finance_summary=finance_summary,
            group_payload=group_payload,
            teacher_payload=teacher_payload,
            marketing_payload=marketing_payload,
            student_summary=student_summary,
        )

        attention_now = []
        if group_payload["close_candidates"]:
            attention_now.append(
                {
                    "title": "Yopish ehtimoli yuqori guruh",
                    "value": group_payload["close_candidates"][0]["group_name"],
                    "type": "stop",
                    "note": group_payload["close_candidates"][0]["primary_action"],
                }
            )
        if student_summary["debtors_count"]:
            attention_now.append(
                {
                    "title": "Qarz bo'yicha tezkor fokus",
                    "value": f"{student_summary['debtors_count']} talaba",
                    "type": "fix",
                    "note": f"{student_summary['debt_amount']:,} so'm ochiq qarz",
                }
            )
        if marketing_payload["best_source"]:
            attention_now.append(
                {
                    "title": "O'sish uchun eng yaxshi kanal",
                    "value": marketing_payload["best_source"]["name"],
                    "type": "grow",
                    "note": f"Konversiya {marketing_payload['best_source']['conversion']}%",
                }
            )

        scoped_attendance_rate = self._attendance_rate_for_range(self.filters.date_from, self.filters.date_to)

        overview = {
            "focus_items": attention_now[:3],
            "health_summary": group_payload["health_summary"],
            "snapshot": {
                "range_label": PRESET_LABELS.get(self.filters.preset, PRESET_LABELS["custom"]),
                "filter_count": sum(
                    [
                        bool(self.filters.category_ids),
                        bool(self.filters.group_ids),
                        bool(self.filters.teacher_ids),
                        bool(self.filters.payment_types),
                        bool(self.filters.source_ids),
                        self.filters.student_cycle != "all",
                        self.filters.student_status != "all",
                        self.filters.debt_status != "all",
                    ]
                ),
            },
            "kpis": {
                "revenue": finance_summary["income"],
                "net_profit": finance_summary["profit"],
                "open_debt": finance_summary["open_debt"],
                "active_students": student_summary["active_students"],
                "attendance_rate": scoped_attendance_rate,
                "lead_conversion": marketing_payload["conversion_rate"],
            },
        }

        return {
            "filters": {
                "options": self._build_filter_options(),
                "applied": {
                    "preset": self.filters.preset,
                    "date_from": self.filters.date_from.isoformat(),
                    "date_to": self.filters.date_to.isoformat(),
                    "category_ids": list(self.filters.category_ids),
                    "group_ids": list(self.filters.group_ids),
                    "teacher_ids": list(self.filters.teacher_ids),
                    "payment_types": list(self.filters.payment_types),
                    "source_ids": list(self.filters.source_ids),
                    "student_cycle": self.filters.student_cycle,
                    "student_status": self.filters.student_status,
                    "debt_status": self.filters.debt_status,
                    "branch_ids": list(self.filters.branch_ids),
                },
            },
            "overview": overview,
            "finance": finance_summary,
            "students": student_summary,
            "teachers": teacher_payload,
            "groups": group_payload,
            "charts": chart_payload,
            "marketing": marketing_payload,
            "plans": plans_payload,
            "insights": insights,
            "executive": executive_summary,
            "system": {
                "last_updated": timezone.localtime(timezone.now()).strftime("%H:%M:%S"),
                "start_date": self.filters.date_from.isoformat(),
                "end_date": self.filters.date_to.isoformat(),
            },
        }


def build_director_dashboard_payload(*, center: Center, params) -> dict:
    filters = resolve_dashboard_filters(center, params)
    service = DirectorDashboardService(center=center, filters=filters)
    return service.build()
