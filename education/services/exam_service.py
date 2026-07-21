from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.db.models import Avg, Count, Q
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


def log_exam_reminder_action(
    *,
    group,
    teacher,
    action: str,
    attendance_date,
    note: str = "",
    metadata=None,
    lesson_number_reference: int | None = None,
):
    if lesson_number_reference is None:
        lesson_number_reference = get_group_lesson_number(group=group, on_date=attendance_date)
    log = ExamReminderLog.objects.create(
        center=group.center,
        group=group,
        teacher=teacher,
        attendance_date=attendance_date or timezone.localdate(),
        lesson_number_reference=int(lesson_number_reference or 0),
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
def save_exam_results_batch(*, session, actor, rows: list[dict], finalize: bool = False):
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
    session.status = (
        ExamSession.STATUS_COMPLETED
        if finalize and progress["is_completed"]
        else ExamSession.STATUS_DRAFT
    )
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
            "finalize": bool(finalize),
            "status": session.status,
        },
    )
    return saved_count


def notify_exam_results(session: ExamSession):
    """
    Sessiya yakunlanganda o'quvchi, ota-ona va boshqaruvga natija yuboradi.
    """
    try:
        from accounts.models import User
        from accounts.utils_bot import send_telegram_message
        from core.models import Notification

        settings_obj = get_or_create_center_exam_settings(session.center)
        passing_percent = Decimal(str(settings_obj.passing_score_percent or 60))

        results = list(
            ExamResult.objects.filter(session=session)
            .select_related("student")
            .prefetch_related("student__parents")
        )

        valid_results = [
            result
            for result in results
            if result.absent_in_exam or result.score is not None or result.percent is not None
        ]
        if not valid_results:
            return 0

        created_count = 0
        for result in valid_results:
            percent_value = result.percent if result.percent is not None else Decimal("0")
            percent_text = f"{percent_value:.1f}"
            if result.absent_in_exam:
                student_message = f"📝 {session.group.nom} guruhida imtihon bo'ldi. Siz qatnashmadingiz."
                parent_message = (
                    f"📝 {session.group.nom} guruhida imtihon bo'ldi. "
                    f"Farzandingiz {result.student.get_full_name()} qatnashmadi."
                )
            elif result.passed:
                student_message = (
                    f"✅ {session.group.nom} imtihon natijangiz: {percent_text}%."
                    " Siz imtihondan o'tdingiz."
                )
                parent_message = (
                    f"✅ {result.student.get_full_name()} {session.group.nom} guruhidagi imtihondan "
                    f"{percent_text}% bilan o'tdi."
                )
            else:
                student_message = (
                    f"❌ {session.group.nom} imtihon natijangiz: {percent_text}%."
                    f" O'tish chegarasi {passing_percent:.0f}%."
                    " Qayta topshirish tavsiya etiladi."
                )
                parent_message = (
                    f"❌ {result.student.get_full_name()} {session.group.nom} guruhidagi imtihondan "
                    f"{percent_text}% oldi. Qayta topshirish tavsiya etiladi."
                )

            Notification.objects.create(
                center=session.center,
                recipient=result.student,
                title="Imtihon natijasi",
                message=student_message,
                type="system",
            )
            created_count += 1

            if result.student.is_telegram_linked and result.student.telegram_id:
                try:
                    send_telegram_message(result.student.telegram_id, student_message)
                except Exception:
                    logger.exception("Student telegram notification failed: result_id=%s", result.id)

            for parent in result.student.parents.all():
                if parent.is_archived:
                    continue
                Notification.objects.create(
                    center=session.center,
                    recipient=parent,
                    title="Farzandingizning imtihon natijasi",
                    message=parent_message,
                    type="system",
                )
                created_count += 1
                if parent.is_telegram_linked and parent.telegram_id:
                    try:
                        send_telegram_message(parent.telegram_id, parent_message)
                    except Exception:
                        logger.exception(
                            "Parent telegram notification failed: result_id=%s parent_id=%s",
                            result.id,
                            parent.id,
                        )

        passed_count = sum(1 for result in valid_results if result.passed and not result.absent_in_exam)
        total = len(valid_results)
        avg_percent = (
            sum(float(result.percent or 0) for result in valid_results if result.percent is not None)
            / max(sum(1 for result in valid_results if result.percent is not None), 1)
        )
        summary = (
            f"📊 {session.group.nom} imtihoni yakunlandi.\n"
            f"O'tdi: {passed_count}/{total}\n"
            f"O'rtacha foiz: {avg_percent:.1f}%"
        )

        managers = User.objects.filter(
            center=session.center,
            role__in=["manager", "director"],
            is_archived=False,
        )
        for manager in managers:
            Notification.objects.create(
                center=session.center,
                recipient=manager,
                title="Imtihon hisoboti",
                message=summary,
                type="system",
            )
            created_count += 1
            if manager.is_telegram_linked and manager.telegram_id:
                try:
                    send_telegram_message(manager.telegram_id, summary)
                except Exception:
                    logger.exception("Manager telegram notification failed: session_id=%s", session.id)

        return created_count
    except Exception:
        logger.exception("notify_exam_results failed: session_id=%s", getattr(session, "id", None))
        return 0


def _exam_telegram_already_notified(*, group, checkpoint: int, reason: str) -> bool:
    """
    Checkpoint bo'yicha dedupe:
    - due_now / overdue: bir marta (session ochilguncha)
    - deferred / pending_results: 24 soatda bir marta
    """
    qs = ExamReminderLog.objects.filter(
        group=group,
        lesson_number_reference=checkpoint,
        action=ExamReminderLog.ACTION_TELEGRAM,
    )
    if reason in ("pending_results", "deferred_checkpoint"):
        since = timezone.now() - timedelta(hours=24)
        return qs.filter(created_at__gte=since).exists()
    return qs.exists()


def _build_teacher_exam_due_message(*, group, state: dict) -> str:
    settings_obj = state.get("settings")
    n = int(getattr(settings_obj, "exam_every_n_lessons", None) or 12)
    lesson_number = int(state.get("lesson_number") or 0)
    checkpoint = int(state.get("target_lesson_number") or 0)
    reason = state.get("reason") or "due_now"
    group_name = getattr(group, "nom", "") or f"Guruh #{getattr(group, 'id', '')}"

    if reason == "pending_results":
        progress = state.get("progress") or {}
        return (
            f"📝 Imtihon natijalari kutilmoqda\n\n"
            f"Guruh: {group_name}\n"
            f"Nazorat darsi: {checkpoint}-dars\n"
            f"Hozirgi dars: {lesson_number}\n"
            f"Kiritilgan: {progress.get('completed_students', 0)}/"
            f"{progress.get('total_students', 0)}\n\n"
            f"Iltimos, saytda imtihon natijalarini to‘ldiring."
        )

    if reason == "deferred_checkpoint":
        return (
            f"⏰ Imtihon eslatmasi (keyinga qoldirilgan)\n\n"
            f"Guruh: {group_name}\n"
            f"Nazorat: har {n} darsda ({checkpoint}-dars)\n"
            f"Hozirgi dars: {lesson_number}\n\n"
            f"Imtihon o‘tkazish yoki qaror qilish uchun saytga kiring."
        )

    overdue = bool(state.get("is_overdue_checkpoint"))
    prefix = "⚠️ Muddat o‘tgan imtihon" if overdue else "📝 Imtihon vaqti keldi"
    return (
        f"{prefix}\n\n"
        f"Guruh: {group_name}\n"
        f"Dars: {lesson_number}-dars (har {n} darsda imtihon)\n"
        f"Nazorat bosqichi: {checkpoint}-dars\n\n"
        f"Saytda guruh sahifasida «Ha / Yo‘q / Keyinroq» ni tanlang "
        f"va baholarni kiriting."
    )


def notify_teacher_exam_due(*, group, on_date=None, force: bool = False) -> dict:
    """
    Guruhda imtihon muddati yetganda o'qituvchiga in-app + Telegram eslatma yuboradi.
    Attendance saqlanganda va kunlik skaner orqali chaqiriladi.
    """
    on_date = on_date or timezone.localdate()
    try:
        state = get_exam_reminder_state(group=group, on_date=on_date)
        if not state.get("enabled"):
            return {"sent": False, "reason": "disabled"}
        if not state.get("due"):
            return {"sent": False, "reason": state.get("reason") or "not_due"}

        teacher = getattr(group, "oqituvchi", None)
        if teacher is None and getattr(group, "oqituvchi_id", None):
            from accounts.models import User

            teacher = User.objects.filter(pk=group.oqituvchi_id).first()
        if not teacher or getattr(teacher, "is_archived", False):
            return {"sent": False, "reason": "no_teacher"}

        checkpoint = int(state.get("target_lesson_number") or 0)
        reason = state.get("reason") or "due_now"
        if checkpoint <= 0:
            return {"sent": False, "reason": "no_checkpoint"}

        # Dedupe: bir checkpoint (yoki 24s ichida deferred/pending) uchun bir marta.
        # Claim avval log yoziladi — keyin yuboriladi (bulk attendance race'ida ham spam kamayadi).
        if not force and _exam_telegram_already_notified(
            group=group, checkpoint=checkpoint, reason=reason
        ):
            return {"sent": False, "reason": "already_notified"}

        message = _build_teacher_exam_due_message(group=group, state=state)
        title = "Imtihon eslatmasi"

        # Avval log (claim), so'ng xabar — parallel chaqiriqlar keyingi exists() da to'xtaydi
        log_exam_reminder_action(
            group=group,
            teacher=teacher,
            action=ExamReminderLog.ACTION_TELEGRAM,
            attendance_date=on_date,
            note="Telegram/in-app imtihon eslatmasi",
            lesson_number_reference=checkpoint,
            metadata={
                "reason": reason,
                "checkpoint": checkpoint,
                "lesson_number": int(state.get("lesson_number") or 0),
                "force": bool(force),
            },
        )

        try:
            from core.models import Notification

            Notification.objects.create(
                center=group.center,
                recipient=teacher,
                title=title,
                message=message.replace("\n", "<br>"),
                type="system",
            )
        except Exception:
            logger.exception(
                "In-app exam reminder failed: group_id=%s teacher_id=%s",
                getattr(group, "id", None),
                getattr(teacher, "id", None),
            )

        telegram_sent = False
        if getattr(teacher, "is_telegram_linked", False) and getattr(teacher, "telegram_id", None):
            try:
                from accounts.utils_bot import send_telegram_message_async

                send_telegram_message_async(teacher.telegram_id, message)
                telegram_sent = True
            except Exception:
                logger.exception(
                    "Teacher telegram exam reminder failed: group_id=%s teacher_id=%s",
                    getattr(group, "id", None),
                    getattr(teacher, "id", None),
                )

        return {
            "sent": True,
            "telegram": telegram_sent,
            "reason": reason,
            "checkpoint": checkpoint,
            "teacher_id": teacher.id,
        }
    except Exception:
        logger.exception(
            "notify_teacher_exam_due failed: group_id=%s",
            getattr(group, "id", None),
        )
        return {"sent": False, "reason": "error"}


def maybe_notify_teacher_exam_due_for_attendance(attendance) -> dict:
    """
    Davomat saqlangandan keyin (on_commit) chaqiriladi.
    Faqat guruhda imtihon tizimi yoqilgan va muddat yetgan bo'lsa yuboradi.
    """
    group = getattr(attendance, "group", None)
    if group is None:
        return {"sent": False, "reason": "no_group"}
    # Archived/closed guruhlarga eslatma yo'q
    if getattr(group, "is_archived", False) or getattr(group, "is_deleted", False) or getattr(
        group, "is_closed", False
    ):
        return {"sent": False, "reason": "group_inactive"}

    center = getattr(group, "center", None) or getattr(attendance, "center", None)
    if center is None:
        return {"sent": False, "reason": "no_center"}

    # Sozlama yo'q yoki o'chiq markazlarda get_or_create qilmaymiz (har davomatda spam bo'lmasin)
    settings_obj = CenterExamSetting.objects.filter(center=center).only("exam_system_enabled").first()
    if settings_obj is None or not settings_obj.exam_system_enabled:
        return {"sent": False, "reason": "disabled"}

    on_date = getattr(attendance, "date", None) or timezone.localdate()
    return notify_teacher_exam_due(group=group, on_date=on_date)


def scan_and_notify_due_exams(*, center=None, on_date=None, force: bool = False) -> dict:
    """
    Barcha (yoki bitta markaz) faol guruhlar bo'yicha imtihon muddatini skanerlaydi
    va o'qituvchilarga eslatma yuboradi. Kunlik cron uchun.
    """
    on_date = on_date or timezone.localdate()
    from education.models import Group

    groups = (
        Group.objects.filter(
            is_archived=False,
            is_deleted=False,
            is_closed=False,
            center__exam_settings__exam_system_enabled=True,
        )
        .select_related("center", "oqituvchi")
        .order_by("center_id", "nom")
    )
    if center is not None:
        groups = groups.filter(center=center)

    sent = 0
    skipped = 0
    errors = 0
    details: list[dict] = []
    for group in groups.iterator(chunk_size=100):
        result = notify_teacher_exam_due(group=group, on_date=on_date, force=force)
        if result.get("sent"):
            sent += 1
        elif result.get("reason") == "error":
            errors += 1
        else:
            skipped += 1
        details.append({"group_id": group.id, **result})
    return {"sent": sent, "skipped": skipped, "errors": errors, "details": details}


def get_teacher_due_exam_groups(*, center, teacher, on_date=None) -> list[dict]:
    """O'qituvchi guruhlarida imtihon eslatmasi kerak bo'lganlar."""
    on_date = on_date or timezone.localdate()
    from education.models import Group

    groups = (
        Group.objects.filter(
            center=center,
            oqituvchi=teacher,
            is_archived=False,
            is_deleted=False,
            is_closed=False,
        )
        .select_related("center")
        .order_by("nom")
    )
    rows = []
    for group in groups:
        state = get_exam_reminder_state(group=group, on_date=on_date)
        if not state.get("enabled"):
            continue
        rows.append({"group": group, "state": state})
    due = [r for r in rows if r["state"].get("due")]
    rest = [r for r in rows if not r["state"].get("due")]
    return due + rest


def get_annual_exam_grades(*, center, year: int, teacher=None, group=None) -> dict:
    """Yillik baholar — oyma-oy o'rtacha, o'quvchi kesimi."""
    from django.db.models.functions import TruncMonth
    from education.models import Group

    qs = ExamResult.objects.filter(
        center=center,
        exam_date__year=year,
    ).filter(
        Q(score__isnull=False) | Q(percent__isnull=False) | Q(absent_in_exam=True)
    )
    if teacher is not None:
        qs = qs.filter(Q(teacher=teacher) | Q(session__teacher=teacher) | Q(group__oqituvchi=teacher))
    if group is not None:
        qs = qs.filter(group=group)

    monthly = list(
        qs.exclude(percent__isnull=True)
        .annotate(month=TruncMonth("exam_date"))
        .values("month")
        .annotate(
            avg_percent=Avg("percent"),
            count=Count("id"),
            pass_count=Count("id", filter=Q(passed=True, absent_in_exam=False)),
        )
        .order_by("month")
    )

    by_student = list(
        qs.values(
            "student_id",
            "student__ism",
            "student__familya",
            "group_id",
            "group__nom",
        )
        .annotate(
            exam_count=Count("id"),
            avg_percent=Avg("percent", filter=Q(percent__isnull=False)),
            pass_count=Count("id", filter=Q(passed=True, absent_in_exam=False)),
            fail_count=Count(
                "id",
                filter=Q(passed=False)
                & (Q(score__isnull=False) | Q(percent__isnull=False) | Q(absent_in_exam=True)),
            ),
        )
        .order_by("student__ism", "student__familya")
    )

    overall_avg = qs.exclude(percent__isnull=True).aggregate(a=Avg("percent"))["a"]
    total = qs.count()
    passed = qs.filter(passed=True, absent_in_exam=False).count()

    month_labels = []
    month_values = []
    month_counts = []
    for row in monthly:
        m = row["month"]
        if m:
            month_labels.append(m.strftime("%b"))
            month_values.append(round(float(row["avg_percent"] or 0), 1))
            month_counts.append(int(row["count"] or 0))

    groups = Group.objects.filter(center=center, is_archived=False).order_by("nom")
    if teacher is not None:
        groups = groups.filter(oqituvchi=teacher)

    return {
        "year": year,
        "total_results": total,
        "passed_count": passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "overall_avg": round(float(overall_avg or 0), 1) if overall_avg is not None else None,
        "month_labels": month_labels,
        "month_values": month_values,
        "month_counts": month_counts,
        "students": by_student,
        "groups": list(groups),
    }


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
