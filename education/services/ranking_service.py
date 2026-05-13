from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from education.models import (
    Attendance,
    CenterExamSetting,
    DailyLightningRecord,
    Enrollment,
    ExamResult,
    GroupInternalRankingSnapshot,
    StudentAcademicSummary,
)
from education.services.audit_service import log_education_event

INTERNAL_RANKING_WEIGHTS = {
    "attendance": Decimal("0.35"),
    "activity": Decimal("0.20"),
    "exam": Decimal("0.25"),
    "homework": Decimal("0.05"),
    "discipline": Decimal("0.10"),
    "lightning_bonus": Decimal("0.05"),
}

DEFAULT_ATTENDANCE_THRESHOLD = Decimal("70")
DEFAULT_PASS_RATE_THRESHOLD = Decimal("70")


def _to_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    try:
        if value is None:
            return default
        return Decimal(str(value))
    except Exception:
        return default


def _q(value: Decimal) -> Decimal:
    return _to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp_0_100(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 100:
        return Decimal("100")
    return value


def _normalize_metric(raw_map: dict[int, Decimal], student_ids: list[int], neutral: Decimal = Decimal("50")) -> dict[int, Decimal]:
    if not student_ids:
        return {}

    vals = [raw_map.get(sid, Decimal("0")) for sid in student_ids]
    min_v = min(vals)
    max_v = max(vals)
    if max_v == min_v:
        return {sid: _q(neutral) for sid in student_ids}

    rng = max_v - min_v
    out: dict[int, Decimal] = {}
    for sid in student_ids:
        raw = raw_map.get(sid, Decimal("0"))
        score = ((raw - min_v) / rng) * Decimal("100")
        out[sid] = _q(_clamp_0_100(score))
    return out


def _rank_explanation(*, row: dict) -> str:
    rank = row["rank_position"]
    positives = []
    cautions = []

    attendance = row["attendance_score"]
    exam = row["exam_score"]
    activity = row["activity_score"]
    discipline = row["discipline_score"]

    if attendance >= 85:
        positives.append("davomati juda barqaror")
    elif attendance >= 70:
        positives.append("davomati yaxshi")
    elif attendance < 50:
        cautions.append("davomat ko‘rsatkichi past")

    if exam >= 80:
        positives.append("imtihon natijalari yuqori")
    elif exam >= 60:
        positives.append("imtihon natijalari qoniqarli")
    elif row["exam_count"] > 0:
        cautions.append("imtihon natijalari pastroq")
    else:
        cautions.append("imtihon ma’lumotlari hali kam")

    if activity >= 75:
        positives.append("guruh ichida faol qatnashadi")
    elif activity < 45:
        cautions.append("faollik signalini oshirish kerak")

    if discipline >= 70:
        positives.append("intizom ko‘rsatkichi yaxshi")
    elif discipline < 45:
        cautions.append("intizom signalida pasayish bor")

    lead = f"Ushbu o‘quvchi {rank}-o‘rinda."
    if positives:
        lead += " Asosiy sabablar: " + ", ".join(positives[:3]) + "."
    if cautions:
        lead += " E’tibor kerak bo‘lgan joylar: " + ", ".join(cautions[:2]) + "."
    return lead


def _get_passing_percent(group) -> Decimal:
    settings_obj = CenterExamSetting.objects.filter(center=group.center).only("passing_score_percent").first()
    return _to_decimal(getattr(settings_obj, "passing_score_percent", 60), default=Decimal("60"))


def _has_group_activity_data(*, group, on_date) -> bool:
    """
    Ichki reyting faqat shu guruh ichidagi real faoliyatga tayansin.
    """
    if Attendance.objects.filter(group=group, date__lte=on_date).exists():
        return True
    if ExamResult.objects.filter(group=group, exam_date__lte=on_date).exists():
        return True
    if DailyLightningRecord.objects.filter(
        group=group,
        date__lte=on_date,
    ).filter(Q(plus_points__gt=0) | Q(minus_points__gt=0)).exists():
        return True
    return False


def build_group_internal_ranking(*, group, on_date=None, actor=None, persist: bool = True):
    """
    Faqat bitta guruh ichki reytingini hisoblaydi.
    Global/chaqmoq rankingga aralashmaydi.
    """
    on_date = on_date or timezone.localdate()
    enrollments = list(
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("student")
        .order_by("student__ism", "student__familya", "student__id")
    )
    if not enrollments:
        return []

    student_ids = [e.student_id for e in enrollments]
    if not _has_group_activity_data(group=group, on_date=on_date):
        return []

    total_lessons = (
        Attendance.objects.filter(group=group, date__lte=on_date)
        .values("date")
        .distinct()
        .count()
    )

    attendance_rows = (
        Attendance.objects.filter(group=group, student_id__in=student_ids, date__lte=on_date)
        .values("student_id")
        .annotate(
            present_count=Count(
                "id",
                filter=Q(status="present") | Q(present=True) | Q(forced=True),
            )
        )
    )
    attendance_present_map = {row["student_id"]: int(row["present_count"] or 0) for row in attendance_rows}

    exam_rows = (
        ExamResult.objects.filter(group=group, student_id__in=student_ids, exam_date__lte=on_date)
        .values("student_id")
        .annotate(
            exam_count=Count("id"),
            avg_score=Avg("score"),
            avg_percent=Avg("percent"),
            pass_count=Count("id", filter=Q(passed=True)),
            fail_count=Count("id", filter=Q(passed=False)),
        )
    )
    exam_map = {row["student_id"]: row for row in exam_rows}
    group_has_exam = any(int(row.get("exam_count") or 0) > 0 for row in exam_map.values())

    daily_rows = (
        DailyLightningRecord.objects.filter(group=group, student_id__in=student_ids, date__lte=on_date)
        .values("student_id")
        .annotate(
            plus_total=Coalesce(Sum("plus_points"), 0),
            minus_total=Coalesce(Sum("minus_points"), 0),
        )
    )
    plus_raw_map: dict[int, Decimal] = {}
    discipline_raw_map: dict[int, Decimal] = {}
    for row in daily_rows:
        sid = row["student_id"]
        plus_total = _to_decimal(row.get("plus_total"), default=Decimal("0"))
        minus_total = _to_decimal(row.get("minus_total"), default=Decimal("0"))
        plus_raw_map[sid] = max(Decimal("0"), plus_total)
        discipline_raw_map[sid] = Decimal("-1") * abs(minus_total)

    lightning_raw_map: dict[int, Decimal] = {}
    for row in daily_rows:
        sid = row["student_id"]
        plus_total = _to_decimal(row.get("plus_total"), default=Decimal("0"))
        minus_total = _to_decimal(row.get("minus_total"), default=Decimal("0"))
        lightning_raw_map[sid] = plus_total - minus_total

    activity_score_map = _normalize_metric(plus_raw_map, student_ids)
    discipline_score_map = _normalize_metric(discipline_raw_map, student_ids)
    lightning_bonus_map = _normalize_metric(lightning_raw_map, student_ids)

    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        sid = student.id
        present_count = int(attendance_present_map.get(sid, 0))
        attendance_score = Decimal("50")
        if total_lessons > 0:
            attendance_score = (Decimal(present_count) / Decimal(total_lessons)) * Decimal("100")
        attendance_score = _q(_clamp_0_100(attendance_score))

        exam_stat = exam_map.get(sid, {})
        exam_count = int(exam_stat.get("exam_count") or 0)
        pass_count = int(exam_stat.get("pass_count") or 0)
        fail_count = int(exam_stat.get("fail_count") or 0)
        avg_score = _to_decimal(exam_stat.get("avg_score"), default=Decimal("0")) if exam_count else None
        avg_percent = _to_decimal(exam_stat.get("avg_percent"), default=Decimal("0")) if exam_count else None

        if avg_percent is None:
            if group_has_exam:
                exam_score = Decimal("0")
            else:
                exam_score = Decimal("50")
        else:
            exam_score = _clamp_0_100(avg_percent)
        exam_score = _q(exam_score)

        activity_score = _q(_clamp_0_100(activity_score_map.get(sid, Decimal("50"))))
        discipline_score = _q(_clamp_0_100(discipline_score_map.get(sid, Decimal("50"))))
        lightning_bonus_score = _q(_clamp_0_100(lightning_bonus_map.get(sid, Decimal("50"))))
        homework_score = Decimal("50.00")  # Homework moduli keyingi fazaga tayyor neutral foundation.

        total_score = (
            attendance_score * INTERNAL_RANKING_WEIGHTS["attendance"]
            + activity_score * INTERNAL_RANKING_WEIGHTS["activity"]
            + exam_score * INTERNAL_RANKING_WEIGHTS["exam"]
            + homework_score * INTERNAL_RANKING_WEIGHTS["homework"]
            + discipline_score * INTERNAL_RANKING_WEIGHTS["discipline"]
            + lightning_bonus_score * INTERNAL_RANKING_WEIGHTS["lightning_bonus"]
        )
        total_score = _q(total_score)

        rows.append(
            {
                "center": group.center,
                "group": group,
                "student": student,
                "student_id": sid,
                "student_full_name": student.get_full_name(),
                "snapshot_date": on_date,
                "attendance_score": attendance_score,
                "activity_score": activity_score,
                "exam_score": exam_score,
                "homework_score": homework_score,
                "discipline_score": discipline_score,
                "lightning_bonus_score": lightning_bonus_score,
                "total_internal_score": total_score,
                "attendance_total_lessons": int(total_lessons),
                "attendance_present_lessons": present_count,
                "exam_count": exam_count,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "average_score": _q(avg_score) if avg_score is not None else None,
                "average_percent": _q(avg_percent) if avg_percent is not None else None,
            }
        )

    rows.sort(
        key=lambda item: (
            -item["total_internal_score"],
            -item["attendance_score"],
            -item["exam_score"],
            item["student_full_name"],
        )
    )

    for idx, row in enumerate(rows, start=1):
        row["rank_position"] = idx
        row["explanation_text"] = _rank_explanation(row=row)

    if persist:
        with transaction.atomic():
            for row in rows:
                snapshot, _ = GroupInternalRankingSnapshot.objects.update_or_create(
                    group=group,
                    student=row["student"],
                    snapshot_date=on_date,
                    defaults={
                        "center": group.center,
                        "rank_position": row["rank_position"],
                        "attendance_score": row["attendance_score"],
                        "activity_score": row["activity_score"],
                        "exam_score": row["exam_score"],
                        "homework_score": row["homework_score"],
                        "discipline_score": row["discipline_score"],
                        "lightning_bonus_score": row["lightning_bonus_score"],
                        "total_internal_score": row["total_internal_score"],
                        "explanation_text": row["explanation_text"],
                        "metadata": {
                            "weights": {k: float(v) for k, v in INTERNAL_RANKING_WEIGHTS.items()},
                            "exam_count": row["exam_count"],
                            "pass_count": row["pass_count"],
                            "fail_count": row["fail_count"],
                        },
                        "calculated_by": actor if getattr(actor, "is_authenticated", False) else None,
                    },
                )
                row["snapshot"] = snapshot

        log_education_event(
            center=group.center,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action_type="internal_ranking_recalculated",
            entity=group,
            payload={"group_id": group.id, "snapshot_date": str(on_date), "student_count": len(rows)},
        )

    return rows


def get_group_internal_ranking_preview(*, group, on_date=None, limit: int = 3, actor=None, persist: bool = True):
    on_date = on_date or timezone.localdate()
    limit = max(1, int(limit or 3))
    if not _has_group_activity_data(group=group, on_date=on_date):
        return []
    if persist:
        snapshot_qs = GroupInternalRankingSnapshot.objects.filter(group=group, snapshot_date=on_date).select_related("student")
        if snapshot_qs.count() >= limit:
            return list(snapshot_qs.order_by("rank_position")[:limit])

    rows = build_group_internal_ranking(group=group, on_date=on_date, actor=actor, persist=persist)
    return rows[:limit]


def _recommendation_status(
    *,
    attendance_percent: Decimal,
    average_percent: Decimal | None,
    pass_rate_percent: Decimal,
    exam_count: int,
    passing_percent: Decimal,
    attendance_threshold: Decimal,
    pass_rate_threshold: Decimal,
) -> tuple[str, str]:
    if exam_count <= 0:
        return (
            StudentAcademicSummary.RECOMMENDATION_NEEDS_REVIEW,
            "Imtihon natijalari yetarli emas, qo‘shimcha ko‘rib chiqish kerak.",
        )

    avg_percent = average_percent if average_percent is not None else Decimal("0")
    eligible = (
        attendance_percent >= attendance_threshold
        and avg_percent >= passing_percent
        and pass_rate_percent >= pass_rate_threshold
    )
    if eligible:
        return (
            StudentAcademicSummary.RECOMMENDATION_ELIGIBLE,
            "Davomat va imtihon ko‘rsatkichlari sertifikat tavsiyasi uchun mos.",
        )

    soft_attendance = attendance_threshold * Decimal("0.85")
    soft_exam = passing_percent * Decimal("0.90")
    soft_pass_rate = pass_rate_threshold * Decimal("0.85")
    if attendance_percent >= soft_attendance and avg_percent >= soft_exam and pass_rate_percent >= soft_pass_rate:
        return (
            StudentAcademicSummary.RECOMMENDATION_NEEDS_REVIEW,
            "Ko‘rsatkichlar chegaraga yaqin, manual review tavsiya etiladi.",
        )

    return (
        StudentAcademicSummary.RECOMMENDATION_NOT_ELIGIBLE,
        "Davomat yoki imtihon ko‘rsatkichlari minimal talabdan past.",
    )


def build_group_completion_recommendations(
    *,
    group,
    on_date=None,
    actor=None,
    persist: bool = True,
    attendance_threshold: Decimal = DEFAULT_ATTENDANCE_THRESHOLD,
    pass_rate_threshold: Decimal = DEFAULT_PASS_RATE_THRESHOLD,
):
    on_date = on_date or timezone.localdate()
    attendance_threshold = _to_decimal(attendance_threshold, default=DEFAULT_ATTENDANCE_THRESHOLD)
    pass_rate_threshold = _to_decimal(pass_rate_threshold, default=DEFAULT_PASS_RATE_THRESHOLD)
    passing_percent = _get_passing_percent(group)

    ranking_rows = build_group_internal_ranking(
        group=group,
        on_date=on_date,
        actor=actor,
        persist=persist,
    )

    recommendation_rows = []
    for row in ranking_rows:
        exam_count = int(row.get("exam_count") or 0)
        pass_count = int(row.get("pass_count") or 0)
        fail_count = int(row.get("fail_count") or 0)
        avg_percent = row.get("average_percent")
        avg_score = row.get("average_score")
        attendance_percent = _to_decimal(row["attendance_score"], default=Decimal("0"))
        pass_rate_percent = Decimal("0")
        if exam_count > 0:
            pass_rate_percent = (Decimal(pass_count) / Decimal(exam_count)) * Decimal("100")
        pass_rate_percent = _q(_clamp_0_100(pass_rate_percent))

        status, reason = _recommendation_status(
            attendance_percent=attendance_percent,
            average_percent=avg_percent,
            pass_rate_percent=pass_rate_percent,
            exam_count=exam_count,
            passing_percent=passing_percent,
            attendance_threshold=attendance_threshold,
            pass_rate_threshold=pass_rate_threshold,
        )

        summary_defaults = {
            "center": group.center,
            "exam_count": exam_count,
            "average_score": avg_score,
            "average_percent": avg_percent,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate_percent": pass_rate_percent,
            "attendance_total_lessons": int(row.get("attendance_total_lessons") or 0),
            "attendance_present_lessons": int(row.get("attendance_present_lessons") or 0),
            "attendance_percent": attendance_percent,
            "internal_rank_position": int(row["rank_position"]),
            "internal_rank_score": row["total_internal_score"],
            "completion_recommendation": status,
            "recommendation_reason": reason,
            "ranking_explanation": row.get("explanation_text", ""),
            "metadata": {
                "snapshot_date": str(on_date),
                "passing_percent": float(passing_percent),
                "attendance_threshold": float(attendance_threshold),
                "pass_rate_threshold": float(pass_rate_threshold),
            },
            "calculated_by": actor if getattr(actor, "is_authenticated", False) else None,
        }
        summary_obj = None
        if persist:
            summary_obj, _ = StudentAcademicSummary.objects.update_or_create(
                group=group,
                student=row["student"],
                defaults=summary_defaults,
            )

        recommendation_rows.append(
            {
                **row,
                "pass_rate_percent": pass_rate_percent,
                "completion_recommendation": status,
                "recommendation_reason": reason,
                "summary": summary_obj,
            }
        )

    if persist:
        log_education_event(
            center=group.center,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action_type="group_completion_recommendation_recalculated",
            entity=group,
            payload={"group_id": group.id, "snapshot_date": str(on_date), "student_count": len(recommendation_rows)},
        )

    return {
        "rows": recommendation_rows,
        "thresholds": {
            "attendance_threshold": _q(attendance_threshold),
            "pass_rate_threshold": _q(pass_rate_threshold),
            "passing_percent": _q(passing_percent),
        },
    }


def get_student_academic_summaries(*, student, center=None):
    qs = StudentAcademicSummary.objects.filter(student=student).select_related("group", "center")
    if center:
        qs = qs.filter(center=center)
    return qs.order_by("group__nom")
