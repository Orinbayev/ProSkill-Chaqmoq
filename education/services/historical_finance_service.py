import calendar
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.utils import timezone

from education.models import (
    Attendance,
    CenterExpense,
    Enrollment,
    FinancialMonth,
    Group,
    MonthlyFinanceSnapshot,
    Payment,
    PaymentAllocation,
    StudentGroupHistory,
    TeacherSalarySnapshot,
)
from education.services.tuition import (
    reconcile_tuition_month,
    teacher_monthly_financials,
)

try:
    from store.models import Expense
except Exception:  # pragma: no cover - optional app dependency in tests
    Expense = None


class HistoricalFinanceService:
    @staticmethod
    def _billable_attendance_filter():
        return (
            Q(present=True)
            | Q(forced=True)
            | Q(status="present")
            | Q(status="absent_unexcused")
        )

    @staticmethod
    def _month_bounds(year, month):
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        return month_start, month_end

    @staticmethod
    def _teacher_groups(teacher, center=None):
        groups = Group.objects.filter(oqituvchi=teacher, is_archived=False)
        if center:
            groups = groups.filter(center=center)
        return list(
            groups.prefetch_related(
                Prefetch(
                    "enrollments",
                    queryset=Enrollment.all_objects.select_related("student"),
                    to_attr="all_enrollments",
                )
            )
        )

    @staticmethod
    def _history_lookup(group_ids):
        history_lookup = {}
        for row in StudentGroupHistory.objects.filter(group_id__in=group_ids).values(
            "group_id",
            "student_id",
            "start_date",
            "end_date",
        ):
            gid = row["group_id"]
            sid = row["student_id"]
            history_lookup.setdefault(gid, {}).setdefault(sid, []).append(
                (row["start_date"], row["end_date"])
            )
        return history_lookup

    @staticmethod
    def _student_was_in_group(history_lookup, gid, sid, month_start, month_end):
        periods = history_lookup.get(gid, {}).get(sid, [])
        if not periods:
            return None

        today = timezone.localdate()
        for start_date, end_date in periods:
            period_end = end_date or today
            if start_date <= month_end and period_end >= month_start:
                return True
        return False

    @staticmethod
    def _attendance_lookup(group_ids, year, month):
        att_lookup = {}
        rows = (
            Attendance.objects.filter(
                group_id__in=group_ids,
                date__year=year,
                date__month=month,
            )
            .filter(HistoricalFinanceService._billable_attendance_filter())
            .values("group_id", "student_id", "date__day")
        )
        for row in rows:
            gid = row["group_id"]
            sid = row["student_id"]
            att_lookup.setdefault(gid, {}).setdefault(sid, []).append(row["date__day"])
        return att_lookup

    @staticmethod
    def _build_dynamic_teacher_salary(
        teacher, year, month, center=None,
        *, _groups=None, _yearly_att=None, _history=None,
    ):
        groups = _groups if _groups is not None else HistoricalFinanceService._teacher_groups(teacher, center=center)
        group_ids = [group.id for group in groups]
        month_start, month_end = HistoricalFinanceService._month_bounds(year, month)

        if not group_ids:
            return {
                "salary": 0,
                "center_profit": 0,
                "turnover": 0,
                "attendance_count": 0,
                "details": [],
                "daily_breakdown": [0] * 31,
            }

        if _yearly_att is not None:
            att_lookup = {
                gid: _yearly_att.get(gid, {}).get(month, {})
                for gid in group_ids
            }
        else:
            att_lookup = HistoricalFinanceService._attendance_lookup(group_ids, year, month)
        history_lookup = _history if _history is not None else HistoricalFinanceService._history_lookup(group_ids)

        enr_lookup = {}
        for group in groups:
            enr_lookup[group.id] = {
                enrollment.student_id: enrollment
                for enrollment in getattr(group, "all_enrollments", [])
            }

        total_salary = 0
        total_turnover = 0
        total_center_profit = 0
        total_lessons = 0
        daily_breakdown = [0] * 31
        details_map = {}

        for group in groups:
            for student_id, days in att_lookup.get(group.id, {}).items():
                if not days:
                    continue

                enrollment = enr_lookup.get(group.id, {}).get(student_id)
                if enrollment is None:
                    continue

                membership_hit = HistoricalFinanceService._student_was_in_group(
                    history_lookup,
                    group.id,
                    student_id,
                    month_start,
                    month_end,
                )
                if membership_hit is False:
                    continue
                if membership_hit is None:
                    created_at = getattr(enrollment, "created_at", None)
                    created_date = created_at.date() if created_at else None
                    if created_date and created_date > month_end:
                        continue

                financials = teacher_monthly_financials(
                    enrollment,
                    len(days),
                    teacher_percent=getattr(teacher, "oqituvchi_foizi", 0) or None,
                )
                if financials["billable_lessons"] <= 0:
                    continue

                total_salary += financials["teacher_salary"]
                total_turnover += financials["turnover"]
                total_center_profit += financials["center_profit"]
                total_lessons += financials["billable_lessons"]

                group_row = details_map.setdefault(
                    group.id,
                    {
                        "group_id": group.id,
                        "group_name": group.nom,
                        "salary": 0,
                        "center_profit": 0,
                        "turnover": 0,
                        "attendance": 0,
                        "is_lead": True,
                        "fi": int(getattr(group, "oqituvchi_foiz", 0) or 0),
                        "enrollments": [],
                    },
                )
                group_row["salary"] += financials["teacher_salary"]
                group_row["center_profit"] += financials["center_profit"]
                group_row["turnover"] += financials["turnover"]
                group_row["attendance"] += financials["billable_lessons"]

                try:
                    student_name = enrollment.student.get_full_name() or enrollment.student.email
                except Exception:
                    student_name = "Noma'lum"

                group_row["enrollments"].append(
                    {
                        "student_id": student_id,
                        "student_name": student_name,
                        "kurs_narhi": int(getattr(enrollment, "kurs_narhi", 0) or 0),
                        "foiz": int(
                            getattr(teacher, "oqituvchi_foizi", 0)
                            or getattr(enrollment, "oqituvchi_foiz", 0)
                            or 0
                        ),
                        "attended": financials["billable_lessons"],
                        "daromad": financials["teacher_salary"],
                        "markaz_foyda": financials["center_profit"],
                    }
                )

                if financials["billable_lessons"] > 0 and days:
                    base = financials["teacher_salary"] // financials["billable_lessons"]
                    extra = financials["teacher_salary"] - (
                        base * financials["billable_lessons"]
                    )
                    for index, day in enumerate(sorted(days)):
                        day_index = day - 1
                        if 0 <= day_index < 31:
                            daily_breakdown[day_index] += base + (1 if index < extra else 0)

        return {
            "salary": int(total_salary),
            "center_profit": int(total_center_profit),
            "turnover": int(total_turnover),
            "attendance_count": int(total_lessons),
            "details": list(details_map.values()),
            "daily_breakdown": daily_breakdown,
        }

    @staticmethod
    def calculate_teacher_salary(teacher, year, month, center=None):
        fin_month = FinancialMonth.objects.filter(year=year, month=month, is_closed=True)
        if center:
            fin_month = fin_month.filter(center=center)
        fin_month = fin_month.first()

        if fin_month:
            snap = TeacherSalarySnapshot.objects.filter(
                teacher=teacher,
                financial_month=fin_month,
            ).first()
            if snap:
                details_val = snap.details or {}
                breakdown = (
                    details_val.get("breakdown", [])
                    if isinstance(details_val, dict)
                    else (details_val if isinstance(details_val, list) else [])
                )
                daily_breakdown = (
                    details_val.get("daily_breakdown", [0] * 31)
                    if isinstance(details_val, dict)
                    else [0] * 31
                )
                return {
                    "salary": int(snap.salary or 0),
                    "attendance_count": int(snap.attendance_count or 0),
                    "details": breakdown,
                    "daily_breakdown": daily_breakdown,
                    "is_locked": True,
                }
            return {
                "salary": 0,
                "attendance_count": 0,
                "details": [],
                "daily_breakdown": [0] * 31,
                "is_locked": True,
            }

        result = HistoricalFinanceService._build_dynamic_teacher_salary(
            teacher,
            year,
            month,
            center=center,
        )
        result["is_locked"] = False
        return result

    @staticmethod
    def get_yearly_teacher_salary(teacher, year, center=None):
        groups = HistoricalFinanceService._teacher_groups(teacher, center=center)
        group_ids = [group.id for group in groups]

        yearly_att = {}
        if group_ids:
            rows = (
                Attendance.objects.filter(group_id__in=group_ids, date__year=year)
                .filter(HistoricalFinanceService._billable_attendance_filter())
                .values("group_id", "student_id", "date__month", "date__day")
            )
            for row in rows:
                yearly_att.setdefault(row["group_id"], {}).setdefault(
                    row["date__month"], {}
                ).setdefault(row["student_id"], []).append(row["date__day"])

        history = HistoricalFinanceService._history_lookup(group_ids) if group_ids else {}
        stats = HistoricalFinanceService.get_yearly_teacher_stats(
            teacher,
            year,
            center,
            _teacher_groups=groups,
            _yearly_att=yearly_att,
            _history=history,
        )
        return [row["salary"] for row in stats]

    @staticmethod
    def get_yearly_teacher_stats(
        teacher, year, center=None, _closed_months=None, _snapshots=None,
        *, _teacher_groups=None, _yearly_att=None, _history=None,
    ):
        results = [
            {"salary": 0, "center_profit": 0, "turnover": 0, "lessons": 0}
            for _ in range(12)
        ]

        if _closed_months is not None:
            closed_months = _closed_months
        else:
            fin_months = FinancialMonth.objects.filter(year=year, is_closed=True)
            if center:
                fin_months = fin_months.filter(center=center)
            closed_months = {}
            for fin_month in fin_months:
                closed_months[fin_month.month] = fin_month

        if closed_months:
            if _snapshots is not None:
                snapshots = _snapshots
            else:
                snapshots = TeacherSalarySnapshot.objects.filter(
                    teacher=teacher,
                    financial_month__in=closed_months.values(),
                ).select_related("financial_month")
            for snap in snapshots:
                month_index = snap.financial_month.month - 1
                if not 0 <= month_index < 12:
                    continue

                details = []
                if isinstance(snap.details, dict):
                    details = snap.details.get("breakdown", [])
                elif isinstance(snap.details, list):
                    details = snap.details

                results[month_index]["salary"] = int(snap.salary or 0)
                results[month_index]["lessons"] = int(snap.attendance_count or 0)
                results[month_index]["turnover"] = sum(
                    item.get("turnover", 0) for item in details if isinstance(item, dict)
                )
                results[month_index]["center_profit"] = sum(
                    item.get("center_profit", 0)
                    for item in details
                    if isinstance(item, dict)
                )

        for month in range(1, 13):
            if month in closed_months:
                continue
            monthly = HistoricalFinanceService._build_dynamic_teacher_salary(
                teacher,
                year,
                month,
                center=center,
                _groups=_teacher_groups,
                _yearly_att=_yearly_att,
                _history=_history,
            )
            results[month - 1] = {
                "salary": int(monthly["salary"]),
                "center_profit": int(monthly["center_profit"]),
                "turnover": int(monthly["turnover"]),
                "lessons": int(monthly["attendance_count"]),
            }

        return results

    @staticmethod
    def _calculate_salary_dynamic(teacher, year, month, center=None):
        return HistoricalFinanceService._build_dynamic_teacher_salary(
            teacher,
            year,
            month,
            center=center,
        )

    @staticmethod
    def _monthly_income_total(center, month_start, month_end):
        allocated_total = int(
            PaymentAllocation.objects.filter(
                payment__is_deleted=False,
                tuition_month__month=month_start,
            )
            .filter(
                Q(center=center)
                | Q(center__isnull=True, payment__center=center)
                | Q(center__isnull=True, payment__center__isnull=True, tuition_month__center=center)
                | Q(
                    center__isnull=True,
                    payment__center__isnull=True,
                    tuition_month__enrollment__center=center,
                )
            )
            .aggregate(total=Sum("amount"))["total"]
            or 0
        )

        unallocated_total = int(
            Payment.objects.filter(
                is_deleted=False,
                paid_date__range=(month_start, month_end),
                allocations__isnull=True,
            )
            .filter(
                Q(center=center)
                | Q(center__isnull=True, group__center=center)
                | Q(center__isnull=True, student__center=center)
                | Q(center__isnull=True, enrollment__center=center)
            )
            .aggregate(total=Sum("summa"))["total"]
            or 0
        )

        return allocated_total + unallocated_total

    @staticmethod
    def _monthly_expense_total(center, month_start, month_end):
        total = int(
            CenterExpense.objects.filter(
                center=center,
                date__range=(month_start, month_end),
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        if Expense is not None:
            total += int(
                Expense.objects.filter(
                    Q(center=center)
                    | Q(center__isnull=True, worker__center=center)
                    | Q(center__isnull=True, product__center=center),
                    sana__date__range=(month_start, month_end),
                ).aggregate(total=Sum("summa"))["total"]
                or 0
            )

        return total

    @staticmethod
    def _monthly_attendance_rate(center, month_start, month_end):
        summary = (
            Attendance.objects.filter(
                Q(center=center) | Q(center__isnull=True, group__center=center),
                date__range=(month_start, month_end),
            ).aggregate(
                present=Count(
                    "id",
                    filter=Q(status="present") | Q(present=True) | Q(forced=True),
                ),
                total=Count("id"),
            )
        )
        total = int(summary.get("total") or 0)
        present = int(summary.get("present") or 0)
        return round((present / total) * 100, 1) if total else 0.0

    @staticmethod
    def _active_student_count(center):
        return (
            Enrollment.objects.filter(
                is_active=True,
                group__is_archived=False,
            )
            .filter(
                Q(center=center) | Q(center__isnull=True, group__center=center),
            )
            .values("student_id")
            .distinct()
            .count()
        )

    @staticmethod
    @transaction.atomic
    def close_month(center, year, month, user=None):
        if center is None:
            raise ValueError("center bo'sh bo'lishi mumkin emas.")

        fin_month, created = FinancialMonth.objects.get_or_create(
            center=center,
            year=year,
            month=month,
            defaults={"is_closed": False},
        )
        if not created and fin_month.is_closed:
            return fin_month

        month_start, month_end = HistoricalFinanceService._month_bounds(year, month)

        enrollments = (
            Enrollment.objects.filter(
                is_active=True,
                group__is_archived=False,
            )
            .filter(Q(center=center) | Q(center__isnull=True, group__center=center))
            .select_related("group", "student")
        )
        for enrollment in enrollments.iterator():
            reconcile_tuition_month(enrollment, month_start)

        User = get_user_model()
        teachers = User.objects.filter(role="teacher", is_archived=False)
        if center:
            teachers = teachers.filter(center=center)

        snapshots = []
        total_teacher_salary = 0
        for teacher in teachers:
            salary_data = HistoricalFinanceService._calculate_salary_dynamic(
                teacher,
                year,
                month,
                center=center,
            )
            full_details = {
                "breakdown": salary_data["details"],
                "daily_breakdown": salary_data["daily_breakdown"],
            }
            snapshots.append((teacher, salary_data, full_details))
            total_teacher_salary += int(salary_data["salary"] or 0)

        fin_month.is_closed = True
        fin_month.closed_at = timezone.now()
        fin_month.closed_by = user
        fin_month.save(update_fields=["is_closed", "closed_at", "closed_by"])

        for teacher, salary_data, full_details in snapshots:
            TeacherSalarySnapshot.objects.update_or_create(
                teacher=teacher,
                financial_month=fin_month,
                defaults={
                    "salary": int(salary_data["salary"] or 0),
                    "attendance_count": int(salary_data["attendance_count"] or 0),
                    "details": full_details,
                },
            )

        total_income = HistoricalFinanceService._monthly_income_total(
            center,
            month_start,
            month_end,
        )
        total_expense = HistoricalFinanceService._monthly_expense_total(
            center,
            month_start,
            month_end,
        )
        MonthlyFinanceSnapshot.objects.update_or_create(
            financial_month=fin_month,
            defaults={
                "total_income": int(total_income),
                "total_expense": int(total_expense),
                "center_profit": int(total_income - total_expense - total_teacher_salary),
                "student_count": HistoricalFinanceService._active_student_count(center),
                "attendance_rate": HistoricalFinanceService._monthly_attendance_rate(
                    center,
                    month_start,
                    month_end,
                ),
            },
        )
        return fin_month

    @staticmethod
    @transaction.atomic
    def open_month(center, year, month, user=None):
        fin_month = FinancialMonth.objects.filter(
            center=center,
            year=year,
            month=month,
        ).first()
        if fin_month:
            TeacherSalarySnapshot.objects.filter(financial_month=fin_month).delete()
            MonthlyFinanceSnapshot.objects.filter(financial_month=fin_month).delete()
            fin_month.is_closed = False
            fin_month.closed_at = None
            fin_month.closed_by = None
            fin_month.save(update_fields=["is_closed", "closed_at", "closed_by"])
        return fin_month
