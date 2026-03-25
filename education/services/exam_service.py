from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from education.models import (
    Attendance,
    CenterExamSetting,
    Enrollment,
    ExamReminderLog,
    ExamResult,
    ExamResultFile,
    ExamSession,
    ExamSessionTaskFile,
)
from education.services.audit_service import log_education_event

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".doc", ".docx", ".txt"}


def get_or_create_center_exam_settings(center):
    settings_obj, _ = CenterExamSetting.objects.get_or_create(center=center)
    return settings_obj


def get_group_lesson_number(*, group, on_date=None) -> int:
    """
    Guruh bo'yicha qaysi darsga kelganini attendance date count orqali qaytaradi.
    """
    on_date = on_date or timezone.localdate()
    return (
        Attendance.objects.filter(group=group, date__lte=on_date)
        .values("date")
        .distinct()
        .count()
    )


def get_group_exam_sequence_number(group) -> int:
    return (ExamSession.objects.filter(group=group).count() or 0) + 1


def get_exam_session_progress(*, session) -> dict:
    """
    Sessiya bo'yicha qamrov holatini hisoblaydi.
    Eslatma qayta chiqishi shu holatga bog'lanadi.
    """
    active_student_ids = list(
        Enrollment.objects.filter(group=session.group, is_active=True).values_list("student_id", flat=True)
    )
    total_students = len(active_student_ids)
    if total_students <= 0:
        return {
            "total_students": 0,
            "completed_students": 0,
            "pending_students": 0,
            "absent_students": 0,
            "is_completed": False,
        }

    completed_student_ids: set[int] = set()
    absent_student_ids: set[int] = set()
    result_rows = ExamResult.objects.filter(session=session, student_id__in=active_student_ids).only(
        "student_id",
        "score",
        "percent",
        "absent_in_exam",
    )
    for row in result_rows:
        if row.absent_in_exam:
            absent_student_ids.add(row.student_id)
            continue
        if row.score is not None or row.percent is not None:
            completed_student_ids.add(row.student_id)

    pending_students = total_students - len(completed_student_ids)
    return {
        "total_students": total_students,
        "completed_students": len(completed_student_ids),
        "pending_students": max(pending_students, 0),
        "absent_students": len(absent_student_ids),
        "is_completed": total_students > 0 and pending_students <= 0,
    }


def get_exam_reminder_state(*, group, on_date=None):
    on_date = on_date or timezone.localdate()
    settings_obj = get_or_create_center_exam_settings(group.center)

    lesson_number = get_group_lesson_number(group=group, on_date=on_date)
    if not settings_obj.exam_system_enabled:
        return {
            "enabled": False,
            "due": False,
            "lesson_number": lesson_number,
            "settings": settings_obj,
            "reason": "disabled",
        }

    n = int(settings_obj.exam_every_n_lessons or 12)
    if n <= 0 or lesson_number <= 0:
        return {
            "enabled": True,
            "due": False,
            "lesson_number": lesson_number,
            "settings": settings_obj,
            "reason": "not_enough_lessons",
        }

    if lesson_number < n:
        return {
            "enabled": True,
            "due": False,
            "lesson_number": lesson_number,
            "settings": settings_obj,
            "reason": "not_due",
            "target_lesson_number": n,
        }

    max_checkpoint = (lesson_number // n) * n
    for checkpoint in range(n, max_checkpoint + 1, n):
        session = (
            ExamSession.objects.filter(group=group, lesson_number_reference=checkpoint)
            .order_by("-id")
            .first()
        )
        if session is None:
            return {
                "enabled": True,
                "due": True,
                "lesson_number": lesson_number,
                "target_lesson_number": checkpoint,
                "settings": settings_obj,
                "reason": "overdue_checkpoint" if lesson_number > checkpoint else "due_now",
                "is_overdue_checkpoint": lesson_number > checkpoint,
                "existing_session": None,
                "can_skip": True,
            }

        # "No" bosilgan checkpoint keyingi checkpointga o'tadi.
        if session.teacher_decision == ExamSession.DECISION_NO:
            continue

        progress = get_exam_session_progress(session=session)
        if session.teacher_decision == ExamSession.DECISION_LATER:
            return {
                "enabled": True,
                "due": True,
                "lesson_number": lesson_number,
                "target_lesson_number": checkpoint,
                "settings": settings_obj,
                "reason": "deferred_checkpoint",
                "is_overdue_checkpoint": lesson_number > checkpoint,
                "existing_session": session,
                "progress": progress,
                "can_skip": True,
            }

        # "Yes" dan keyin barcha o'quvchilar qamrab olinmaguncha reminder qayta chiqadi.
        if not progress["is_completed"]:
            return {
                "enabled": True,
                "due": True,
                "lesson_number": lesson_number,
                "target_lesson_number": checkpoint,
                "settings": settings_obj,
                "reason": "pending_results",
                "is_overdue_checkpoint": lesson_number > checkpoint,
                "existing_session": session,
                "progress": progress,
                "can_skip": False,
            }

    return {
        "enabled": True,
        "due": False,
        "lesson_number": lesson_number,
        "settings": settings_obj,
        "reason": "not_due",
        "target_lesson_number": max_checkpoint,
    }


def log_exam_reminder_action(*, group, teacher, action: str, attendance_date, note: str = "", metadata=None):
    log = ExamReminderLog.objects.create(
        center=group.center,
        group=group,
        teacher=teacher,
        attendance_date=attendance_date or timezone.localdate(),
        lesson_number_reference=get_group_lesson_number(group=group, on_date=attendance_date),
        action=action,
        note=note or "",
        metadata=metadata or {},
    )
    log_education_event(
        center=group.center,
        actor=teacher,
        action_type="exam_reminder_action",
        entity=log,
        message=f"Eslatma harakati: {action}",
        payload={"group_id": group.id, "action": action},
    )
    return log


@transaction.atomic
def create_or_get_exam_session_from_reminder(
    *,
    group,
    teacher,
    attendance_date=None,
    created_by=None,
    decision_note: str = "",
    lesson_number_reference: int | None = None,
):
    attendance_date = attendance_date or timezone.localdate()
    lesson_number = int(lesson_number_reference or 0)
    if lesson_number <= 0:
        lesson_number = get_group_lesson_number(group=group, on_date=attendance_date)

    session, created = ExamSession.objects.get_or_create(
        center=group.center,
        group=group,
        lesson_number_reference=lesson_number,
        defaults={
            "attendance_date": attendance_date,
            "teacher": teacher if getattr(teacher, "role", "") == "teacher" else group.oqituvchi,
            "exam_date": attendance_date,
            "exam_sequence_number": get_group_exam_sequence_number(group),
            "teacher_decision": ExamSession.DECISION_YES,
            "decision_note": decision_note or "",
            "created_by": created_by,
            "updated_by": created_by,
        },
    )

    if not created:
        update_fields = []
        if session.status == ExamSession.STATUS_CANCELLED:
            session.status = ExamSession.STATUS_DRAFT
            update_fields.append("status")
        if getattr(teacher, "role", "") == "teacher" and session.teacher_id != teacher.id:
            session.teacher = teacher
            update_fields.append("teacher")
        if session.exam_date != attendance_date:
            session.exam_date = attendance_date
            update_fields.append("exam_date")
        if session.attendance_date != attendance_date:
            session.attendance_date = attendance_date
            update_fields.append("attendance_date")
        if session.teacher_decision != ExamSession.DECISION_YES:
            session.teacher_decision = ExamSession.DECISION_YES
            update_fields.append("teacher_decision")
        if decision_note:
            session.decision_note = decision_note
            update_fields.append("decision_note")
        session.updated_by = created_by
        update_fields.append("updated_by")
        update_fields.append("updated_at")
        session.save(update_fields=update_fields)

    log_exam_reminder_action(
        group=group,
        teacher=teacher,
        action=ExamReminderLog.ACTION_YES,
        attendance_date=attendance_date,
        metadata={"session_id": session.id, "created": created},
    )
    return session


@transaction.atomic
def create_or_update_exam_session_decision(
    *,
    group,
    teacher,
    attendance_date=None,
    actor=None,
    decision: str,
    decision_note: str = "",
    lesson_number_reference: int | None = None,
):
    """
    "No" / "Later" qarorlarini checkpointga bog'lab saqlaydi.
    """
    attendance_date = attendance_date or timezone.localdate()
    decision = (decision or "").strip().lower()
    if decision not in {ExamSession.DECISION_NO, ExamSession.DECISION_LATER, ExamSession.DECISION_YES}:
        raise ValueError("Noto'g'ri imtihon qarori.")

    checkpoint = int(lesson_number_reference or 0)
    if checkpoint <= 0:
        checkpoint = get_group_lesson_number(group=group, on_date=attendance_date)

    defaults = {
        "attendance_date": attendance_date,
        "teacher": teacher if getattr(teacher, "role", "") == "teacher" else group.oqituvchi,
        "exam_date": attendance_date,
        "exam_sequence_number": get_group_exam_sequence_number(group),
        "teacher_decision": decision,
        "decision_note": decision_note or "",
        "status": ExamSession.STATUS_CANCELLED if decision == ExamSession.DECISION_NO else ExamSession.STATUS_DRAFT,
        "created_by": actor,
        "updated_by": actor,
    }
    session, created = ExamSession.objects.get_or_create(
        center=group.center,
        group=group,
        lesson_number_reference=checkpoint,
        defaults=defaults,
    )

    if not created:
        update_fields = []
        expected_status = ExamSession.STATUS_CANCELLED if decision == ExamSession.DECISION_NO else ExamSession.STATUS_DRAFT
        if session.status != expected_status:
            session.status = expected_status
            update_fields.append("status")
        if session.teacher_decision != decision:
            session.teacher_decision = decision
            update_fields.append("teacher_decision")
        if session.attendance_date != attendance_date:
            session.attendance_date = attendance_date
            update_fields.append("attendance_date")
        if session.exam_date != attendance_date:
            session.exam_date = attendance_date
            update_fields.append("exam_date")
        if getattr(teacher, "role", "") == "teacher" and session.teacher_id != teacher.id:
            session.teacher = teacher
            update_fields.append("teacher")
        if decision_note is not None:
            normalized_note = decision_note or ""
            if session.decision_note != normalized_note:
                session.decision_note = normalized_note
                update_fields.append("decision_note")
        session.updated_by = actor
        update_fields.append("updated_by")
        update_fields.append("updated_at")
        session.save(update_fields=update_fields)

    return session


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _validate_uploaded_files(*, files, field_name: str):
    for f in files:
        ext = Path(getattr(f, "name", "")).suffix.lower()
        if not ext or ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise ValueError(f"{field_name}: ruxsat etilmagan fayl turi ({ext}).")
        if getattr(f, "size", 0) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"{field_name}: fayl 10MB dan katta bo‘lishi mumkin emas.")


def save_exam_session_task_files(*, session, actor, files: list):
    if not files:
        return 0
    _validate_uploaded_files(files=files, field_name="Task fayli")
    created_count = 0
    for f in files:
        file_obj = ExamSessionTaskFile.objects.create(
            session=session,
            file=f,
            uploaded_by=actor,
        )
        log_education_event(
            center=session.center,
            actor=actor,
            action_type="exam_result_file_uploaded",
            entity=file_obj,
            payload={"session_id": session.id, "file_kind": "session_task"},
        )
        created_count += 1
    return created_count


def _derive_fail_reason(*, absent: bool, passed: bool, percent, passing_percent: Decimal) -> str:
    if passed:
        return ""
    if absent:
        return "Imtihonda qatnashmagan"
    if percent is None:
        return "Foiz/ball to‘liq kiritilmagan"
    return f"O‘tish foizidan past ({percent}% < {passing_percent}%)"


@transaction.atomic
def save_exam_results_batch(*, session, actor, rows: list[dict]):
    """
    rows format:
      {
        "student": User,
        "score": "...",
        "percent": "...",
        "teacher_comment": "...",
        "assignment_description": "...",
        "absent_in_exam": bool,
        "retake_recommended": bool,
        "work_files": [InMemoryUploadedFile...],
        "task_files": [InMemoryUploadedFile...],
      }
    """
    settings_obj = get_or_create_center_exam_settings(session.center)
    passing_percent = Decimal(str(settings_obj.passing_score_percent or 60))

    saved_count = 0
    for row in rows:
        student = row["student"]
        score = _to_decimal(row.get("score"))
        percent = _to_decimal(row.get("percent"))

        if percent is None and score is not None:
            percent = score
        if percent is not None:
            if percent < 0:
                percent = Decimal("0")
            if percent > 100:
                percent = Decimal("100")

        absent = bool(row.get("absent_in_exam"))
        if absent:
            passed = False
        else:
            passed = bool(percent is not None and percent >= passing_percent)
        fail_reason = _derive_fail_reason(
            absent=absent,
            passed=passed,
            percent=percent,
            passing_percent=passing_percent,
        )

        work_files = row.get("work_files") or []
        task_files = row.get("task_files") or []
        if settings_obj.exam_file_upload_enabled:
            _validate_uploaded_files(files=work_files, field_name="Ish fayli")
            _validate_uploaded_files(files=task_files, field_name="Task fayli")
        else:
            work_files = []
            task_files = []

        result, created = ExamResult.objects.get_or_create(
            session=session,
            student=student,
            defaults={
                "center": session.center,
                "group": session.group,
                "teacher": actor if getattr(actor, "role", "") == "teacher" else session.teacher,
                "score": score,
                "percent": percent,
                "passed": passed,
                "teacher_comment": row.get("teacher_comment", "") or "",
                "assignment_description": (
                    row.get("assignment_description", "") or ""
                    if settings_obj.optional_task_upload_prompt_enabled
                    else ""
                ),
                "exam_date": session.exam_date,
                "lesson_number_reference": session.lesson_number_reference,
                "absent_in_exam": absent,
                "retake_recommended": bool(row.get("retake_recommended")),
                "fail_reason": fail_reason,
                "follow_up_status": (
                    ExamResult.FOLLOW_UP_NOT_REQUIRED if passed else ExamResult.FOLLOW_UP_PENDING
                ),
                "follow_up_updated_by": actor if not passed else None,
                "follow_up_updated_at": timezone.now() if not passed else None,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if not created:
            previous_follow_up = result.follow_up_status
            result.center = session.center
            result.group = session.group
            result.teacher = actor if getattr(actor, "role", "") == "teacher" else session.teacher
            result.score = score
            result.percent = percent
            result.passed = passed
            result.teacher_comment = row.get("teacher_comment", "") or ""
            result.assignment_description = (
                row.get("assignment_description", "") or ""
                if settings_obj.optional_task_upload_prompt_enabled
                else ""
            )
            result.exam_date = session.exam_date
            result.lesson_number_reference = session.lesson_number_reference
            result.absent_in_exam = absent
            result.retake_recommended = bool(row.get("retake_recommended"))
            result.fail_reason = fail_reason
            if passed:
                result.follow_up_status = ExamResult.FOLLOW_UP_NOT_REQUIRED
            elif previous_follow_up == ExamResult.FOLLOW_UP_NOT_REQUIRED:
                result.follow_up_status = ExamResult.FOLLOW_UP_PENDING
            if result.follow_up_status != previous_follow_up:
                result.follow_up_updated_by = actor
                result.follow_up_updated_at = timezone.now()
            result.updated_by = actor
            result.save()

        for f in work_files:
            file_obj = ExamResultFile.objects.create(
                result=result,
                file=f,
                file_kind=ExamResultFile.FILE_WORK,
                uploaded_by=actor,
            )
            log_education_event(
                center=session.center,
                actor=actor,
                action_type="exam_result_file_uploaded",
                entity=file_obj,
                payload={"result_id": result.id, "file_kind": ExamResultFile.FILE_WORK},
            )
        for f in task_files:
            file_obj = ExamResultFile.objects.create(
                result=result,
                file=f,
                file_kind=ExamResultFile.FILE_TASK,
                uploaded_by=actor,
            )
            log_education_event(
                center=session.center,
                actor=actor,
                action_type="exam_result_file_uploaded",
                entity=file_obj,
                payload={"result_id": result.id, "file_kind": ExamResultFile.FILE_TASK},
            )

        log_education_event(
            center=session.center,
            actor=actor,
            action_type="exam_result_created" if created else "exam_result_updated",
            entity=result,
            payload={
                "student_id": student.id,
                "session_id": session.id,
                "passed": passed,
                "follow_up_status": result.follow_up_status,
            },
        )

        saved_count += 1

    progress = get_exam_session_progress(session=session)
    session.status = ExamSession.STATUS_COMPLETED if progress["is_completed"] else ExamSession.STATUS_DRAFT
    if session.teacher_decision != ExamSession.DECISION_YES:
        session.teacher_decision = ExamSession.DECISION_YES
    session.updated_by = actor
    session.save(update_fields=["status", "teacher_decision", "updated_by", "updated_at"])

    log_education_event(
        center=session.center,
        actor=actor,
        action_type="exam_results_saved",
        entity=session,
        message=f"{saved_count} ta imtihon natijasi saqlandi",
        payload={
            "session_id": session.id,
            "saved_count": saved_count,
            "pending_students": progress["pending_students"],
            "completed_students": progress["completed_students"],
        },
    )
    return saved_count


def get_student_exam_summary(*, student, group=None):
    qs = ExamResult.objects.filter(student=student)
    if group:
        qs = qs.filter(group=group)

    stats = qs.aggregate(
        exam_count=Count("id"),
        average_percent=Avg("percent"),
    )
    passed = qs.filter(passed=True).count()
    exam_count = int(stats["exam_count"] or 0)
    pass_rate = (Decimal(passed) / Decimal(exam_count) * Decimal("100")) if exam_count else Decimal("0")
    last_exam = qs.order_by("-exam_date", "-id").first()

    return {
        "exam_count": exam_count,
        "average_percent": float(stats["average_percent"] or 0),
        "pass_rate_percent": float(pass_rate),
        "last_exam": last_exam,
    }
