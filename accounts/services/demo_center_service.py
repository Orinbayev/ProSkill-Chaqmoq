from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Center
from billing.models import (
    CenterSubscription,
    PaymentTransaction,
    Subscription,
    SubscriptionOrder,
    SubscriptionRequest,
)
from chaqmoq.models import Ledger, LightningHistory, Rule
from core.models import Notification
from education.models import (
    Attendance,
    AttendanceHistory,
    Category,
    CenterExamSetting,
    DailyLightningRecord,
    DailyLightningSetting,
    Dars,
    EducationAuditLog,
    Enrollment,
    ExamReminderLog,
    ExamResult,
    ExamResultFile,
    ExamSession,
    ExamSessionTaskFile,
    FinancialMonth,
    Group,
    GroupInternalRankingSnapshot,
    GroupStudent,
    MonthlyFinanceSnapshot,
    Oquvchi,
    OylikHisobot,
    Payment,
    PaymentAllocation,
    SalaryPayout,
    Student,
    StudentAcademicSummary,
    StudentGroupHistory,
    TeacherCompensationRule,
    TeacherExpectedIncomeSnapshot,
    TeacherIncome,
    TeacherSalarySnapshot,
    TuitionMonth,
    CertificateRecord,
    CertificateTemplate,
    CertificateVerificationLog,
)
from education.services.ranking_service import build_group_completion_recommendations
from education.services.tuition import create_payment_and_allocate, ensure_tuition_month


User = get_user_model()

DEMO_CENTER_SLUG = "demo-center"
DEMO_CENTER_NAME = "Chaqmoq Demo Center"
DEMO_PASSWORD_DEFAULT = "Demo12345!"
DEMO_NOTE_TAG = "[DEMO_SEED]"


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_add(value: date, delta: int) -> date:
    year = value.year + (value.month - 1 + delta) // 12
    month = ((value.month - 1 + delta) % 12) + 1
    return date(year, month, 1)


def _local_aware_datetime(day: date, hour: int = 12) -> datetime:
    return timezone.make_aware(datetime.combine(day, time(hour=hour, minute=0)))


def _restore_if_deleted(obj) -> None:
    if getattr(obj, "is_deleted", False):
        obj.restore()


def _hard_delete(qs) -> int:
    if hasattr(qs, "hard_delete"):
        deleted, _ = qs.hard_delete()
        return int(deleted or 0)
    deleted, _ = qs.delete()
    return int(deleted or 0)


def _build_attendance_dates(today: date) -> list[date]:
    days: list[date] = []
    cur = today - timedelta(days=28)
    while cur <= today:
        if cur.weekday() < 6:  # Monday-Saturday
            days.append(cur)
        cur += timedelta(days=1)
    return days[-18:]


def _scenario_for_index(index: int) -> str:
    order = ["excellent", "average", "weak", "debtor", "absent"]
    return order[index % len(order)]


def _attendance_status(scenario: str, day_index: int) -> str:
    if scenario == "excellent":
        return "absent_excused" if day_index % 11 == 0 else "present"
    if scenario == "average":
        if day_index % 7 == 0:
            return "absent_excused"
        return "present"
    if scenario == "weak":
        return "absent_unexcused" if day_index % 3 == 0 else "present"
    if scenario == "debtor":
        return "absent_unexcused" if day_index % 5 == 0 else "present"
    # absent
    if day_index % 6 == 0:
        return "present"
    return "absent_unexcused"


def _score_for_scenario(scenario: str, student_id: int) -> tuple[float | None, float | None, bool, bool]:
    if scenario == "excellent":
        percent = 90 + (student_id % 8)
    elif scenario == "average":
        percent = 72 + (student_id % 9)
    elif scenario == "weak":
        percent = 48 + (student_id % 10)
    elif scenario == "debtor":
        percent = 55 + (student_id % 9)
    else:
        return None, None, False, True
    percent = float(min(percent, 99))
    score = round(percent * 1.0, 2)
    passed = percent >= 60
    return score, percent, passed, False


def _demo_center_by_slug(slug: str) -> Center | None:
    return Center.all_objects.filter(slug=slug).first()


def _ensure_demo_center(slug: str) -> Center:
    center = _demo_center_by_slug(slug)
    if center:
        _restore_if_deleted(center)
    else:
        center = Center.objects.create(
            name=DEMO_CENTER_NAME,
            slug=slug,
            address="Toshkent shahri, Demo ko'chasi 7",
            phone="+998901112233",
            plan=Center.Plan.PRO,
            status=Center.STATUS_ACTIVE,
            max_students=300,
            max_users=120,
            max_groups=40,
            capacity_limit=300,
            is_demo=True,
            monthly_price=0,
        )

    center.name = DEMO_CENTER_NAME
    center.status = Center.STATUS_ACTIVE
    center.plan = center.plan or Center.Plan.PRO
    center.capacity_limit = max(center.capacity_limit or 0, 300)
    center.max_students = max(center.max_students or 0, 300)
    center.max_users = max(center.max_users or 0, 120)
    center.max_groups = max(center.max_groups or 0, 40)
    center.is_demo = True
    center.features = center.features or {
        "finance": True,
        "tasks": True,
        "leads": True,
        "kpi": True,
        "store": True,
    }
    center.save()
    return center


def _upsert_demo_user(
    *,
    center: Center,
    email: str,
    role: str,
    password: str,
    ism: str,
    familya: str,
    telefon1: str,
    is_staff: bool = False,
    lavozim: str = "",
) -> User:
    user = User.all_objects.filter(email__iexact=email).first()
    if user and not user.is_demo_user and user.center_id != center.id:
        raise ValueError(f"Email conflict with non-demo user: {email}")

    if user:
        _restore_if_deleted(user)
    else:
        user = User(email=email)

    user.role = role
    user.center = center
    user.ism = ism
    user.familya = familya
    user.telefon1 = telefon1
    user.lavozim = lavozim
    user.is_demo_user = True
    user.is_archived = False
    user.is_active = True
    user.is_staff = is_staff
    user.telegram_id = None
    user.telegram_username = None
    user.is_telegram_linked = False
    user.set_password(password)
    user.save()
    return user


def _ensure_demo_rules(center: Center) -> dict[str, Rule]:
    plus_rule, _ = Rule.objects.get_or_create(
        center=center,
        nom="Darsda faol qatnashdi",
        tur=Rule.PLUS,
        defaults={
            "min_baho": 1,
            "max_baho": 10,
            "can_director": True,
            "can_manager": True,
            "can_teacher": True,
        },
    )
    minus_rule, _ = Rule.objects.get_or_create(
        center=center,
        nom="Sababsiz dars qoldirdi",
        tur=Rule.MINUS,
        defaults={
            "min_baho": 1,
            "max_baho": 10,
            "can_director": True,
            "can_manager": True,
            "can_teacher": True,
        },
    )
    payment_rule, _ = Rule.objects.get_or_create(
        center=center,
        nom="To'lov bonusi",
        tur=Rule.PAYMENT_BONUS,
        defaults={
            "payment_bonus_lightning": 5,
            "can_director": True,
            "can_manager": True,
            "can_teacher": False,
        },
    )
    return {"plus": plus_rule, "minus": minus_rule, "payment": payment_rule}


def _ensure_demo_payment(
    *,
    enrollment: Enrollment,
    amount: int,
    month: date,
    created_by: User,
    tag: str,
) -> None:
    if amount <= 0:
        return

    month = _month_start(month)
    note_tag = f"{DEMO_NOTE_TAG} {tag} {month.isoformat()}"
    exists = Payment.objects.filter(
        enrollment=enrollment,
        note__icontains=note_tag,
    ).exists()
    if exists:
        return

    create_payment_and_allocate(
        enrollment=enrollment,
        created_by=created_by,
        cash_amount=int(amount),
        card_amount_som=0,
        start_month=month,
        paid_at=timezone.now(),
        note=note_tag,
    )


@transaction.atomic
def reset_demo_center(*, slug: str = DEMO_CENTER_SLUG) -> dict[str, Any]:
    center = _demo_center_by_slug(slug)
    if not center:
        return {"center_found": False, "slug": slug, "reset": False}
    if not center.is_demo:
        raise ValueError(f"Center '{slug}' is not marked as demo. Reset aborted.")

    demo_user_ids = list(User.all_objects.filter(center=center).values_list("id", flat=True))

    # Core notifications
    Notification.objects.filter(
        Q(center=center) | Q(recipient__center=center) | Q(sender__center=center)
    ).delete()

    # Billing data
    SubscriptionOrder.objects.filter(center=center).delete()
    SubscriptionRequest.objects.filter(center=center).delete()
    CenterSubscription.objects.filter(center=center).delete()
    Subscription.objects.filter(user__center=center).delete()
    PaymentTransaction.objects.filter(user__center=center).delete()

    # Education data
    CertificateVerificationLog.objects.filter(certificate__center=center).delete()
    CertificateRecord.objects.filter(center=center).delete()
    CertificateTemplate.objects.filter(center=center).delete()
    StudentAcademicSummary.objects.filter(center=center).delete()
    GroupInternalRankingSnapshot.objects.filter(center=center).delete()
    EducationAuditLog.objects.filter(center=center).delete()
    ExamResultFile.objects.filter(result__center=center).delete()
    ExamSessionTaskFile.objects.filter(session__center=center).delete()
    ExamResult.objects.filter(center=center).delete()
    ExamSession.objects.filter(center=center).delete()
    ExamReminderLog.objects.filter(center=center).delete()
    CenterExamSetting.objects.filter(center=center).delete()

    TeacherSalarySnapshot.objects.filter(financial_month__center=center).delete()
    MonthlyFinanceSnapshot.objects.filter(financial_month__center=center).delete()
    FinancialMonth.objects.filter(center=center).delete()
    TeacherExpectedIncomeSnapshot.objects.filter(center=center).delete()
    SalaryPayout.objects.filter(center=center).delete()
    TeacherCompensationRule.objects.filter(teacher__center=center).delete()
    StudentGroupHistory.objects.filter(center=center).delete()
    TeacherIncome.objects.filter(center=center).delete()

    DailyLightningSetting.objects.filter(center=center).delete()
    DailyLightningRecord.objects.filter(center=center).delete()
    AttendanceHistory.objects.filter(center=center).delete()
    Attendance.objects.filter(center=center).delete()

    _hard_delete(
        PaymentAllocation.all_objects.filter(
            Q(center=center) | Q(payment__center=center) | Q(tuition_month__center=center)
        )
    )
    _hard_delete(Payment.all_objects.filter(center=center))
    _hard_delete(TuitionMonth.all_objects.filter(center=center))
    _hard_delete(Enrollment.all_objects.filter(center=center))
    GroupStudent.objects.filter(center=center).delete()
    Dars.objects.filter(center=center).delete()
    Oquvchi.objects.filter(center=center).delete()
    OylikHisobot.objects.filter(center=center).delete()
    _hard_delete(Group.all_objects.filter(center=center))
    _hard_delete(Category.all_objects.filter(center=center))
    Student.objects.filter(center=center).delete()

    # Chaqmoq data
    LightningHistory.objects.filter(student__center=center).delete()
    Ledger.objects.filter(
        Q(student__center=center) | Q(group__center=center) | Q(rule__center=center)
    ).delete()
    Rule.objects.filter(center=center).delete()

    # Accounts data (only demo-center users)
    User.all_objects.filter(center=center, is_superuser=False).hard_delete()

    center.status = Center.STATUS_ACTIVE
    center.is_demo = True
    center.is_deleted = False
    center.save(update_fields=["status", "is_demo", "is_deleted"])

    return {
        "center_found": True,
        "slug": slug,
        "center_id": center.id,
        "reset": True,
        "deleted_user_ids_count": len(demo_user_ids),
    }


@transaction.atomic
def seed_demo_center(
    *,
    slug: str = DEMO_CENTER_SLUG,
    password: str = DEMO_PASSWORD_DEFAULT,
    reset_before_seed: bool = False,
) -> dict[str, Any]:
    if reset_before_seed:
        reset_demo_center(slug=slug)

    center = _ensure_demo_center(slug)

    director = _upsert_demo_user(
        center=center,
        email="director_demo@demo.chaqmoqapp.uz",
        role="director",
        password=password,
        ism="Sardor",
        familya="Rahimov",
        telefon1="+998901000001",
        is_staff=True,
        lavozim="Direktor",
    )
    manager = _upsert_demo_user(
        center=center,
        email="manager_demo@demo.chaqmoqapp.uz",
        role="manager",
        password=password,
        ism="Dilshod",
        familya="Karimov",
        telefon1="+998901000002",
        is_staff=True,
        lavozim="Manager",
    )

    teacher_defs = [
        ("teacher_demo_1@demo.chaqmoqapp.uz", "Otabek", "Tursunov", "+998901000011"),
        ("teacher_demo_2@demo.chaqmoqapp.uz", "Nargiza", "Abdullayeva", "+998901000012"),
        ("teacher_demo_3@demo.chaqmoqapp.uz", "Jasur", "Sultonov", "+998901000013"),
        ("teacher_demo_4@demo.chaqmoqapp.uz", "Shahnoza", "Rasulova", "+998901000014"),
    ]
    teachers: list[User] = []
    for email, ism, familya, phone in teacher_defs:
        teachers.append(
            _upsert_demo_user(
                center=center,
                email=email,
                role="teacher",
                password=password,
                ism=ism,
                familya=familya,
                telefon1=phone,
                is_staff=False,
                lavozim="O'qituvchi",
            )
        )

    category_lang, _ = Category.all_objects.get_or_create(center=center, name="Tillar")
    _restore_if_deleted(category_lang)
    category_lang.icon = "book"
    category_lang.save(update_fields=["icon"])

    category_it, _ = Category.all_objects.get_or_create(center=center, name="IT")
    _restore_if_deleted(category_it)
    category_it.icon = "laptop"
    category_it.save(update_fields=["icon"])

    group_defs = [
        ("IELTS Foundation A", Group.LANG, category_lang, teachers[0], 750000),
        ("Frontend N1", Group.IT, category_it, teachers[1], 680000),
        ("Python Beginner", Group.IT, category_it, teachers[2], 700000),
        ("Russian Language 1", Group.LANG, category_lang, teachers[3], 620000),
        ("Kids Math Group", Group.IT, category_it, teachers[1], 590000),
    ]
    groups: list[Group] = []
    for idx, (name, category, category_obj, teacher, price) in enumerate(group_defs):
        group, _ = Group.all_objects.get_or_create(
            center=center,
            nom=name,
            defaults={
                "category": category,
                "category_obj": category_obj,
                "oqituvchi": teacher,
                "kurs_narxi": price,
                "oqituvchi_foiz": 40,
                "oy_dars_soni": 12,
                "course_start_date": timezone.localdate() - timedelta(days=60 + idx * 7),
                "duration_months": 6,
                "lessons_per_week": 3,
            },
        )
        _restore_if_deleted(group)
        group.category = category
        group.category_obj = category_obj
        group.oqituvchi = teacher
        group.kurs_narxi = price
        group.oqituvchi_foiz = 40
        group.oy_dars_soni = 12
        group.is_archived = False
        group.is_closed = False
        group.save()
        groups.append(group)

    student_name_pool = [
        ("Aziz", "Yusupov"),
        ("Madina", "Raximova"),
        ("Behruz", "Aliyev"),
        ("Shahzoda", "Normatova"),
        ("Kamron", "Usmonov"),
        ("Gulnoza", "Ergasheva"),
        ("Sherzod", "Jo'rayev"),
        ("Zilola", "Akbarova"),
        ("Sardor", "Mamatov"),
        ("Fotima", "Qobilova"),
        ("Oybek", "To'xtayev"),
        ("Nigina", "Sobirova"),
        ("Asliddin", "Qudratov"),
        ("Mubina", "Saidova"),
        ("Javohir", "Niyozov"),
        ("Lola", "Mahmudova"),
        ("Samandar", "Qosimov"),
        ("Dildora", "Abduqodirova"),
        ("Rustam", "Rasulov"),
        ("Sevara", "Murodova"),
        ("Mirjalol", "Toshpulatov"),
        ("Sarvinoz", "Qahhorova"),
        ("Umid", "Hakimov"),
        ("Shirin", "Yodgorova"),
    ]

    students: list[User] = []
    scenarios: dict[int, str] = {}
    for idx, (ism, familya) in enumerate(student_name_pool, start=1):
        student = _upsert_demo_user(
            center=center,
            email=f"student_demo_{idx}@demo.chaqmoqapp.uz",
            role="student",
            password=password,
            ism=ism,
            familya=familya,
            telefon1=f"+99890990{idx:04d}",
            is_staff=False,
        )
        student.birth_date = date(2007 + (idx % 7), (idx % 12) + 1, (idx % 27) + 1)
        student.gender = User.Gender.MALE if idx % 2 else User.Gender.FEMALE
        student.is_archived = False
        student.save(update_fields=["birth_date", "gender", "is_archived"])
        students.append(student)
        scenarios[student.id] = _scenario_for_index(idx - 1)
        Student.objects.get_or_create(user=student, defaults={"center": center})

    parents: list[User] = []
    for idx in range(1, 11):
        parent = _upsert_demo_user(
            center=center,
            email=f"parent_demo_{idx}@demo.chaqmoqapp.uz",
            role="parent",
            password=password,
            ism=f"OtaOna{idx}",
            familya="Demo",
            telefon1=f"+99893330{idx:04d}",
            is_staff=False,
        )
        parents.append(parent)

    for idx, parent in enumerate(parents):
        linked_students = students[idx * 2:(idx * 2) + 2]
        parent.children.set(linked_students)

    enrollments: list[Enrollment] = []
    for idx, student in enumerate(students):
        group = groups[idx % len(groups)]
        enrollment, _ = Enrollment.all_objects.get_or_create(
            group=group,
            student=student,
            defaults={
                "center": center,
                "kurs_narhi": group.kurs_narxi,
                "oqituvchi_foiz": group.oqituvchi_foiz,
                "is_active": True,
            },
        )
        _restore_if_deleted(enrollment)
        enrollment.center = center
        enrollment.kurs_narhi = group.kurs_narxi
        enrollment.oqituvchi_foiz = group.oqituvchi_foiz
        enrollment.is_active = True
        enrollment.save()
        enrollments.append(enrollment)

    attendance_days = _build_attendance_dates(timezone.localdate())
    rules = _ensure_demo_rules(center)

    for enrollment in enrollments:
        scenario = scenarios.get(enrollment.student_id, "average")
        for day_index, lesson_day in enumerate(attendance_days):
            status = _attendance_status(scenario, day_index)
            attendance, _ = Attendance.objects.update_or_create(
                group=enrollment.group,
                student=enrollment.student,
                date=lesson_day,
                defaults={
                    "teacher": enrollment.group.oqituvchi,
                    "center": center,
                    "status": status,
                    "present": status == "present",
                    "forced": False,
                    "created_by": manager,
                },
            )

            plus_points = 0
            minus_points = 0
            if status == "present":
                plus_points = 2 if scenario in {"average", "debtor"} else 3
            elif status == "absent_unexcused":
                minus_points = 2

            DailyLightningRecord.objects.update_or_create(
                group=enrollment.group,
                student=enrollment.student,
                date=lesson_day,
                defaults={
                    "center": center,
                    "attendance_status": status,
                    "plus_points": plus_points,
                    "minus_points": minus_points,
                },
            )

            if lesson_day < (timezone.localdate() - timedelta(days=10)):
                continue

            if plus_points > 0:
                if not Ledger.objects.filter(
                    student=enrollment.student,
                    group=enrollment.group,
                    rule=rules["plus"],
                    sana__date=lesson_day,
                ).exists():
                    Ledger.objects.create(
                        student=enrollment.student,
                        group=enrollment.group,
                        beruvchi=enrollment.group.oqituvchi,
                        rule=rules["plus"],
                        ball=plus_points,
                        sana=_local_aware_datetime(lesson_day, 18),
                    )
            if minus_points > 0:
                if not Ledger.objects.filter(
                    student=enrollment.student,
                    group=enrollment.group,
                    rule=rules["minus"],
                    sana__date=lesson_day,
                ).exists():
                    Ledger.objects.create(
                        student=enrollment.student,
                        group=enrollment.group,
                        beruvchi=enrollment.group.oqituvchi,
                        rule=rules["minus"],
                        ball=-minus_points,
                        sana=_local_aware_datetime(lesson_day, 18),
                    )

            # Keep teacher income row fresh for seeded attendance if signal order changes.
            if attendance.teacher_id is None and enrollment.group.oqituvchi_id:
                attendance.teacher = enrollment.group.oqituvchi
                attendance.save(update_fields=["teacher"])

    current_month = _month_start(timezone.localdate())
    previous_month = _month_add(current_month, -1)
    older_month = _month_add(current_month, -2)

    for enrollment in enrollments:
        ensure_tuition_month(enrollment, previous_month)
        ensure_tuition_month(enrollment, current_month)

        scenario = scenarios.get(enrollment.student_id, "average")
        fee = int(enrollment.kurs_narhi or 0)

        if scenario == "excellent":
            _ensure_demo_payment(
                enrollment=enrollment,
                amount=fee,
                month=previous_month,
                created_by=manager,
                tag="PAID_PREV",
            )
            _ensure_demo_payment(
                enrollment=enrollment,
                amount=fee,
                month=current_month,
                created_by=manager,
                tag="PAID_CURRENT",
            )
        elif scenario == "average":
            _ensure_demo_payment(
                enrollment=enrollment,
                amount=fee,
                month=previous_month,
                created_by=manager,
                tag="PAID_PREV",
            )
            _ensure_demo_payment(
                enrollment=enrollment,
                amount=max(int(fee * 0.5), 1),
                month=current_month,
                created_by=manager,
                tag="PARTIAL_CURRENT",
            )
        elif scenario == "weak":
            _ensure_demo_payment(
                enrollment=enrollment,
                amount=max(int(fee * 0.7), 1),
                month=previous_month,
                created_by=manager,
                tag="PARTIAL_PREV",
            )
        elif scenario == "debtor":
            ensure_tuition_month(enrollment, older_month)
            _ensure_demo_payment(
                enrollment=enrollment,
                amount=max(int(fee * 0.3), 1),
                month=previous_month,
                created_by=manager,
                tag="OVERDUE_PARTIAL",
            )
        else:
            # frequently absent scenario -> pending current + overdue previous
            ensure_tuition_month(enrollment, previous_month)

    exam_settings, _ = CenterExamSetting.objects.get_or_create(center=center)
    exam_settings.exam_system_enabled = True
    exam_settings.exam_every_n_lessons = 12
    exam_settings.passing_score_percent = 60
    exam_settings.exam_result_required = True
    exam_settings.updated_by = director
    exam_settings.save()

    exam_date = timezone.localdate() - timedelta(days=7)
    for group in groups:
        session, _ = ExamSession.objects.get_or_create(
            center=center,
            group=group,
            lesson_number_reference=12,
            defaults={
                "teacher": group.oqituvchi,
                "attendance_date": exam_date,
                "exam_date": exam_date,
                "exam_sequence_number": 1,
                "teacher_decision": ExamSession.DECISION_YES,
                "status": ExamSession.STATUS_COMPLETED,
                "created_by": manager,
                "updated_by": manager,
            },
        )
        if session.status != ExamSession.STATUS_COMPLETED:
            session.status = ExamSession.STATUS_COMPLETED
            session.teacher_decision = ExamSession.DECISION_YES
            session.updated_by = manager
            session.save(update_fields=["status", "teacher_decision", "updated_by"])

        group_enrollments = [e for e in enrollments if e.group_id == group.id]
        for enrollment in group_enrollments:
            scenario = scenarios.get(enrollment.student_id, "average")
            score, percent, passed, absent = _score_for_scenario(scenario, enrollment.student_id)
            ExamResult.objects.update_or_create(
                session=session,
                student=enrollment.student,
                defaults={
                    "center": center,
                    "group": group,
                    "teacher": group.oqituvchi,
                    "score": score,
                    "percent": percent,
                    "passed": bool(passed),
                    "teacher_comment": f"{DEMO_NOTE_TAG} demo exam result",
                    "assignment_description": "Demo topshiriq",
                    "exam_date": session.exam_date,
                    "lesson_number_reference": 12,
                    "absent_in_exam": bool(absent),
                    "retake_recommended": not bool(passed),
                    "created_by": manager,
                    "updated_by": manager,
                },
            )

        build_group_completion_recommendations(
            group=group,
            on_date=timezone.localdate(),
            actor=manager,
            persist=True,
        )

    credentials = [
        {"role": "director", "email": director.email, "password": password},
        {"role": "manager", "email": manager.email, "password": password},
    ]
    credentials.extend({"role": "teacher", "email": t.email, "password": password} for t in teachers[:2])
    credentials.extend({"role": "parent", "email": p.email, "password": password} for p in parents[:1])

    return {
        "center_id": center.id,
        "center_slug": center.slug,
        "center_name": center.name,
        "users_total": User.objects.filter(center=center).count(),
        "groups_total": Group.objects.filter(center=center, is_archived=False).count(),
        "students_total": User.objects.filter(center=center, role="student", is_archived=False).count(),
        "parents_total": User.objects.filter(center=center, role="parent", is_archived=False).count(),
        "credentials": credentials,
        "note": "Demo center seeded safely",
    }
