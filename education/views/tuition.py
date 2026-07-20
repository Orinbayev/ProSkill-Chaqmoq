"""
Auto-split from education/views.py (phase 7 god-file reduction).
Public API re-exported via education.views package.
"""
from __future__ import annotations

from .common import *  # noqa: F403


@login_required
@require_POST
def calculate_lessons_api(request):
    """
    Enrollment dars/narx preview API.
    CSRF himoyalangan (sessiya cookie); frontend X-CSRFToken yuboradi.
    @csrf_exempt olib tashlandi — web sessiya CSRF bypass xavfi yo'qoladi.
    """
    try:

        center = get_active_center(request)
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            if request.content_type == "application/json":
                return JsonResponse(
                    {"success": False, "error": "JSON ma'lumot noto'g'ri yuborildi."},
                    status=400,
                )
            payload = request.POST

        enrollment_id = _parse_int_value(payload.get("enrollment_id"))
        group_id = _parse_int_value(payload.get("group_id"))

        enrollment = None
        if enrollment_id:
            enrollment_qs = Enrollment.all_objects.select_related("group", "group__category_obj", "student", "course")
            if center:
                enrollment_qs = enrollment_qs.filter(
                    Q(center=center)
                    | Q(center__isnull=True, group__center=center)
                    | Q(center__isnull=True, student__center=center)
                )
            enrollment = enrollment_qs.filter(id=enrollment_id).first()
            if enrollment is None:
                return JsonResponse({"success": False, "error": "Enrollment topilmadi."}, status=400)

        group = None
        if group_id:
            if enrollment is not None:
                sibling_qs = Enrollment.objects.select_related("group", "group__category_obj", "student", "course").filter(
                    student=enrollment.student,
                    group_id=group_id,
                    is_active=True,
                    student__is_archived=False,
                    group__is_archived=False,
                    group__is_deleted=False,
                )
                if center:
                    sibling_qs = sibling_qs.filter(center=center)
                sibling_enrollment = sibling_qs.first()
                if sibling_enrollment is None:
                    return JsonResponse({"success": False, "error": "Bu o'quvchi ushbu guruhga biriktirilmagan."}, status=400)
                enrollment = sibling_enrollment
                group = enrollment.group
            else:
                group_qs = Group.objects.select_related("category_obj")
                if center:
                    group_qs = group_qs.filter(center=center)
                group = group_qs.filter(id=group_id).first()
                if group is None:
                    return JsonResponse({"success": False, "error": "Guruh topilmadi."}, status=400)
        elif enrollment is not None:
            group = enrollment.group

        if group is None:
            return JsonResponse({"success": False, "error": "Guruhni tanlang."}, status=400)

        start_date_raw = (payload.get("joined_at") or payload.get("start_date") or "").strip()
        if start_date_raw:
            start_date = parse_date(start_date_raw)
            if start_date is None:
                return JsonResponse({"success": False, "error": "Boshlanish sanasi noto'g'ri."}, status=400)
        else:
            start_date = (
                getattr(enrollment, "joined_at", None)
                or enrollment_start_date(enrollment)
                if enrollment is not None
                else timezone.localdate()
            )
        allowed_lesson_patterns = {
            Enrollment.LESSON_PATTERN_ODD,
            Enrollment.LESSON_PATTERN_EVEN,
            Enrollment.LESSON_PATTERN_DAILY,
            Enrollment.LESSON_PATTERN_GROUP,
        }
        lesson_pattern_raw = payload.get("lesson_pattern")
        if lesson_pattern_raw not in (None, ""):
            lesson_pattern_raw = str(lesson_pattern_raw).strip().lower()
            if lesson_pattern_raw not in allowed_lesson_patterns:
                return JsonResponse({"success": False, "error": "Dars patterni noto'g'ri."}, status=400)
        lesson_pattern = normalize_lesson_pattern(
            lesson_pattern_raw or getattr(enrollment, "lesson_pattern", None)
        )
        if lesson_pattern not in allowed_lesson_patterns:
            return JsonResponse({"success": False, "error": "Dars patterni noto'g'ri."}, status=400)

        course_price = int(
            _parse_int_value(
                payload.get("kurs_narhi"),
                getattr(enrollment, "kurs_narhi", 0) if enrollment is not None else getattr(group, "kurs_narxi", 0),
            )
            or 0
        )
        teacher_percent = int(
            _parse_int_value(
                payload.get("oqituvchi_foiz"),
                getattr(enrollment, "oqituvchi_foiz", 0) if enrollment is not None else getattr(group, "oqituvchi_foiz", 0),
            )
            or 0
        )
        monthly_lessons = int(
            _parse_int_value(
                payload.get("monthly_lessons"),
                getattr(enrollment, "monthly_lessons", 0) if enrollment is not None else getattr(group, "oy_dars_soni", 0),
            )
            or getattr(group, "oy_dars_soni", 0)
            or 12
        )

        teacher_share_only = _parse_bool_value(payload.get("teacher_share_only"))
        missing = object()
        payable_raw = payload.get("student_payable_amount", missing)
        if teacher_share_only:
            student_payable_amount = round(course_price * teacher_percent / 100)
        elif payable_raw is missing:
            student_payable_amount = getattr(enrollment, "student_payable_amount", None) if enrollment is not None else None
        elif payable_raw in (None, "", "None"):
            student_payable_amount = None
        else:
            student_payable_amount = _parse_int_value(
                payable_raw,
                getattr(enrollment, "student_payable_amount", None) if enrollment is not None else None,
            )

        preview_enrollment = _build_tuition_preview_enrollment(
            base_enrollment=enrollment,
            group=group,
            start_date=start_date,
            lesson_pattern=lesson_pattern,
            monthly_lessons=monthly_lessons,
            course_price=course_price,
            teacher_percent=teacher_percent,
            student_payable_amount=student_payable_amount,
        )
        preview_month = month_first_day(timezone.localdate())
        preview = tuition_month_preview(preview_enrollment, preview_month)
        period_end = _parse_period_end(payload.get("period_end_date") or payload.get("end_date"), preview["month"])
        preview = _apply_period_end_to_preview(preview, period_end)

        remaining_raw = payload.get("remaining_lessons", missing)
        if remaining_raw is missing:
            remaining_lessons = (
                getattr(enrollment, "remaining_lessons_override", None)
                if enrollment is not None and getattr(enrollment, "remaining_lessons_override", None) is not None
                else int(preview["lesson_count"] or 0)
            )
        elif remaining_raw in ("", None):
            remaining_lessons = int(preview["lesson_count"] or 0)
        else:
            try:
                remaining_lessons = validate_remaining_lessons(remaining_raw)
            except ValidationError as exc:
                return JsonResponse({"success": False, "error": exc.messages[0]}, status=400)

        try:
            lesson_plan = calculate_lessons(
                start_date=preview["start_date"],
                remaining_lessons=remaining_lessons,
                pattern=preview["lesson_pattern"],
                from_date=timezone.localdate(),
                group=group,
            )
        except ValidationError as exc:
            return JsonResponse({"success": False, "error": exc.messages[0]}, status=400)
        preview = _apply_lesson_count_breakdown(preview, preview_enrollment, remaining_lessons)
        preview_payload = _serialize_tuition_preview(preview)
        lesson_plan_payload = _serialize_lesson_plan(lesson_plan)
        response_data = {
            "total_lessons": preview_payload["lesson_count"],
            "lesson_price": preview_payload["per_lesson_amount"],
            "total_debt": preview_payload["fee_amount"],
            "teacher_share": preview_payload["teacher_share"],
            "center_share": preview_payload["center_share"],
            "lesson_dates": [
                int(label.split(".", 1)[0])
                for label in preview_payload.get("lesson_date_labels", [])
                if str(label).split(".", 1)[0].isdigit()
            ],
            "end_date": preview_payload["period_end_date"],
        }
        return JsonResponse(
            {
                "success": True,
                "data": response_data,
                "preview": preview_payload,
                "lesson_plan": lesson_plan_payload,
            },
            status=200,
        )
    except Exception as exc:
        logger.exception("calculate_lessons_api failed")
        return JsonResponse(
            {"success": False, "error": str(exc) or "Hisob-kitobda xatolik yuz berdi."},
            status=400,
        )



def sync_tuition_fee(enrollment, new_fee=None, start_month=None):
    """
    Viewlar uchun backward-compatible wrapper.
    Endi barcha logika service qatlamida bajariladi.
    """
    from education.services.tuition import sync_tuition_fee as service_sync_tuition_fee

    service_sync_tuition_fee(
        enrollment=enrollment,
        start_month=month_first_day(start_month or timezone.localdate()),
        new_fee=int(new_fee if new_fee is not None else effective_student_payable_amount(enrollment) or 0),
    )



@login_required
@require_feature("finance")
def qarzdorlar_home(request):
    from core.tenant import get_request_center, require_center
    from billing.services import clear_feature_request_cache
    clear_feature_request_cache()

    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("core:home")

    # Multi-tenant izolyatsiya: center bo'lmasa boshqa markaz qarzdorlari
    # ko'rinib qolmasligi uchun require_center superuser'ni picker'ga,
    # boshqalarni 404 ga yuboradi.
    center = require_center(request)

    # ─── FILTERS ────────────────────────────────────────────────────────────
    q = (request.GET.get("q") or "").strip()
    group_id = _get_int(request.GET, "group", 0)
    lesson_pattern_filter = (request.GET.get("lesson_pattern_filter") or "").strip().lower()
    if lesson_pattern_filter not in {
        Enrollment.LESSON_PATTERN_ODD,
        Enrollment.LESSON_PATTERN_EVEN,
        Enrollment.LESSON_PATTERN_DAILY,
    }:
        lesson_pattern_filter = ""
    min_debt = _get_int(request.GET, "min_debt", 0)
    max_debt = _get_int(request.GET, "max_debt", 0)
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or request.GET.get("end_date") or "").strip()

    # Status filter (template'dagi <select name="status">):
    #   active   — faqat faol qarzdorlar (is_deferred=False) [default]
    #   deferred — faqat kechiktirilgan
    #   all      — ikkalasi
    selected_status = (request.GET.get("status") or "active").strip().lower()
    if selected_status not in {"active", "deferred", "all"}:
        selected_status = "active"

    allowed_page_sizes = (10, 20, 50, 100)
    per_page_raw = (request.GET.get("per_page") or "10").strip()
    try:
        per_page = int(per_page_raw)
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in allowed_page_sizes:
        per_page = 10

    # ─── JORIY OY ANIQLASH ──────────────────────────────────────────────────
    today = timezone.localdate()
    selected_from = parse_date(date_from_raw) if date_from_raw else None
    selected_to = parse_date(date_to_raw) if date_to_raw else None

    used_default_period = False
    if not selected_from and not selected_to:
        # Default: faqat JORIY OY qarzi.
        # Foydalanuvchi o'tgan oyni ko'rmoqchi bo'lsa filterdan tanlaydi
        # (Sanadan / Sanagacha yoki "Oy" select).
        used_default_period = True
        selected_from = today.replace(day=1)
        selected_to = today
    else:
        if selected_from and not selected_to:
            selected_to = today if selected_from <= today else selected_from
        elif selected_to and not selected_from:
            selected_from = selected_to.replace(day=1)
        if selected_from and selected_to and selected_from > selected_to:
            selected_to = selected_from

    sel_month = (request.GET.get("pay_month") or "").strip()
    pay_month_int = None
    if sel_month and sel_month.isdigit():
        maybe_month = int(sel_month)
        if 1 <= maybe_month <= 12:
            pay_month_int = maybe_month

    if pay_month_int:
        selected_year = selected_to.year if selected_to else today.year
        _pay_month_start = date(selected_year, pay_month_int, 1)
        selected_from = _pay_month_start
        selected_to = month_last_day(_pay_month_start)

    # Har doim selected_from va selected_to oralig'idagi oylar bo'yicha qarzni hisoblaymiz.
    from education.services.tuition import month_range_starts
    period_months = month_range_starts(selected_from, selected_to)
    _display_month = month_first_day(selected_to)
    effective_pay_month = month_first_day(selected_from)

    # ─── FAOL ENROLLMENT'LAR ─────────────────────────────────────────────────
    # Faqat:  is_active=True  +  student NOT archived  +  group NOT archived
    # Legacy data: center=None enrollment'lari group/student.center orqali
    # markazga biriktiriladi (dashboard_metrics bilan izchil).
    from django.db.models import Q as _Q
    _center_q = (
        _Q(center=center)
        | _Q(center__isnull=True, group__center=center)
        | _Q(center__isnull=True, student__center=center)
    )
    active_enrs_qs = (
        Enrollment.objects
        .select_related("student", "group", "group__oqituvchi", "group__category_obj", "group__center")
        .filter(
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        )
        .filter(_center_q)
    )

    # ─── GURUHDAN CHIQARILGAN, AMMO QARZI BOR ENROLLMENT'LAR ─────────────────
    # is_active=False YOKI is_deleted=True (soft-deleted) lekin joriy PERIOD da
    # TuitionMonth yoki Davomat mavjud → ko'rsatamiz.
    # all_objects — is_deleted=True (guruhdan o'chirilgan) enrollment'larni ham oladi.
    _inactive_tm_enr_ids = set(
        TuitionMonth.objects
        .filter(
            Q(enrollment__is_active=False) | Q(enrollment__is_deleted=True),
            is_deleted=False,
            month__in=period_months,
            enrollment__student__is_archived=False,
            enrollment__group__is_archived=False,
            enrollment__group__is_deleted=False,
        )
        .values_list("enrollment_id", flat=True)
    )
    # Davomat yozilgan lekin TuitionMonth yo'q — bu oyda chiqarilgan bo'lishi mumkin
    from django.db.models import Exists, OuterRef as _OuterRef
    _inactive_att_enr_ids = set(
        Enrollment.all_objects.filter(
            Q(is_active=False) | Q(is_deleted=True),
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        ).filter(_center_q).annotate(
            _has_att=Exists(
                Attendance.objects.filter(
                    student_id=_OuterRef("student_id"),
                    group_id=_OuterRef("group_id"),
                    date__gte=selected_from,
                    date__lte=selected_to,
                )
            )
        ).filter(_has_att=True).values_list("id", flat=True)
    )
    _inactive_enr_ids = _inactive_tm_enr_ids | _inactive_att_enr_ids
    inactive_enrs_qs = (
        Enrollment.all_objects
        .select_related("student", "group", "group__oqituvchi", "group__category_obj", "group__center")
        .filter(
            Q(is_active=False) | Q(is_deleted=True),
            id__in=_inactive_enr_ids,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        )
        .filter(_center_q)
    )

    chart_mode = "monthly"
    chart_months = _last_12_ending(selected_to)

    # ─── ENROLLMENTS (FILTER UCHUN BASE) ─────────────────────────────────────
    enrs_base = active_enrs_qs
    if group_id:
        enrs_base = enrs_base.filter(group_id=group_id)

    # PERF: Qidiruv DB darajasida (avval Python loop'da edi — har student uchun
    # alohida qidirardi). Endi student bo'yicha indekslangan filter:
    if q:
        ql_terms = q.split()
        for term in ql_terms:
            enrs_base = enrs_base.filter(
                _Q(student__ism__icontains=term)
                | _Q(student__familya__icontains=term)
                | _Q(student__telefon1__icontains=term)
                | _Q(student__telefon2__icontains=term)
            )

    active_list = list(
        enrs_base.order_by(
            "student__familya",
            "student__ism",
            "student_id",
            "group__nom",
            "id",
        )
    )

    # Inactive enrollment'lar ham xuddi shu qidiruv/guruh filtrlaridan o'tishi kerak
    inactive_base = inactive_enrs_qs
    if group_id:
        inactive_base = inactive_base.filter(group_id=group_id)
    if q:
        ql_terms = q.split()
        for term in ql_terms:
            inactive_base = inactive_base.filter(
                _Q(student__ism__icontains=term)
                | _Q(student__familya__icontains=term)
                | _Q(student__telefon1__icontains=term)
                | _Q(student__telefon2__icontains=term)
            )
    inactive_list = list(inactive_base.order_by("student__familya", "student__ism", "id"))
    for _e in inactive_list:
        _e._is_unenrolled = True

    enrollment_list = active_list + inactive_list

    # PERF: Pre-load (a) StudentGroupHistory start dates, (b) GroupSchedule
    # weekday counts. Bu N+1 muammoning ASOSIY manbasi — har enrollment uchun
    # alohida `GroupSchedule.objects.filter(group=...)` chaqiruvi qilinmaydi.
    preload_enrollment_history_starts(enrollment_list)
    from education.services.tuition import preload_group_schedules
    preload_group_schedules({e.group_id for e in enrollment_list if e.group_id})

    # auto_net_student_credits is a payment-time write operation — calling it on
    # every page load causes 5+ queries per student (N+1). It is triggered by
    # the payment save path; skip it here entirely.

    # Lazy tuzatish: lesson_pattern stale bo'lsa "group" ga o'tkaz.
    # bulk_update bilan bir so'rovda, N+1 save() o'rniga.
    _cur_month_for_recalc = today.replace(day=1)
    from education.services.tuition import ensure_tuition_month as _etm
    _pattern_stale = [
        e for e in active_list
        if getattr(e, "is_active", False)
        and int(getattr(getattr(e, "group", None), "oy_dars_soni", 0) or 0) > 0
        and e.lesson_pattern in ("odd", "even", "daily")
    ]
    if _pattern_stale:
        for _e in _pattern_stale:
            _e.lesson_pattern = Enrollment.LESSON_PATTERN_GROUP
        Enrollment.objects.bulk_update(_pattern_stale, ["lesson_pattern"])

    # ensure_tuition_month: Pre-fetch existing TuitionMonth IDs for current month
    # in ONE query, then only call _etm for enrollments that are missing one.
    _active_ids = [e.id for e in active_list if getattr(e, "is_active", False)]
    if _active_ids:
        from education.models import TuitionMonth as _TM, Payment as _Pay, PaymentAllocation as _PA
        from django.db.models import Sum as _Sum
        _existing_tm_enr_ids = set(
            _TM.objects.filter(
                enrollment_id__in=_active_ids,
                month=_cur_month_for_recalc,
                is_deleted=False,
            ).values_list("enrollment_id", flat=True)
        )
        # To'lov bor lekin allocation yo'q YOKI yetarli emas → _etm chaqirilsin
        _pay_enr_ids = set(
            _Pay.objects.filter(
                enrollment_id__in=_active_ids,
                paid_date__year=_cur_month_for_recalc.year,
                paid_date__month=_cur_month_for_recalc.month,
                is_deleted=False,
                summa__gt=0,
            ).values_list("enrollment_id", flat=True)
        )
        # "To'liq bog'langan" = allocation.amount yig'indisi >= TuitionMonth.fee
        # Qisman bog'langan (allocation < fee) bo'lsa ham _etm chaqirilishi kerak.
        if _pay_enr_ids:
            from education.services.tuition import tuition_month_fee_field as _ff
            _fee_field = _ff()
            _tm_fee_map = {
                row["enrollment_id"]: int(row[_fee_field] or 0)
                for row in _TM.objects.filter(
                    enrollment_id__in=list(_pay_enr_ids),
                    month=_cur_month_for_recalc,
                    is_deleted=False,
                ).values("enrollment_id", _fee_field)
            }
            _alloc_sum_map = {
                row["tuition_month__enrollment_id"]: int(row["paid"] or 0)
                for row in _PA.objects.filter(
                    tuition_month__enrollment_id__in=list(_pay_enr_ids),
                    tuition_month__month=_cur_month_for_recalc,
                    tuition_month__is_deleted=False,
                    payment__is_deleted=False,
                ).values("tuition_month__enrollment_id")
                .annotate(paid=_Sum("amount"))
            }
            # allocation < fee → hali to'liq bog'lanmagan (qarz ko'rinishi mumkin)
            _partially_linked_ids = {
                enr_id
                for enr_id in _pay_enr_ids
                if _alloc_sum_map.get(enr_id, 0) < _tm_fee_map.get(enr_id, 1)
            }
            _unlinked_pay_ids = _partially_linked_ids
        else:
            _unlinked_pay_ids = set()

        for e in active_list:
            if not getattr(e, "is_active", False):
                continue
            if e.id in _existing_tm_enr_ids:
                _group_price = int(getattr(getattr(e, "group", None), "kurs_narxi", 0) or 0)
                _has_custom = (
                    e.student_payable_amount is not None
                    or e.kurs_narhi != _group_price
                )
                # To'lov bor lekin allocation to'liq emas bo'lsa ham _etm chaqiramiz
                if not _has_custom and e.id not in _unlinked_pay_ids:
                    continue
            try:
                _etm(e, _cur_month_for_recalc)
            except Exception:
                pass

    # Chiqarilgan (inactive) o'quvchilar — JORIY OY reconcile'i.
    # MUHIM: reconcile (mavjud TM fee'sini haqiqiy davomatga qarab yangilash)
    # HAR DOIM ishlaydi — filterda qaysi oy tanlanganidan qat'i nazar. Sababi:
    # o'quvchi guruhdan chiqarilgach joriy oy uchun qolib ketgan fee>0 TuitionMonth
    # "fantom qarz" bo'lib qoladi. Foydalanuvchi o'tgan oyni (mas. iyun) filterlasa,
    # joriy oy (iyul) reconcile qilinmay qolar edi → breakdown modalda va boshqa
    # oy filtrlarida fantom 250 000 so'm chiqardi. Davomat 0 → fee=0 → qarzdan chiqadi.
    # Yangi TM YARATISH esa faqat joriy oy ko'rilayotganda (perf uchun), aks holda
    # o'tgan oyni ko'rayotganda keraksiz joriy-oy yozuvi yaratmaymiz.
    if inactive_list:
        from education.services.tuition import (
            attendance_based_fee as _abf,
            billable_attendance_count as _bac,
        )
        _inactive_ids = [e.id for e in inactive_list]
        _existing_inactive_tm_ids = set(
            TuitionMonth.objects.filter(
                enrollment_id__in=_inactive_ids,
                month=_cur_month_for_recalc,
                is_deleted=False,
            ).values_list("enrollment_id", flat=True)
        )
        _may_create_current = _cur_month_for_recalc in period_months
        for _ie in inactive_list:
            if _ie.id in _existing_inactive_tm_ids:
                # Inactive o'quvchi: haqiqiy davomat asosida TM fee ni yangilaylik.
                # Davomat 0 bo'lsa fee=0 → qarzdorlardan chiqib ketadi.
                try:
                    _etm(_ie, _cur_month_for_recalc)
                except Exception:
                    pass
                continue
            if not _may_create_current:
                continue
            try:
                _att = _bac(_ie, _cur_month_for_recalc)
                if _att > 0:
                    _fee = _abf(_ie, _cur_month_for_recalc)
                    if _fee > 0:
                        TuitionMonth.objects.create(
                            enrollment=_ie,
                            month=_cur_month_for_recalc,
                            fee_amount=_fee,
                            center=_ie.center or getattr(_ie.group, "center", None),
                        )
            except Exception:
                pass

    # ── BARCHA O'QUVCHILAR: O'TGAN OYLAR UCHUN LAZY RECALCULATION ──────────────
    # Muammo: fee jadval/transfer asosida yozilgan, lekin haqiqiy davomat
    # olinmagan → davomat=0 bo'lsa fee=0 qilish kerak.
    # MUHIM: Filter oralig'idan TASHQARI oylar ham (oxirgi 3 oy) tekshiriladi —
    # default (joriy oy) filtrda ham eski noto'g'ri data tuzatilsin.
    _past_months_set = {m for m in period_months if m < _cur_month_for_recalc}
    _back = _cur_month_for_recalc
    for _ in range(3):
        _back = (_back - timedelta(days=1)).replace(day=1)
        _past_months_set.add(_back)
    _past_months = sorted(_past_months_set)
    if _past_months and enrollment_list:
        from education.services.tuition import tuition_month_fee_field as _tff
        from django.db.models import Count as _Cnt
        _fee_fld = _tff()
        _all_enr_map = {e.id: e for e in enrollment_list}

        # Himoyalangan reason'lar: ensure_tuition_month bilan bir xil to'plam.
        # Bularni auto-recalc 0 ga TUSHIRMASLIGI kerak — aks holda qo'lda
        # kiritilgan / to'g'ri oyga ko'chirilgan qarz (davomat yozilmagan bo'lsa)
        # keyingi sahifa ochilganda yana o'chib ketardi.
        _protected_recalc_q = (
            _Q(deleted_reason="manual_cleared")
            | _Q(deleted_reason__startswith="cleanup_")
            | _Q(deleted_reason__startswith="move_future_")
            | _Q(deleted_reason__startswith="reset_")
            | _Q(deleted_reason__startswith="user_edit")
        )
        for _pm in _past_months:
            try:
                # Fee>0 bo'lgan va himoyalanmagan TM larni topamiz (aktiv+inactive)
                _past_tms = list(
                    TuitionMonth.objects.filter(
                        enrollment_id__in=list(_all_enr_map.keys()),
                        month=_pm,
                        is_deleted=False,
                    ).exclude(
                        _protected_recalc_q
                    ).filter(**{f"{_fee_fld}__gt": 0})
                )
                if not _past_tms:
                    continue

                _pm_end = month_last_day(_pm)
                _sg_pairs = [
                    (_all_enr_map[tm.enrollment_id].student_id,
                     _all_enr_map[tm.enrollment_id].group_id)
                    for tm in _past_tms
                    if tm.enrollment_id in _all_enr_map
                ]
                if not _sg_pairs:
                    continue

                _student_ids = list({p[0] for p in _sg_pairs})
                _group_ids = list({p[1] for p in _sg_pairs})

                # Davomat soni (barcha status — shu jumladan sababli)
                _att_any = {
                    (r["student_id"], r["group_id"]): r["cnt"]
                    for r in Attendance.objects.filter(
                        student_id__in=_student_ids,
                        group_id__in=_group_ids,
                        date__gte=_pm,
                        date__lte=_pm_end,
                    ).values("student_id", "group_id").annotate(cnt=_Cnt("id"))
                }

                # Davomat=0 → fee=0 (batch): aktiv va inactive uchun ham
                _zero_ids = [
                    tm.id
                    for tm in _past_tms
                    if tm.enrollment_id in _all_enr_map
                    and _att_any.get((
                        _all_enr_map[tm.enrollment_id].student_id,
                        _all_enr_map[tm.enrollment_id].group_id,
                    ), 0) == 0
                ]
                if _zero_ids:
                    TuitionMonth.objects.filter(id__in=_zero_ids).update(**{_fee_fld: 0})
            except Exception:
                pass

    debt_snapshots = calculate_enrollment_debt_snapshots(
        enrollment_list, period_months
    )

    # ── JAMI QARZ (QARZ ustuni) — TANLANGAN OY(LAR) bo'yicha ─────────────────
    # Har enrollment uchun faqat period_months (filterda tanlangan oy oralig'i)
    # ichidagi TuitionMonth'lar bo'yicha max(0, fee - paid).
    # MUHIM: month__in=period_months bo'lmasa QARZ ustuni BARCHA oylarni
    # yig'ib, oy filtri ishlamay qoladi (iyun tanlansa ham iyul qarzdorlari
    # ko'rinadi). Bu chart, yuqoridagi "Jami qarz" (center_month_debt_summary)
    # va per-enrollment snapshot bilan bir xil period doirasi.
    # Kelajak oy (paid==0) hisobga olinmaydi — student breakdown bilan bir xil.
    from django.db.models import Sum as _SumTot
    from education.services.tuition import tuition_month_fee_field as _fee_f_tot
    _fee_field_tot = _fee_f_tot()
    _cur_mk_debt = today.strftime("%Y-%m")
    _enr_ids_debt = [e.id for e in enrollment_list]
    _tm_fee_rows = list(
        TuitionMonth.objects
        .filter(
            enrollment_id__in=_enr_ids_debt,
            is_deleted=False,
            month__in=period_months,
        )
        .values_list("id", "enrollment_id", "month", _fee_field_tot)
    )
    _tm_paid_map = {}
    if _tm_fee_rows:
        for _r in (
            PaymentAllocation.objects
            .filter(
                tuition_month_id__in=[x[0] for x in _tm_fee_rows],
                tuition_month__is_deleted=False,
                payment__is_deleted=False,
            )
            .values("tuition_month_id")
            .annotate(paid=_SumTot("amount"))
        ):
            _tm_paid_map[_r["tuition_month_id"]] = int(_r["paid"] or 0)
    # Per-enrollment (GURUH bo'yicha) qarz — har guruh alohida sanaladi, netlanmaydi.
    # QARZ ustuni, "Jami qarz" header va diagramma AYNAN shu usulda hisoblanadi:
    # bir guruhdagi ortiqcha (avans) to'lov boshqa guruh qarzini YOPMAYDI. Shu tufayli
    # uch raqam ham bir xil chiqadi (ilgari QARZ ustuni o'quvchi bo'yicha netlanib,
    # diagrammadan past ko'rsatardi).
    enr_total_debt = {}
    for _tmid, _enrid, _mon, _fee in _tm_fee_rows:
        _paid = _tm_paid_map.get(_tmid, 0)
        if _mon.strftime("%Y-%m") > _cur_mk_debt and _paid == 0:
            continue  # kelajak oy, to'lov yo'q — breakdown ham ko'rsatmaydi
        enr_total_debt[_enrid] = enr_total_debt.get(_enrid, 0) + max(0, int(_fee or 0) - _paid)

    # _total_debt_enrs — chart_snapshots (line below) uchun kerak.
    # active non-deferred + inactive enrollments (search/group filtersiz).
    _total_debt_enrs = list(active_enrs_qs.filter(is_deferred=False)) + list(inactive_enrs_qs)

    # ─── JAMI QARZ SUMMASI ───────────────────────────────────────────────────
    # YAGONA MANBA: center_month_debt_summary — Director dashboard ham AYNAN shu
    # funksiyani ishlatadi, shuning uchun ikkala raqam 100% bir xil bo'ladi.
    try:
        from education.services.tuition import center_month_debt_summary as _cmds
        total_center_debt, _ = _cmds(center, period_months)
    except Exception:
        total_center_debt = 0

    # ─── STUDENT MAP (student bo'yicha guruhlash) ────────────────────────────
    student_map = {}   # {student_id: row_dict}

    for e in enrollment_list:
        sid  = e.student_id
        snapshot = debt_snapshots.get(e.id, {})
        # QARZ = o'quvchining BARCHA to'lanmagan oylari yig'indisi (breakdown
        # "Jami qarz" bilan aynan bir xil), faqat tanlangan oy emas.
        debt = int(enr_total_debt.get(e.id, snapshot.get("debt", 0)) or 0)
        _e_unenrolled = getattr(e, "_is_unenrolled", False)
        if _e_unenrolled and debt <= 0:
            continue
        f    = int(snapshot.get("total_fee", 0) or 0)
        p    = int(snapshot.get("total_paid", 0) or 0)
        # lesson_count: jadval bo'yicha haqiqiy dars soni (12 yoki 13).
        # Hisob-kitob denominatori har doim 12 (tuition.py da belgilangan).
        lesson_count = int(snapshot.get("lesson_count", 0) or 0)
        enr_credit = int(snapshot.get("credit_balance", 0) or 0)
        # debt endi kumulativ (o'tgan oylarni ham o'z ichiga oladi) — "O'tgan"
        # satrini alohida ko'rsatmaymiz, aks holda ikki marta sanaladi.
        prev_unpaid = 0
        start_date = enrollment_start_date(e)
        pattern_value = enrollment_lesson_pattern(e)
        pattern_label = lesson_pattern_label(pattern_value)

        _e_unenrolled = getattr(e, "_is_unenrolled", False)
        if sid not in student_map:
            student_map[sid] = {
                "student":     e.student,
                "group_names": [],
                "lesson_pattern_names": [],
                "lesson_pattern_values": [],
                "group_cards": [],
                "total_fee":   0,
                "total_paid":  0,
                "debt":        0,
                "previous_unpaid": 0,
                "credit_balance": 0,
                "lesson_count": 0,
                "start_date":  start_date,
                "enrollment_count": 0,
                "created_at":  e.created_at,
                "enrollment":  e,
                "debt_enrollment_ids": [],
                "primary_debt_enrollment": None,
                "deferred_enrollment": None,
                "is_deferred": False,
                "has_unenrolled_debt": False,
                "teacher_share_only_debt": 0,
                "teacher_share_only_full_total": 0,
                "teacher_share_only_payment_enrollment_id": None,
                "teacher_share_only_unpaid_count": 0,
                "group":       e.group,
                "staff":       getattr(e.group, "oqituvchi", None),
            }

        row = student_map[sid]
        row["enrollment_count"] += 1
        row["total_fee"]       += f
        row["total_paid"]      += p
        row["debt"]            += debt
        row["previous_unpaid"] += prev_unpaid
        row["credit_balance"]  += enr_credit
        row["lesson_count"] += lesson_count
        if _e_unenrolled and debt > 0:
            row["has_unenrolled_debt"] = True
        if start_date and (not row.get("start_date") or start_date < row["start_date"]):
            row["start_date"] = start_date
        if debt > 0:
            row["debt_enrollment_ids"].append(e.id)
            if row["primary_debt_enrollment"] is None:
                row["primary_debt_enrollment"] = e
        if e.created_at and (not row.get("created_at") or e.created_at < row["created_at"]):
            row["created_at"] = e.created_at
        if getattr(e, "is_deferred", False):
            row["is_deferred"] = True
            row["deferred_enrollment"] = e

        if e.group:
            gnom = getattr(e.group, "nom", "")
            if gnom and gnom not in row["group_names"]:
                row["group_names"].append(gnom)
            row["group_cards"].append({
                "enrollment_id": e.id,
                "group_id": e.group_id,
                "group_name": gnom or "—",
                "lesson_pattern": pattern_value,
                "lesson_pattern_label": pattern_label,
                "lesson_count": lesson_count,
                "debt_amount": debt,
                "debt_amount_display": _format_money_exact(debt),
                "fee_amount": f,
                "fee_amount_display": _format_money_exact(f),
                "start_date": start_date,
                "is_unenrolled": _e_unenrolled,
            })
        if pattern_value and pattern_value not in row["lesson_pattern_values"]:
            row["lesson_pattern_values"].append(pattern_value)
        if pattern_label and pattern_label not in row["lesson_pattern_names"]:
            row["lesson_pattern_names"].append(pattern_label)

        full_amount = full_course_amount(e)
        effective_amount = effective_student_payable_amount(e)
        teacher_share_amount = int(getattr(e, "oqituvchi_daromadi", 0) or 0)
        if (
            e.student_payable_amount not in (None, "")
            and full_amount > effective_amount
            and effective_amount == teacher_share_amount
        ):
            row["teacher_share_only_debt"] += max(0, debt)
            row["teacher_share_only_full_total"] += full_amount
            if debt > 0:
                row["teacher_share_only_unpaid_count"] += 1
                if row["teacher_share_only_payment_enrollment_id"] is None:
                    row["teacher_share_only_payment_enrollment_id"] = e.id

    # ─── GROUP LABEL ─────────────────────────────────────────────────────────
    for r in student_map.values():
        # QARZ ustuni = o'quvchining guruhlari bo'yicha qarz yig'indisi (per-enrollment,
        # netlanmasdan) — diagramma va "Jami qarz" header bilan aynan bir xil.
        # r["debt"] yuqorida enr_total_debt'dan yig'ilgan; bu yerda qayta yozilmaydi.
        if r["primary_debt_enrollment"] is not None:
            r["enrollment"] = r["primary_debt_enrollment"]
            r["group"] = r["primary_debt_enrollment"].group
            r["staff"] = getattr(r["group"], "oqituvchi", None)
            r["start_date"] = enrollment_start_date(r["primary_debt_enrollment"])
        r["group_label"] = ", ".join(r["group_names"]) if r["group_names"] else "—"
        r["lesson_pattern_label"] = ", ".join(r["lesson_pattern_names"]) if r["lesson_pattern_names"] else "—"
        r["group_cards"] = sorted(
            r.get("group_cards") or [],
            key=lambda item: ((item.get("group_name") or "").lower(), item.get("enrollment_id") or 0),
        )
        r["visible_group_cards"] = r["group_cards"][:2]
        r["remaining_group_card_count"] = max(0, len(r["group_cards"]) - 2)
        r["has_teacher_share_only"] = (
            r["teacher_share_only_debt"] > 0
            and r["teacher_share_only_full_total"] > r["teacher_share_only_debt"]
        )
        if r["teacher_share_only_unpaid_count"] > 1:
            r["teacher_share_only_payment_enrollment_id"] = None
        r["payment_amount"] = r["teacher_share_only_debt"] if r["has_teacher_share_only"] else r["debt"]
        r["payment_scope"] = "teacher_share_only" if r["has_teacher_share_only"] else "student_total"
        debt_enrollment_ids = r.get("debt_enrollment_ids") or []
        r["payment_enrollment_id"] = debt_enrollment_ids[0] if len(debt_enrollment_ids) == 1 else None

    # ─── QIDIRUV: DB darajasida qilinadi (yuqorida `enrs_base.filter(...)`)
    # Bu yerda Python loop kerak emas — student_map allaqachon faqat mos
    # keluvchi enrollment'lardan tuzilgan.
    all_rows = list(student_map.values())

    def _matches_lesson_pattern_filter(row):
        if not lesson_pattern_filter:
            return True
        return lesson_pattern_filter in (row.get("lesson_pattern_values") or [])

    def _matches_status_filter(row):
        """Status select bo'yicha filtrlash: active / deferred / all."""
        if selected_status == "all":
            return True
        is_deferred = bool(row.get("is_deferred"))
        if selected_status == "deferred":
            return is_deferred
        # active (default) — kechiktirilmagan qarzdorlar
        return not is_deferred

    # Bazaviy qarzdor satrlar — barcha qarz/min/max/status filterlari qo'llangan,
    # lesson_pattern HALI qo'llanmagan (lesson_pattern badge sonlari uchun kerak).
    debt_filter_base_rows = []
    for row in all_rows:
        if not row["group_names"]:
            continue
        if row["debt"] <= 0:
            continue
        if min_debt and row["debt"] < min_debt:
            continue
        if max_debt and row["debt"] > max_debt:
            continue
        if not _matches_status_filter(row):
            continue
        debt_filter_base_rows.append(row)

    lesson_pattern_filter_counts = {
        "all": len(debt_filter_base_rows),
        Enrollment.LESSON_PATTERN_ODD: sum(
            1 for row in debt_filter_base_rows if Enrollment.LESSON_PATTERN_ODD in (row.get("lesson_pattern_values") or [])
        ),
        Enrollment.LESSON_PATTERN_EVEN: sum(
            1 for row in debt_filter_base_rows if Enrollment.LESSON_PATTERN_EVEN in (row.get("lesson_pattern_values") or [])
        ),
        Enrollment.LESSON_PATTERN_DAILY: sum(
            1 for row in debt_filter_base_rows if Enrollment.LESSON_PATTERN_DAILY in (row.get("lesson_pattern_values") or [])
        ),
    }

    # ─── STATISTIKA ──────────────────────────────────────────────────────────
    # debt_filter_base_rows allaqachon qarz/min/max/status bo'yicha filtrlangan —
    # uning ustiga faqat lesson_pattern_filter qolgan.
    debtor_rows = [row for row in debt_filter_base_rows if _matches_lesson_pattern_filter(row)]
    debtors_count = len(debtor_rows)

    # paid / no_group statistikasi (badge'lar uchun) — full set'dan hisoblanadi
    paid_count = 0
    no_group_count = 0
    for r in all_rows:
        if not _matches_lesson_pattern_filter(r):
            continue
        if not r["group_names"]:
            no_group_count += 1
        elif r["debt"] <= 0:
            paid_count += 1

    display_rows = debtor_rows

    filtered_debt   = sum(r["debt"] for r in display_rows)

    # Jami qarz: jadvaldagi ma'lumotlar bilan izchil (arxivlangan guruhlar chiqarib tashlangan),
    # status filteri qo'llangan, lekin min/max qarz filterlari qo'llanmagan.
    total_center_debt = sum(
        r["debt"] for r in all_rows
        if r.get("group_names") and r["debt"] > 0 and _matches_status_filter(r)
    )

    # Chart: Jami qarz bilan bir xil enrollments (_total_debt_enrs) ishlatamiz.
    # preload_group_schedules allaqachon yuqorida enrollment_list uchun chaqirilgan,
    # lekin _total_debt_enrs yangi guruhlarni o'z ichiga olishi mumkin — yangilash.
    from education.services.tuition import preload_group_schedules as _pgs2
    _pgs2({e.group_id for e in _total_debt_enrs if e.group_id})
    preload_enrollment_history_starts(_total_debt_enrs)
    chart_snapshots = calculate_enrollment_debt_snapshots(
        _total_debt_enrs,
        chart_months,
    )
    graph_map = {chart_month: 0 for chart_month in chart_months}
    for snapshot in chart_snapshots.values():
        month_details = snapshot.get("months", {})
        for chart_month in chart_months:
            graph_map[chart_month] += int(
                month_details.get(chart_month, {}).get("debt", 0) or 0
            )
    chart_series = [graph_map[month] for month in chart_months]
    chart_labels = [_human_month_label(month) for month in chart_months]
    chart_period_label = _human_month_period_label(chart_months[0], chart_months[-1])
    selected_period_label = _human_period_label(selected_from, selected_to)
    if used_default_period:
        selected_period_label = "Joriy oy qarzi · o'tgan oylar uchun filtrni o'zgartiring"

    # ─── PAGINATOR ───────────────────────────────────────────────────────────
    from django.core.paginator import Paginator
    paginator   = Paginator(display_rows, per_page)
    page_obj    = paginator.get_page(request.GET.get("page"))

    # ─── GURUHLAR (filter uchun) ──────────────────────────────────────────────
    groups_qs = Group.objects.filter(is_archived=False)
    if center:
        groups_qs = groups_qs.filter(center=center)

    context = {
        "page_obj":       page_obj,
        "groups":         groups_qs,
        "selected_group": group_id,
        "total_debt":     total_center_debt,
        "filtered_debt":  filtered_debt,
        "chart_data":     chart_series,
        "chart_labels":   chart_labels,
        "chart_mode":     chart_mode,
        "chart_kicker":   "Oxirgi 12 oy",
        "chart_period_label": chart_period_label,
        "selected_period_label": selected_period_label,
        "q":              q,
        "selected_lesson_pattern_filter": lesson_pattern_filter,
        "lesson_pattern_filter_counts": lesson_pattern_filter_counts,
        "min_debt":       min_debt if min_debt else "",
        "max_debt":       max_debt if max_debt else "",
        "selected_status": selected_status,
        "date_from":      selected_from.isoformat(),
        "date_to":        selected_to.isoformat(),
        "pay_month":      str(pay_month_int) if pay_month_int else "",
        "effective_pay_month": effective_pay_month.strftime("%Y-%m"),
        "per_page":       per_page,
        "page_size_options": allowed_page_sizes,
        "uz_months": [
            (1, "Yanvar"),   (2, "Fevral"),   (3, "Mart"),    (4, "Aprel"),
            (5, "May"),      (6, "Iyun"),     (7, "Iyul"),    (8, "Avgust"),
            (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
        ],
        "stats_summary": {
            "total":    sum(1 for row in all_rows if _matches_lesson_pattern_filter(row)),
            "debtors":  debtors_count,
            "paid":     paid_count,
            "no_group": no_group_count,
        },
    }

    try:
        from store.views import _ensure_default_payment_methods as _seed_pm
        from store.models import PaymentMethod as _PM
        if center:
            _seed_pm(center)
            context["payment_methods"] = list(
                _PM.objects.filter(center=center, is_active=True).order_by('nom')
            )
        else:
            context["payment_methods"] = []
    except Exception:
        context["payment_methods"] = []

    return render(request, "education/qarzdorlar.html", context)



@login_required
@require_GET
@require_feature("finance")
def month_preview(request):
    from core.tenant import get_request_center

    if not user_can_manage_payments(request.user):
        return HttpResponseForbidden("Ruxsat yo'q.")

    center = get_request_center(request)

    month_raw = (request.GET.get("month") or "").strip()
    month = parse_month_str(month_raw) if month_raw else timezone.localdate().replace(day=1)
    if month is None:
        month = timezone.localdate().replace(day=1)

    group_id = _get_int(request.GET, "group", 0)

    fee_field = tuition_month_fee_field()
    m_start = month_first_day(month)
    m_end = month_last_day(m_start)

    enrollments_qs = (
        Enrollment.objects
        .select_related("student", "group")
        .filter(is_active=True, student__is_archived=False, group__is_archived=False, group__is_deleted=False)
    )
    if center:
        enrollments_qs = enrollments_qs.filter(center=center)
    if group_id:
        enrollments_qs = enrollments_qs.filter(group_id=group_id)

    existing_tm = {
        tm.enrollment_id: tm
        for tm in TuitionMonth.all_objects.filter(
            enrollment__in=enrollments_qs, month=m_start, is_deleted=False
        )
    }

    rows = []
    total_current = 0
    total_prorated = 0
    total_reconciled = 0

    for enr in enrollments_qs:
        tm = existing_tm.get(enr.id)
        current_fee = int(getattr(tm, fee_field, 0) or 0) if tm else 0
        prorated = int(prorated_monthly_fee(enr, m_start) or 0)
        reconciled = int(attendance_based_fee(enr, m_start) or 0)
        billable = billable_attendance_count(enr, m_start)

        start_d = enrollment_start_date(enr)
        period_start = max(start_d, m_start)
        expected_lessons = expected_lessons_in_period(enr, period_start, m_end) if period_start <= m_end else 0

        delta = reconciled - current_fee

        rows.append({
            "enrollment": enr,
            "student": enr.student,
            "group": enr.group,
            "start_date": start_d,
            "effective_price": effective_student_payable_amount(enr),
            "full_price": full_course_amount(enr),
            "current_fee": current_fee,
            "prorated_fee": prorated,
            "reconciled_fee": reconciled,
            "billable_lessons": billable,
            "expected_lessons": expected_lessons,
            "delta": delta,
            "has_tm": tm is not None,
        })

        total_current += current_fee
        total_prorated += prorated
        total_reconciled += reconciled

    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)

    group_options = (
        Group.objects.filter(is_archived=False)
        .filter(center=center) if center else Group.objects.filter(is_archived=False)
    )

    return render(
        request,
        "education/month_preview.html",
        {
            "month": m_start,
            "month_str": m_start.strftime("%Y-%m"),
            "rows": rows,
            "total_current": total_current,
            "total_prorated": total_prorated,
            "total_reconciled": total_reconciled,
            "total_delta": total_reconciled - total_current,
            "group_options": group_options.order_by("nom"),
            "selected_group_id": group_id,
        },
    )



@require_POST
@login_required
def edit_tuition_month_fee(request, tm_id):
    """
    TuitionMonth.fee_amount ni yangilaydi.
    Multi-tenant: TuitionMonth faqat joriy markazga tegishli bo'lsa ruxsat.
    """
    if not user_can_manage_payments(request.user):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q."}, status=403)

    center = get_active_center(request)
    qs = TuitionMonth.objects.select_related("enrollment", "enrollment__group")
    if center:
        from django.db.models import Q as _Q
        qs = qs.filter(
            _Q(center=center)
            | _Q(enrollment__center=center)
            | _Q(enrollment__group__center=center)
        )
    tm = get_object_or_404(qs, id=tm_id)

    new_fee_raw = (request.POST.get("new_fee") or "").strip()
    note = (request.POST.get("note") or "").strip()

    try:
        new_fee = int(Decimal(new_fee_raw or "0"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Noto'g'ri summa."}, status=400)

    if new_fee < 0:
        return JsonResponse({"ok": False, "error": "Summa manfiy bo'lishi mumkin emas."}, status=400)

    fee_field = tuition_month_fee_field()
    setattr(tm, fee_field, new_fee)
    update_fields = [fee_field]
    if note:
        # Note ni TuitionMonth'da saqlash uchun note maydoni bo'lsa
        from education.services.tuition import _model_has_field as _mhf
        if _mhf(TuitionMonth, "note"):
            tm.note = note
            update_fields.append("note")
    tm.save(update_fields=update_fields)

    month_label = f"{_UZ_MONTHS.get(tm.month.month, tm.month.month)} {tm.month.year}"
    return JsonResponse({
        "ok": True,
        "new_fee": new_fee,
        "new_fee_display": format_money(new_fee),
        "month_label": month_label,
    })



@require_POST
@login_required
def edit_student_month_debt(request, student_id):
    """
    O'quvchining bitta oy uchun umumiy qarz miqdorini o'rnatadi.
    Bir oy ichida bir nechta TuitionMonth bo'lsa ham hammasi yangilanadi:
    - Birinchi TM: fee = new_debt + TM.paid  (bu TMda qarz = new_debt)
    - Qolgan TMlar: fee = TM.paid            (bu TMlarda qarz = 0)
    POST: month="2026-04", new_debt=500000
    """
    if not user_can_manage_payments(request.user):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q."}, status=403)

    center = get_active_center(request)

    month_str = (request.POST.get("month") or "").strip()
    new_debt_raw = (request.POST.get("new_debt") or "").strip()

    try:
        y, m = int(month_str[:4]), int(month_str[5:7])
        month_date = date(y, m, 1)
    except Exception:
        return JsonResponse({"ok": False, "error": "Noto'g'ri oy formati."}, status=400)

    # Kelajak oylarni tahrirlash mumkin emas — ular avtomatik hisoblanadi
    cur_month_first = timezone.localdate().replace(day=1)
    if month_date > cur_month_first:
        return JsonResponse({"ok": False, "error": "Kelajakdagi oy uchun to'lovni tahrirlash mumkin emas. Oy kelganda avtomatik hisoblanadi."}, status=400)

    try:
        new_debt = int(Decimal(new_debt_raw or "0"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Noto'g'ri summa."}, status=400)

    if new_debt < 0:
        return JsonResponse({"ok": False, "error": "Qarz manfiy bo'lishi mumkin emas."}, status=400)

    from django.db.models import Q as _Q2
    user_qs = User.objects.filter(role="student")
    if center:
        user_qs = user_qs.filter(center=center)
    student = get_object_or_404(user_qs, id=student_id)

    # Enrollment filter must match student_monthly_breakdown exactly so that
    # the same TuitionMonths are updated here and read there.
    _center_q_edit = (
        _Q2(center=center)
        | _Q2(center__isnull=True, group__center=center)
        | _Q2(center__isnull=True, student__center=center)
    )
    # all_objects — guruhdan CHIQARILGAN (is_deleted=True) enrollment oyini ham
    # tahrirlash mumkin bo'lsin (breakdown all_objects bilan izchil). Aks holda
    # chiqarilgan o'quvchi oyini qalamcha bilan saqlab bo'lmasdi ("yozuv topilmadi").
    enrollments_for_student = Enrollment.all_objects.filter(student=student)
    if center:
        enrollments_for_student = enrollments_for_student.filter(_center_q_edit)

    tms_qs = TuitionMonth.objects.filter(
        enrollment__in=enrollments_for_student,
        month=month_date,
        is_deleted=False,
    ).select_related("enrollment").prefetch_related(
        Prefetch(
            "allocations",
            queryset=PaymentAllocation.objects.filter(payment__is_deleted=False),
            to_attr="active_allocations",
        )
    )

    tms = list(tms_qs.order_by("id"))
    if not tms:
        return JsonResponse({"ok": False, "error": "Bu oy uchun yozuv topilmadi."}, status=404)

    fee_field = tuition_month_fee_field()
    paid_per_tm = [sum(int(a.amount or 0) for a in tm.active_allocations) for tm in tms]
    total_paid_now = sum(paid_per_tm)

    # new_paid: to'langan summani kamaytirish (ixtiyoriy)
    new_paid_raw = request.POST.get("new_paid")
    new_paid = None
    if new_paid_raw is not None:
        try:
            new_paid = int(Decimal(new_paid_raw.strip()))
        except Exception:
            return JsonResponse({"ok": False, "error": "Noto'g'ri to'langan summa."}, status=400)
        if new_paid < 0:
            return JsonResponse({"ok": False, "error": "To'langan summa manfiy bo'lishi mumkin emas."}, status=400)
        if new_paid > total_paid_now:
            return JsonResponse({"ok": False, "error": "To'langan summani oshirish mumkin emas."}, status=400)

    with transaction.atomic():
        # Agar to'langan kamaytirish so'ralgan bo'lsa
        affected_payment_ids: set = set()
        if new_paid is not None and new_paid < total_paid_now:
            to_free = total_paid_now - new_paid
            # Barcha allocationlarni ko'rib chiqib, kerakli miqdorni ozod qilamiz
            for tm in tms:
                if to_free <= 0:
                    break
                allocs_sorted = sorted(tm.active_allocations, key=lambda a: a.amount, reverse=True)
                for alloc in allocs_sorted:
                    if to_free <= 0:
                        break
                    affected_payment_ids.add(alloc.payment_id)
                    alloc_amt = int(alloc.amount or 0)
                    if alloc_amt <= to_free:
                        # Bu allocationni to'liq o'chiramiz
                        to_free -= alloc_amt
                        Enrollment.objects.filter(pk=tm.enrollment_id).update(
                            credit_balance=F("credit_balance") + alloc_amt
                        )
                        alloc.is_deleted = True
                        alloc.save(update_fields=["is_deleted"])
                    else:
                        # Qisman kamaytiramiz
                        alloc.amount = alloc_amt - to_free
                        alloc.save(update_fields=["amount"])
                        Enrollment.objects.filter(pk=tm.enrollment_id).update(
                            credit_balance=F("credit_balance") + to_free
                        )
                        to_free = 0
            # paid_per_tm ni yangi holat bilan yangilaymiz
            paid_per_tm = [
                sum(int(a.amount or 0) for a in tm.allocations.filter(is_deleted=False))
                for tm in tms
            ]

            # To'lovlar bo'limida ham o'zgarishni aks ettirish:
            # ta'sirlangan Payment yozuvlarini yangilaymiz (yoki o'chiramiz)
            if affected_payment_ids:
                for pay_id in affected_payment_ids:
                    remaining_alloc = (
                        PaymentAllocation.objects
                        .filter(payment_id=pay_id, is_deleted=False)
                        .aggregate(s=Sum("amount"))["s"] or 0
                    )
                    pay_obj = Payment.all_objects.filter(pk=pay_id, is_deleted=False).first()
                    if pay_obj is None:
                        continue
                    if remaining_alloc == 0:
                        # Hech qanday aktiv allocation qolmadi → To'lovlar bo'limidan o'chiramiz
                        pay_obj.is_deleted = True
                        pay_obj.save(update_fields=["is_deleted"])
                    elif remaining_alloc < int(pay_obj.summa or 0):
                        # Qisman kamaytirish → summani yangi miqdorga o'rnatamiz
                        pay_obj.summa = remaining_alloc
                        # cash_amount ni ham mutanosib ravishda kamaytiramiz
                        old_cash = int(pay_obj.cash_amount or 0)
                        if old_cash > remaining_alloc:
                            pay_obj.cash_amount = remaining_alloc
                        pay_obj.save(update_fields=["summa", "cash_amount"])

        # Birinchi TM: fee = new_debt + uning to'lovi (qarz = new_debt)
        setattr(tms[0], fee_field, new_debt + paid_per_tm[0])
        tms[0].save(update_fields=[fee_field])

        # Qolgan TMlar: fee = to'lovi (qarz = 0)
        for i in range(1, len(tms)):
            setattr(tms[i], fee_field, paid_per_tm[i])
            tms[i].save(update_fields=[fee_field])

        # Foydalanuvchi qo'lda o'rnatgan fee ni _etm (ensure_tuition_month) qayta
        # yozib tashlaydi (schedule asosida hisoblaydi) — shu to'g'ri yozuvni
        # himoyalamiz: deleted_reason = "user_edit" => _etm bu TMni o'tkazib yuboradi.
        _protect_ids = set()
        for tm in tms:
            _cur_reason = getattr(tm, "deleted_reason", None) or ""
            if _cur_reason not in ("manual_cleared",) and not _cur_reason.startswith(
                ("cleanup_", "move_future_", "reset_", "user_edit")
            ):
                tm.deleted_reason = "user_edit"
                tm.save(update_fields=["deleted_reason"])
                _protect_ids.add(tm.id)

        # Inactive enrollment uchun new_debt=0: _etm qayta hisoblashining oldini
        # olish uchun TuitionMonth ni manual_cleared bilan soft-delete qilamiz.
        # Aks holda keyingi sahifa yuklanishida _etm davomat asosida fee ni
        # qayta tiklaydi (chiqarilgan o'quvchi uchun noto'g'ri).
        if new_debt == 0 and total_paid_now == 0:
            for tm in tms:
                _enr = tm.enrollment
                _is_inactive = (
                    not getattr(_enr, "is_active", True)
                    or getattr(_enr, "is_deleted", False)
                )
                if _is_inactive:
                    tm.is_deleted = True
                    tm.deleted_reason = "manual_cleared"
                    tm.deleted_at = timezone.now()
                    tm.save(update_fields=["is_deleted", "deleted_reason", "deleted_at"])

    # DB dan haqiqiy qiymatni o'qiymiz (Python object qiymatiga ishonmaymiz)
    tms[0].refresh_from_db(fields=[fee_field])
    saved_fee = int(getattr(tms[0], fee_field, 0) or 0) if tms else 0
    saved_paid = paid_per_tm[0] if paid_per_tm else 0
    expected_fee = new_debt + (paid_per_tm[0] if paid_per_tm else 0)
    if saved_fee != expected_fee:
        return JsonResponse({"ok": False, "error": "Ma'lumot saqlanmadi. Qaytadan urinib ko'ring."}, status=500)
    saved_debt = max(0, saved_fee - saved_paid)
    total_debt = get_student_total_debt(student, center)
    return JsonResponse({"ok": True, "fee": saved_fee, "paid": saved_paid, "debt": saved_debt, "total_debt": total_debt})



@require_POST
@login_required
def delete_student_month(request, student_id):
    """
    O'quvchining bitta kelajak oylik TuitionMonth yozuvlarini o'chiradi.
    Faqat joriy oydan KEYIN bo'lgan oylar uchun ruxsat beriladi.
    Agar to'lov allocatsiyalari mavjud bo'lsa, ular ham o'chiriladi va
    tegishli summa enrollment.credit_balance ga qaytariladi.
    POST: month="2026-06"
    """
    if not user_can_manage_payments(request.user):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q."}, status=403)

    center = get_active_center(request)
    month_str = (request.POST.get("month") or "").strip()

    try:
        y, m_num = int(month_str[:4]), int(month_str[5:7])
        month_date = date(y, m_num, 1)
    except Exception:
        return JsonResponse({"ok": False, "error": "Noto'g'ri oy formati."}, status=400)

    today = date.today()
    current_month = date(today.year, today.month, 1)
    if month_date <= current_month:
        return JsonResponse({"ok": False, "error": "Faqat kelajak oylarni o'chirish mumkin."}, status=400)

    from django.db.models import Q as _Q4
    user_qs = User.objects.filter(role="student")
    if center:
        user_qs = user_qs.filter(center=center)
    student = get_object_or_404(user_qs, id=student_id)

    tms_qs = TuitionMonth.objects.filter(
        enrollment__student=student,
        month=month_date,
        is_deleted=False,
    ).prefetch_related(
        Prefetch(
            "allocations",
            queryset=PaymentAllocation.objects.filter(is_deleted=False),
            to_attr="active_allocations",
        )
    )
    if center:
        tms_qs = tms_qs.filter(
            _Q4(center=center)
            | _Q4(enrollment__center=center)
            | _Q4(enrollment__group__center=center)
        )

    tms = list(tms_qs)
    if not tms:
        return JsonResponse({"ok": False, "error": "Bu oy uchun yozuv topilmadi."}, status=404)

    with transaction.atomic():
        for tm in tms:
            has_alloc = bool(tm.active_allocations)

            if has_alloc:
                # To'lov bor: to'lovni bekor qilamiz.
                # Agar to'lov faqat shu oyga edi → to'lovni ham o'chiramiz (credit yo'q).
                # Agar to'lov boshqa oylarga ham tegishli → freed qismni credit_balance ga,
                # to'lov summasini kamaytiramiz.
                affected_pay_ids = {alloc.payment_id for alloc in tm.active_allocations}
                freed = sum(int(a.amount or 0) for a in tm.active_allocations)
                for alloc in tm.active_allocations:
                    alloc.is_deleted = True
                    alloc.save(update_fields=["is_deleted"])

                for pay_id in affected_pay_ids:
                    remaining_alloc = (
                        PaymentAllocation.objects
                        .filter(payment_id=pay_id, is_deleted=False)
                        .aggregate(s=Sum("amount"))["s"] or 0
                    )
                    pay_obj = Payment.all_objects.filter(pk=pay_id, is_deleted=False).first()
                    if pay_obj is None:
                        continue
                    if remaining_alloc == 0:
                        # To'lov butunlay bekor — o'chiramiz, credit yo'q
                        pay_obj.is_deleted = True
                        pay_obj.save(update_fields=["is_deleted"])
                    else:
                        # Qisman bekor: freed miqdor credit_balance ga
                        Enrollment.objects.filter(pk=tm.enrollment_id).update(
                            credit_balance=F("credit_balance") + freed
                        )
                        if remaining_alloc < int(pay_obj.summa or 0):
                            pay_obj.summa = remaining_alloc
                            old_cash = int(pay_obj.cash_amount or 0)
                            if old_cash > remaining_alloc:
                                pay_obj.cash_amount = remaining_alloc
                            pay_obj.save(update_fields=["summa", "cash_amount"])

                # To'lov bekor qilingani uchun shu oy qayta qarz bo'lishi kerak →
                # "future_deleted" dan _etm bu TM ni tiklaydi va oy yana to'lanmagan
                # ko'rinadi. Keyingi to'lov shu oyga ketadi.
                tm.is_deleted = True
                tm.deleted_reason = "future_deleted"
                tm.deleted_at = timezone.now()
                tm.save(update_fields=["is_deleted", "deleted_reason", "deleted_at"])
            else:
                # To'lov yo'q: oy jadvaldan butunlay o'chiriladi (o'quvchi ketmoqda).
                # "manual_cleared" → _etm bu oyni qayta tiklamaydi.
                tm.is_deleted = True
                tm.deleted_reason = "manual_cleared"
                tm.deleted_at = timezone.now()
                tm.save(update_fields=["is_deleted", "deleted_reason", "deleted_at"])

    return JsonResponse({"ok": True})



@require_POST
@login_required
def reset_student_month_payments(request, student_id):
    """
    O'quvchining bitta oyi uchun barcha to'lov allocatsiyalarini bekor qiladi —
    oy TO'LIQ QARZ holatiga qaytadi (credit_balance ga o'tkazilmaydi!).
    Bekor qilingan qism To'lovlar bo'limida ham kamayadi/o'chadi.
    POST: month="2026-06"
    """
    if not user_can_manage_payments(request.user):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q."}, status=403)

    center = get_active_center(request)
    month_str = (request.POST.get("month") or "").strip()

    try:
        y, m_num = int(month_str[:4]), int(month_str[5:7])
        month_date = date(y, m_num, 1)
    except Exception:
        return JsonResponse({"ok": False, "error": "Noto'g'ri oy formati."}, status=400)

    from django.db.models import Q as _Q5
    user_qs = User.objects.filter(role="student")
    if center:
        user_qs = user_qs.filter(center=center)
    student = get_object_or_404(user_qs, id=student_id)

    tms_qs = TuitionMonth.objects.filter(
        enrollment__student=student,
        month=month_date,
        is_deleted=False,
    ).prefetch_related(
        Prefetch(
            "allocations",
            queryset=PaymentAllocation.objects.filter(is_deleted=False, payment__is_deleted=False),
            to_attr="active_allocations",
        )
    )
    if center:
        tms_qs = tms_qs.filter(
            _Q5(center=center)
            | _Q5(enrollment__center=center)
            | _Q5(enrollment__group__center=center)
        )

    tms = list(tms_qs)
    if not tms:
        return JsonResponse({"ok": False, "error": "Bu oy uchun yozuv topilmadi."}, status=404)

    total_freed = 0
    with transaction.atomic():
        affected_pay_ids: set = set()
        for tm in tms:
            for alloc in tm.active_allocations:
                affected_pay_ids.add(alloc.payment_id)
                total_freed += int(alloc.amount or 0)
                alloc.is_deleted = True
                alloc.save(update_fields=["is_deleted"])

        # To'lovlar bo'limini sinxronlash: allocation qolmagan payment
        # o'chiriladi, qisman qolgani kamaytiriladi.
        for pay_id in affected_pay_ids:
            remaining_alloc = (
                PaymentAllocation.objects
                .filter(payment_id=pay_id, is_deleted=False)
                .aggregate(s=Sum("amount"))["s"] or 0
            )
            pay_obj = Payment.all_objects.filter(pk=pay_id, is_deleted=False).first()
            if pay_obj is None:
                continue
            if remaining_alloc == 0:
                pay_obj.is_deleted = True
                pay_obj.save(update_fields=["is_deleted"])
            elif remaining_alloc < int(pay_obj.summa or 0):
                pay_obj.summa = remaining_alloc
                old_cash = int(pay_obj.cash_amount or 0)
                if old_cash > remaining_alloc:
                    pay_obj.cash_amount = remaining_alloc
                pay_obj.save(update_fields=["summa", "cash_amount"])

        # Fee ni to'g'ri qiymatga qaytaramiz. ANIQ QOIDA:
        #   O'TGAN oy  → haqiqiy davomat asosida (nechta darsga kelgan bo'lsa
        #                shuncha × dars narxi). Davomat 0 bo'lsa qarz ham 0.
        #   JORIY oy   → to'liq oylik narx (jadval asosida).
        from education.services.tuition import (
            prorated_monthly_fee as _pmf,
            attendance_based_fee as _abf,
        )
        fee_field = tuition_month_fee_field()
        _cur_month_first = timezone.localdate().replace(day=1)
        _is_past_month = month_date < _cur_month_first
        for tm in tms:
            if _is_past_month:
                normal_fee = int(_abf(tm.enrollment, month_date) or 0)
            else:
                normal_fee = int(_pmf(tm.enrollment, month_date) or 0)
            _upd = []
            if int(getattr(tm, fee_field, 0) or 0) != normal_fee:
                setattr(tm, fee_field, normal_fee)
                _upd.append(fee_field)
            if _is_past_month:
                # O'tgan oy davomat asosidagi qiymatini _etm (jadval asosida
                # hisoblaydi) qayta yozib tashlamasin — user_edit bilan
                # himoyalaymiz. Davomat o'zgarsa signal baribir yangilaydi.
                if not (getattr(tm, "deleted_reason", None) or ""):
                    tm.deleted_reason = "user_edit"
                    _upd.append("deleted_reason")
            else:
                # Joriy oy: himoya kerak emas — _etm ham xuddi shu to'liq
                # narxni hisoblaydi. Eski user_edit qolib ketgan bo'lsa olib
                # tashlaymiz.
                if (getattr(tm, "deleted_reason", None) or "").startswith("user_edit"):
                    tm.deleted_reason = ""
                    _upd.append("deleted_reason")
            if _upd:
                tm.save(update_fields=_upd)

            # Credit balansni 0 qilamiz — aks holda keyingi oy yaratilganda
            # bekor qilingan pul avtomatik to'lov sifatida qayta yoziladi.
            Enrollment.objects.filter(pk=tm.enrollment_id).update(credit_balance=0)

        # YETIM to'lovlarni ham o'chiramiz: shu oy sanasi bilan yozilgan,
        # hech qanday aktiv allocation'i qolmagan paymentlar. Ular turgani
        # bilan _auto_link_payment_to_tm har sahifa yuklanishida ularni shu
        # oyga qayta bog'lab, "avtomatik to'lov" sifatida tiriltiraveradi.
        _enr_ids = [tm.enrollment_id for tm in tms]
        _orphan_pays = Payment.objects.filter(
            enrollment_id__in=_enr_ids,
            is_deleted=False,
            paid_date__year=month_date.year,
            paid_date__month=month_date.month,
        )
        for _op in _orphan_pays:
            _live_alloc = (
                PaymentAllocation.objects
                .filter(payment=_op, is_deleted=False)
                .aggregate(s=Sum("amount"))["s"] or 0
            )
            if _live_alloc == 0 and int(_op.summa or 0) > 0:
                _op.is_deleted = True
                _op.save(update_fields=["is_deleted"])

    total_debt = get_student_total_debt(student, center)
    return JsonResponse({"ok": True, "freed": total_freed, "total_debt": total_debt})



@login_required
def student_monthly_breakdown(request, student_id):
    """
    O'quvchi barcha enrollments bo'yicha oylik to'lov breakdown'ini JSON formatida qaytaradi.
    """
    center = get_active_center(request)

    user_qs = User.objects.filter(role="student")
    if center:
        _enr_cq = (
            Q(center=center)
            | Q(center__isnull=True, group__center=center)
            | Q(center__isnull=True, student__center=center)
        )
        user_qs = user_qs.filter(
            Q(center=center)
            | Q(pk__in=Enrollment.all_objects.filter(_enr_cq).values("student_id"))
        )
    student = get_object_or_404(user_qs, id=student_id)

    from django.db.models import Q as _Q
    _center_q_mb = (
        _Q(center=center)
        | _Q(center__isnull=True, group__center=center)
        | _Q(center__isnull=True, student__center=center)
    )
    # MUHIM: all_objects — guruhdan CHIQARILGAN (is_deleted=True) enrollment'lar
    # ham kiritiladi. Aks holda chiqarilgan o'quvchining o'qigan oyi (mas. iyun)
    # qarzi to'lov oynasida (oylik breakdown) umuman ko'rinmaydi va to'lov
    # qilib bo'lmaydi — qarz esa qarzdorlar ro'yxatida turadi.
    enrollments = Enrollment.all_objects.filter(student=student).select_related("group")
    if center:
        enrollments = enrollments.filter(_center_q_mb)

    fee_field = tuition_month_fee_field()

    # Barcha TuitionMonth'larni yig'amiz
    all_tms = (
        TuitionMonth.objects
        .filter(enrollment__in=enrollments, is_deleted=False)
        .select_related("enrollment__group")
        .order_by("month")
        .prefetch_related(
            Prefetch(
                "allocations",
                queryset=PaymentAllocation.objects.filter(
                    payment__is_deleted=False,
                ).select_related("payment"),
                to_attr="active_allocations",
            )
        )
    )

    # Oylar bo'yicha grupplaymiz
    from collections import defaultdict
    # tm_id_map: m_key -> list of (tm_id, enrollment_id) — fee tahrirlash uchun
    month_map = defaultdict(lambda: {"fee": 0, "paid": 0, "payments": [], "enrollments": [], "tm_ids": [], "price_per_lesson": 0, "monthly_lessons": 0})

    for tm in all_tms:
        m_key = tm.month.strftime("%Y-%m")
        fee = int(getattr(tm, fee_field, 0) or 0)
        paid = sum(int(a.amount or 0) for a in tm.active_allocations)
        month_map[m_key]["fee"] += fee
        month_map[m_key]["paid"] += paid
        month_map[m_key]["enrollments"].append(tm.enrollment_id)
        month_map[m_key]["tm_ids"].append(tm.id)
        # Bitta dars narxini enrollment dan olamiz (birinchi TuitionMonth dan)
        if not month_map[m_key]["price_per_lesson"] and tm.enrollment:
            enr = tm.enrollment
            ml = int(getattr(enr.group, "oy_dars_soni", 0) or 0) or int(getattr(enr, "monthly_lessons", 0) or 0) or 12
            kn = int(getattr(enr, "kurs_narhi", 0))
            month_map[m_key]["monthly_lessons"] = ml
            month_map[m_key]["price_per_lesson"] = round(kn / ml) if ml > 0 else 0

        group_name = tm.enrollment.group.nom if tm.enrollment and tm.enrollment.group else ""
        for alloc in tm.active_allocations:
            p = alloc.payment
            p_note = getattr(p, "note", "") or ""
            month_map[m_key]["payments"].append({
                "amount": int(alloc.amount or 0),
                "note": p_note,
                "group": group_name,
            })

    cur_month_key = timezone.localdate().strftime("%Y-%m")

    months_result = []
    total_debt = 0
    for m_key in sorted(month_map.keys()):
        entry = month_map[m_key]
        year, month_num = int(m_key[:4]), int(m_key[5:7])
        month_label = f"{_UZ_MONTHS.get(month_num, month_num)} {year}"
        fee = entry["fee"]
        paid = entry["paid"]
        debt = max(0, fee - paid)

        # Kelajak oy va to'lov yo'q — ko'rsatmayiz.
        # Faqat ortiqcha to'lov (paid>0) bo'lsa kelajak oy ko'rinadi.
        is_future = m_key > cur_month_key
        if is_future and paid == 0:
            continue

        total_debt += debt

        if fee <= 0 and paid > 0:
            status = "paid"
        elif fee <= 0:
            # Kelajak oy uchun fee hali hisoblanmagan — ko'rsatilmaydi (yuqorida skip qilingan)
            # Joriy/o'tgan oy uchun fee=0: to'langan deb hisoblanadi
            status = "paid"
        elif paid <= 0:
            status = "debtor"
        elif paid >= fee:
            status = "paid"
        else:
            status = "partial"

        # tm_id: birinchi TuitionMonth ID (fee tahrirlash uchun; enrollment_id bilan birga ishlatiladi)
        tm_ids = entry.get("tm_ids", [])
        tm_id = tm_ids[0] if tm_ids else None

        months_result.append({
            "month": m_key,
            "month_label": month_label,
            "fee": fee,
            "paid": paid,
            "debt": debt,
            "status": status,
            "payments": entry["payments"],
            "tm_id": tm_id,
            "tm_ids": tm_ids,
            "price_per_lesson": entry.get("price_per_lesson", 0),
            "monthly_lessons": entry.get("monthly_lessons", 0),
        })

    response = JsonResponse({
        "months": months_result,
        "total_debt": total_debt,
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response

