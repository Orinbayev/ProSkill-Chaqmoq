"""
Auto-split from education/views.py (phase 7 god-file reduction).
Public API re-exported via education.views package.
"""
from __future__ import annotations

from .common import *  # noqa: F403


@transaction.atomic
def enrollment_edit(request, enrollment_id):
    center = get_active_center(request)
    qs = Enrollment.all_objects.select_related("student", "group", "group__category_obj", "course")
    if center:
        qs = qs.filter(
            Q(center=center)
            | Q(center__isnull=True, group__center=center)
            | Q(center__isnull=True, student__center=center)
        )

    enr = get_object_or_404(qs, id=enrollment_id)
    # student_enrollments uchun faqat o'chirilmagan (is_deleted=False) aktiv enrollmentlar
    active_qs = Enrollment.objects.select_related("student", "group", "group__category_obj", "course")
    if center:
        active_qs = active_qs.filter(
            Q(center=center)
            | Q(center__isnull=True, group__center=center)
            | Q(center__isnull=True, student__center=center)
        )
    student_enrollments = list(
        active_qs.filter(
            student=enr.student,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        ).order_by("group__category_obj__name", "group__nom", "id")
    )
    if all(item.id != enr.id for item in student_enrollments):
        student_enrollments.append(enr)

    enrollment_map = {item.id: item for item in student_enrollments}
    enrollment_by_group_id = {item.group_id: item for item in student_enrollments if item.group_id}
    enrollment_catalog = _student_enrollment_catalog(student_enrollments)

    all_groups = Group.objects.select_related("category_obj")
    if center:
        all_groups = all_groups.filter(center=center)

    next_url = request.POST.get("next") or request.GET.get("next") or reverse("education:qarzdorlar_home")
    month_str = (request.GET.get("month") or request.POST.get("month") or "").strip()
    start_month = parse_month_yyyy_mm(month_str) or first_day_of_current_month()
    lesson_pattern_options = _lesson_pattern_options()

    def _resolve_active_enrollment(candidate_id):
        return enrollment_map.get(candidate_id) or enr

    def _build_edit_context(active_enrollment, *, teacher_share_only_checked: bool):
        # preview_month: URL'dagi ?month= yoki joriy oy (enrollment boshlanish oyiga bog'liq emas)
        preview_month = start_month
        pricing_preview = tuition_month_preview(active_enrollment, preview_month)

        # Tugash sanasi: saqlangan last_lesson_date ni ko'rsatamiz.
        # Faqat joriy billing oyi yoki kelajakdagi sana bo'lsa ishlatamiz —
        # o'tgan oydagi eski noto'g'ri qiymatlar e'tiborga olinmaydi.
        _billing_month_start = month_first_day(pricing_preview["month"])
        _billing_month_end = month_last_day(pricing_preview["month"])
        _saved_end = getattr(active_enrollment, "last_lesson_date", None)
        if _saved_end and _saved_end >= _billing_month_start:
            pricing_preview = _apply_period_end_to_preview(pricing_preview, _saved_end)
            _period_end_date = _saved_end
        else:
            _period_end_date = _billing_month_end

        # Joriy oy to'langan/to'lanmagan holatini tekshiramiz
        _month_paid = int(get_month_paid(active_enrollment, preview_month) or 0)
        _fee = int(pricing_preview.get("fee_amount", 0) or 0)
        _remaining_debt = max(0, _fee - _month_paid)
        _month_label = pricing_preview.get("month_label_uz", "").upper()
        if _fee > 0 and _month_paid >= _fee:
            pricing_preview["debt_label_uz"] = f"{_month_label} OYI TO'LANGAN"
            pricing_preview["fee_amount"] = 0
            pricing_preview["fee_amount_display"] = format_money(0)
            pricing_preview["is_month_paid"] = True
        else:
            pricing_preview["debt_label_uz"] = f"{_month_label} OYI QARZI"
            pricing_preview["fee_amount"] = _remaining_debt
            pricing_preview["fee_amount_display"] = format_money(_remaining_debt)
            pricing_preview["is_month_paid"] = False

        group_options = [
            {
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "enrollment_id": row["enrollment_id"],
            }
            for row in enrollment_catalog.get("enrollments", [])
        ]
        remaining_lessons_value = (
            active_enrollment.remaining_lessons_override
            if active_enrollment.remaining_lessons_override is not None
            else int(pricing_preview["lesson_count"] or 0)
        )
        lesson_plan = calculate_lessons(
            start_date=pricing_preview["start_date"],
            remaining_lessons=remaining_lessons_value,
            pattern=pricing_preview["lesson_pattern"],
            from_date=timezone.localdate(),
            group=active_enrollment.group,
        )
        pricing_preview = _apply_lesson_count_breakdown(
            pricing_preview,
            active_enrollment,
            remaining_lessons_value,
        )
        # Faqat so'nggi 2 oy ko'rsatiladi: joriy oy + bitta oldingi oy.
        # Mart va undan avvalgi qarzlar UI'da yashiriladi (DB'da saqlanadi).
        if getattr(active_enrollment, "id", None):
            _cum_snapshots = calculate_enrollment_debt_snapshots(
                [active_enrollment],
                [preview_month],
                cumulative_up_to=preview_month,
            )
            _cum_snap = _cum_snapshots.get(active_enrollment.id, {})
            credit = int(_cum_snap.get("credit_balance", 0) or 0)

            # Faqat bir oldingi oy (aprel) qarzini ko'rsatamiz
            prev_month = _add_month(month_first_day(preview_month), -1)
            prev_tm = TuitionMonth.objects.filter(
                enrollment=active_enrollment,
                month=prev_month,
                is_deleted=False,
            ).first()
            if prev_tm:
                prev_fee = int(getattr(prev_tm, "fee_amount", 0) or 0)
                prev_paid = int(get_month_paid(active_enrollment, prev_month) or 0)
                previous_unpaid_1month = max(0, prev_fee - prev_paid)
            else:
                previous_unpaid_1month = 0

            current_fee = int(pricing_preview.get("fee_amount", 0) or 0)
            cumulative_2months = current_fee + previous_unpaid_1month
            pricing_preview["previous_unpaid"] = previous_unpaid_1month
            pricing_preview["cumulative_debt"] = cumulative_2months
            pricing_preview["credit_balance"] = credit
            pricing_preview["net_cumulative_debt"] = max(0, cumulative_2months - credit)
        else:
            pricing_preview["previous_unpaid"] = 0
            pricing_preview["cumulative_debt"] = int(pricing_preview.get("fee_amount", 0) or 0)
            pricing_preview["credit_balance"] = 0
            pricing_preview["net_cumulative_debt"] = int(pricing_preview.get("fee_amount", 0) or 0)
        return {
            "enr": active_enrollment,
            "groups": group_options,
            "selected_group_id": active_enrollment.group_id,
            "active_enrollment_id": active_enrollment.id,
            "active_enrollment_stored_pattern": getattr(
                active_enrollment,
                "lesson_pattern",
                Enrollment.LESSON_PATTERN_GROUP,
            ),
            "next": next_url,
            "month": month_str,
            "teacher_share_only_checked": teacher_share_only_checked,
            "pricing_preview": pricing_preview,
            "lesson_pattern_options": lesson_pattern_options,
            "selected_lesson_pattern": pricing_preview["lesson_pattern"],
            "remaining_lessons_value": remaining_lessons_value,
            "lesson_plan": lesson_plan,
            "period_end_date": _period_end_date,
            "course_price_display": format_money(active_enrollment.kurs_narhi),
            "enrollment_catalog": enrollment_catalog,
        }

    def _render_enrollment_edit_form(*, teacher_share_only_checked: bool, active_enrollment=None):
        return render(
            request,
            "education/enrollment_edit.html",
            _build_edit_context(
                active_enrollment or enr,
                teacher_share_only_checked=teacher_share_only_checked,
            ),
        )

    if (
        request.method == "GET"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
        and request.GET.get("preview") == "1"
    ):
        active_enrollment = _resolve_active_enrollment(
            _parse_int_value(request.GET.get("active_enrollment_id"), enr.id)
        )
        selected_group_id = _parse_int_value(request.GET.get("group_id"), active_enrollment.group_id)
        if selected_group_id and selected_group_id not in enrollment_by_group_id:
            return JsonResponse({"error": "Bu o'quvchi ushbu guruhga biriktirilmagan."}, status=400)
        selected_group = enrollment_by_group_id.get(selected_group_id, active_enrollment).group
        joined_at = (
            parse_date((request.GET.get("joined_at") or request.GET.get("start_date") or "").strip())
            or getattr(active_enrollment, "joined_at", None)
            or enrollment_start_date(active_enrollment)
        )
        lesson_pattern = request.GET.get("lesson_pattern") or getattr(active_enrollment, "lesson_pattern", None)
        course_price = int(
            _parse_int_value(
                request.GET.get("kurs_narhi"),
                getattr(active_enrollment, "kurs_narhi", 0) or 0,
            )
            or 0
        )
        teacher_percent = (
            int(getattr(selected_group, "oqituvchi_foiz", 0) or 0)
            if getattr(selected_group, "id", None) and selected_group.id != active_enrollment.group_id
            else int(
                _parse_int_value(
                    request.GET.get("oqituvchi_foiz"),
                    getattr(active_enrollment, "oqituvchi_foiz", 0) or 0,
                )
                or 0
            )
        )
        monthly_lessons = int(
            _parse_int_value(
                request.GET.get("monthly_lessons"),
                getattr(active_enrollment, "monthly_lessons", 0)
                or getattr(selected_group, "oy_dars_soni", 0)
                or 12,
            )
            or 12
        )
        teacher_share_only = _parse_bool_value(request.GET.get("teacher_share_only"))
        missing = object()
        payable_raw = request.GET.get("student_payable_amount", missing)
        if teacher_share_only:
            student_payable_amount = round(course_price * teacher_percent / 100)
        elif payable_raw is missing:
            student_payable_amount = getattr(active_enrollment, "student_payable_amount", None)
        elif payable_raw in (None, "", "None"):
            student_payable_amount = None
        else:
            student_payable_amount = _parse_int_value(
                payable_raw,
                getattr(active_enrollment, "student_payable_amount", None),
            )

        preview_enrollment = _build_tuition_preview_enrollment(
            base_enrollment=active_enrollment,
            group=selected_group,
            start_date=joined_at,
            lesson_pattern=lesson_pattern,
            monthly_lessons=monthly_lessons,
            course_price=course_price,
            teacher_percent=teacher_percent,
            student_payable_amount=student_payable_amount,
        )
        preview = tuition_month_preview(
            preview_enrollment,
            start_month,
        )
        period_end = _parse_period_end(
            request.GET.get("period_end_date") or request.GET.get("end_date"),
            preview["month"],
        )
        preview = _apply_period_end_to_preview(preview, period_end)
        remaining_raw = request.GET.get("remaining_lessons")
        if remaining_raw in (None, ""):
            remaining_lessons = (
                getattr(active_enrollment, "remaining_lessons_override", None)
                if getattr(active_enrollment, "remaining_lessons_override", None) is not None
                else int(preview["lesson_count"] or 0)
            )
        else:
            try:
                remaining_lessons = validate_remaining_lessons(remaining_raw)
            except ValidationError as exc:
                return JsonResponse({"error": exc.messages[0]}, status=400)

        lesson_plan = calculate_lessons(
            start_date=preview["start_date"],
            remaining_lessons=remaining_lessons,
            pattern=preview["lesson_pattern"],
            from_date=timezone.localdate(),
            group=selected_group,
        )
        preview = _apply_lesson_count_breakdown(preview, preview_enrollment, remaining_lessons)
        return JsonResponse(
            {
                "preview": _serialize_tuition_preview(preview),
                "lesson_plan": _serialize_lesson_plan(lesson_plan),
            }
        )

    if request.method == "POST":
        active_enrollment = _resolve_active_enrollment(
            _parse_int_value(request.POST.get("active_enrollment_id"), enr.id)
        )
        student_ism = request.POST.get("ism", "").strip()
        student_familya = request.POST.get("familya", "").strip()
        student_telefon1 = request.POST.get("telefon1", "").strip()

        gid = _parse_int_value(request.POST.get("group_id"))
        selected_group = active_enrollment.group
        old_group_id = active_enrollment.group_id
        if gid:
            target_enrollment = enrollment_by_group_id.get(gid)
            if target_enrollment:
                if target_enrollment.id != active_enrollment.id:
                    active_enrollment = target_enrollment
                    selected_group = active_enrollment.group
                    old_group_id = active_enrollment.group_id
            else:
                messages.error(request, "Bu o'quvchi ushbu guruhga biriktirilmagan.")
                return _render_enrollment_edit_form(
                    teacher_share_only_checked=_parse_bool_value(request.POST.get("teacher_share_only")),
                    active_enrollment=active_enrollment,
                )

        new_price = int(_parse_int_value(request.POST.get("kurs_narhi"), 0) or 0)
        active_enrollment.kurs_narhi = new_price

        oqf = _parse_int_value(request.POST.get("oqituvchi_foiz"), None)
        if getattr(selected_group, "id", None) and selected_group.id != old_group_id:
            active_enrollment.oqituvchi_foiz = int(getattr(selected_group, "oqituvchi_foiz", 0) or 0)
        elif oqf is not None:
            active_enrollment.oqituvchi_foiz = int(oqf)

        joined_at_raw = (request.POST.get("joined_at") or request.POST.get("start_date") or "").strip()
        if joined_at_raw and parse_date(joined_at_raw) is None:
            messages.error(request, "Boshlanish sanasi noto'g'ri kiritildi.")
            return _render_enrollment_edit_form(
                teacher_share_only_checked=_parse_bool_value(request.POST.get("teacher_share_only")),
                active_enrollment=active_enrollment,
            )
        joined_at = parse_date(joined_at_raw) if joined_at_raw else None
        schedule_meta = resolve_lesson_schedule(
            joined_at or active_enrollment.joined_at or timezone.localdate(),
            request.POST.get("lesson_pattern") or getattr(active_enrollment, "lesson_pattern", None),
        )
        active_enrollment.joined_at = schedule_meta["start_date"]
        active_enrollment._tuition_start_date = active_enrollment.joined_at
        active_enrollment.lesson_pattern = schedule_meta["lesson_pattern"]
        if schedule_meta["adjustment_note"]:
            messages.info(request, schedule_meta["adjustment_note"])
        # Guruh oy_dars_soni — yagona manba', stale enrollment qiymatini yangilash
        monthly_lessons_raw = (request.POST.get("monthly_lessons") or "").strip()
        try:
            active_enrollment.monthly_lessons = int(
                getattr(selected_group, "oy_dars_soni", 0)
                or monthly_lessons_raw
                or getattr(active_enrollment, "monthly_lessons", 0)
                or 12
            )
        except (TypeError, ValueError):
            active_enrollment.monthly_lessons = getattr(selected_group, "oy_dars_soni", 0) or 12
        active_enrollment.pricing_type = (
            Enrollment.PRICING_PRORATED
            if active_enrollment.joined_at and active_enrollment.joined_at.day > 1
            else Enrollment.PRICING_FULL
        )

        payable_raw = (request.POST.get("student_payable_amount") or "").replace(" ", "").replace(",", "").strip()
        teacher_share_only = _parse_bool_value(request.POST.get("teacher_share_only"))
        if teacher_share_only:
            active_enrollment.student_payable_amount = round(
                full_course_amount(active_enrollment) * (active_enrollment.oqituvchi_foiz or 0) / 100
            )
        elif payable_raw == "":
            active_enrollment.student_payable_amount = None
        else:
            try:
                active_enrollment.student_payable_amount = int(payable_raw)
            except (TypeError, ValueError):
                messages.error(request, "O'quvchidan olinadigan summa noto'g'ri kiritildi.")
                return _render_enrollment_edit_form(
                    teacher_share_only_checked=teacher_share_only,
                    active_enrollment=active_enrollment,
                )

        remaining_lessons_raw = (request.POST.get("remaining_lessons_override") or "").strip()
        if remaining_lessons_raw == "":
            active_enrollment.remaining_lessons_override = None
        else:
            try:
                active_enrollment.remaining_lessons_override = validate_remaining_lessons(remaining_lessons_raw)
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
                return _render_enrollment_edit_form(
                    teacher_share_only_checked=teacher_share_only,
                    active_enrollment=active_enrollment,
                )

        preview_enrollment = _build_tuition_preview_enrollment(
            base_enrollment=active_enrollment,
            group=selected_group,
            start_date=active_enrollment.joined_at,
            lesson_pattern=active_enrollment.lesson_pattern,
            monthly_lessons=active_enrollment.monthly_lessons,
            course_price=active_enrollment.kurs_narhi,
            teacher_percent=active_enrollment.oqituvchi_foiz,
            student_payable_amount=active_enrollment.student_payable_amount,
        )
        preview = tuition_month_preview(
            preview_enrollment,
            start_month,
        )
        period_end = _parse_period_end(
            request.POST.get("period_end_date") or request.POST.get("end_date"),
            preview["month"],
        )
        preview = _apply_period_end_to_preview(preview, period_end)
        billing_lesson_count = (
            active_enrollment.remaining_lessons_override
            if active_enrollment.remaining_lessons_override is not None
            else int(preview["lesson_count"] or 0)
        )
        billing_preview = _apply_lesson_count_breakdown(
            preview,
            preview_enrollment,
            billing_lesson_count,
        )
        lesson_plan = calculate_lessons(
            start_date=preview["start_date"],
            remaining_lessons=billing_lesson_count,
            pattern=preview["lesson_pattern"],
            from_date=timezone.localdate(),
            group=selected_group,
        )
        # period_end ni to'g'ridan-to'g'ri saqlaymiz (lesson_plan oxirgi sanasi emas,
        # chunki period_end kelajak oyda bo'lishi mumkin)
        active_enrollment.last_lesson_date = period_end

        try:
            active_enrollment.full_clean()
        except ValidationError as exc:
            error_messages = []
            for messages_list in exc.message_dict.values():
                error_messages.extend(messages_list)
            messages.error(request, " ".join(error_messages))
            return _render_enrollment_edit_form(
                teacher_share_only_checked=teacher_share_only,
                active_enrollment=active_enrollment,
            )

        active_enrollment.student.ism = student_ism
        active_enrollment.student.familya = student_familya
        active_enrollment.student.telefon1 = student_telefon1
        active_enrollment.student.save(update_fields=["ism", "familya", "telefon1"])

        active_enrollment.save()

        open_history = StudentGroupHistory.objects.filter(
            student=active_enrollment.student,
            group=active_enrollment.group,
            end_date__isnull=True,
        ).order_by("-start_date").first()
        if open_history:
            open_history.start_date = active_enrollment.joined_at
            open_history.kurs_narxi = active_enrollment.kurs_narhi
            open_history.oqituvchi_foiz = active_enrollment.oqituvchi_foiz
            open_history.save(update_fields=["start_date", "kurs_narxi", "oqituvchi_foiz"])
        else:
            StudentGroupHistory.objects.create(
                student=active_enrollment.student,
                group=active_enrollment.group,
                center=active_enrollment.center,
                start_date=active_enrollment.joined_at,
                kurs_narxi=active_enrollment.kurs_narhi,
                oqituvchi_foiz=active_enrollment.oqituvchi_foiz,
            )

        sync_tuition_fee(
            enrollment=active_enrollment,
            new_fee=effective_student_payable_amount(active_enrollment),
            start_month=month_first_day(active_enrollment.joined_at or start_month),
        )
        billing_month = month_first_day(active_enrollment.joined_at or start_month)
        fee_field = tuition_month_fee_field()
        # TuitionMonth fee: o'quvchidan real olinadigan summa (student_payable_amount hisobga olinadi).
        # billing_preview["fee_amount"] full_course_amount asosida — individual chegirma bo'lsa
        # effective narx bilan qayta hisoblaymiz.
        _eff_price = int(effective_student_payable_amount(active_enrollment) or 0)
        _full_price = int(full_course_amount(active_enrollment) or 0)
        if _eff_price != _full_price:
            _ml = int(
                getattr(active_enrollment, "monthly_lessons", 0)
                or getattr(selected_group, "oy_dars_soni", 0)
                or 12
            )
            _eff_bd = tuition_amount_breakdown(
                active_enrollment,
                billing_lesson_count,
                course_price=_eff_price,
                monthly_lessons=_ml,
                teacher_percent=int(getattr(active_enrollment, "oqituvchi_foiz", 0) or 0),
            )
            _tuition_fee = int(_eff_bd["fee_amount"])
        else:
            _tuition_fee = int(billing_preview["fee_amount"] or 0)
        tuition_month, _ = TuitionMonth.all_objects.update_or_create(
            enrollment=active_enrollment,
            month=billing_month,
            defaults={
                "center": active_enrollment.center,
                fee_field: _tuition_fee,
            },
        )
        if tuition_month.is_deleted:
            tuition_month.restore()

        messages.success(request, "O'quvchi ma'lumotlari muvaffaqiyatli yangilandi!")
        if get_student_total_debt(active_enrollment.student, center) <= 0:
            next_url = reverse("education:tolovlar_home")
        return redirect(next_url)

    return _render_enrollment_edit_form(
        teacher_share_only_checked=_is_teacher_share_only_enrollment(enr),
        active_enrollment=_resolve_active_enrollment(
            _parse_int_value(request.GET.get("active_enrollment_id"), enr.id)
        ),
    )



@login_required
@require_http_methods(["GET", "POST"])
def enrollment_delete(request, enrollment_id: int):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("core:home")

    # from core.tenant import get_request_center
    center = get_active_center(request)
    qs = Enrollment.all_objects.select_related("student", "group")
    if center:
        qs = qs.filter(
            Q(center=center)
            | Q(center__isnull=True, group__center=center)
            | Q(center__isnull=True, student__center=center)
        )

    enr = get_object_or_404(qs, id=enrollment_id)
    next_url = request.GET.get("next") or request.POST.get("next") or "education:tolovlar_home"

    if request.method == "POST":
        student_name = f"{enr.student.ism} {enr.student.familya}"
        group_name = getattr(enr.group, "nom", "")
        keep_in_group = request.POST.get("keep_in_group") == "1"
        # Oy parametri: berilsa, faqat o'sha oyga ta'sir qiladi (aprelni
        # tozalasangiz may tegmaydi). Berilmasa — barcha oylar (eski xulq).
        month_str = (request.POST.get("month") or "").strip()
        target_month = parse_month_str(month_str) if month_str else None

        if keep_in_group:
            with transaction.atomic():
                # all_objects — is_deleted=True bo'lganlarni ham ko'rsatadi,
                # agar avval o'chirilgan bo'lsa, ustiga qayta o'chirish xavfsiz.
                tm_qs = TuitionMonth.all_objects.filter(enrollment=enr)
                if target_month is not None:
                    tm_qs = tm_qs.filter(month=target_month)

                # Faqat hali o'chirilmagan recordlar
                alive_tm_ids = list(
                    tm_qs.filter(is_deleted=False).values_list("id", flat=True)
                )

                # Virtual TuitionMonth case: DBda yozuv yo'q bo'lsa ham o'quvchi
                # qarzdor ko'rinadi. Shu holda sentinel yozuv yaratib o'chiramiz —
                # calculate_enrollment_debt_snapshots bundan keyin fee=0 deb oladi.
                # deleted_reason="manual_cleared" ensure_tuition_month'ni qayta
                # tiklamasligiga ishora beradi.
                if target_month is not None and not tm_qs.exists():
                    from education.services.tuition import prorated_monthly_fee, tuition_month_fee_field
                    fee_field_name = tuition_month_fee_field()
                    fee_val = int(prorated_monthly_fee(enr, target_month) or 0)
                    sentinel_tm = TuitionMonth(
                        enrollment=enr,
                        month=target_month,
                        center=getattr(enr, "center", None),
                        is_deleted=True,
                        deleted_at=timezone.now(),
                        deleted_by=request.user,
                        deleted_reason="manual_cleared",
                    )
                    setattr(sentinel_tm, fee_field_name, fee_val)
                    sentinel_tm.save()

                # 1) Shu oy(lar)ga tegishli PaymentAllocation'larni soft-delete.
                if alive_tm_ids:
                    PaymentAllocation.objects.filter(
                        tuition_month_id__in=alive_tm_ids,
                        is_deleted=False,
                    ).update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)

                # 2) Qaysi Payment'lar hech qanday aktiv allocation'siz qoldi —
                #    ularni o'chirmay, summa=0 qilib saqlaymiz. Shunday qilsak
                #    o'quvchi to'lovlar bo'limida "0 so'm" to'lagan deb ko'rinadi
                #    va yo'qolib ketmaydi.
                payments_to_zero = Payment.objects.filter(
                    enrollment=enr, is_deleted=False
                )
                _today = timezone.localdate().isoformat()
                for p in payments_to_zero:
                    has_active_allocations = p.allocations.filter(is_deleted=False).exists()
                    if not has_active_allocations:
                        _note = (p.note or "").strip()
                        p.summa = 0
                        p.cash_amount = 0
                        p.card_amount = 0
                        p.note = (_note + f" [To'lov tozalandi: {_today}]").strip()
                        p.save(update_fields=["summa", "cash_amount", "card_amount", "note"])

                # 3) Alive TuitionMonth'larni soft-delete.
                # deleted_reason="manual_cleared" ensure_tuition_month'ni qayta
                # tiklamasligiga ishora beradi.
                if alive_tm_ids:
                    TuitionMonth.objects.filter(id__in=alive_tm_ids).update(
                        is_deleted=True,
                        deleted_at=timezone.now(),
                        deleted_by=request.user,
                        deleted_reason="manual_cleared",
                    )

            if target_month is not None:
                messages.success(
                    request,
                    f"{target_month:%Y-%m} oyi uchun to'lov yozuvlari o'chirildi. "
                    f"{student_name} ({group_name}) guruhda qoldi.",
                )
            else:
                messages.success(
                    request,
                    f"To'lov yozuvlari (barcha oylar) o'chirildi. "
                    f"{student_name} ({group_name}) guruhda qoldi.",
                )
        else:
            with transaction.atomic():
                TuitionMonth.objects.filter(
                    enrollment=enr, is_deleted=False
                ).update(
                    is_deleted=True,
                    deleted_at=timezone.now(),
                    deleted_by=request.user,
                    deleted_reason="manual_cleared",
                )
                PaymentAllocation.objects.filter(
                    tuition_month__enrollment=enr, is_deleted=False
                ).update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)
                enr.delete(deleted_by=request.user)
            messages.success(request, f"🗑️ {student_name} ({group_name}) guruhdan o'chirildi.")
        return redirect(next_url)

    return render(request, "education/enrollment_delete_confirm.html", {"enr": enr, "next": next_url})



@login_required
def student_detail(request, student_id: int):
    from core.tenant import get_tenant_object_or_404

    # Faqat active center o'quvchisi — boshqa markaz IDOR dan himoyalangan.
    student = get_tenant_object_or_404(User, request, pk=student_id, role="student")
    center = get_active_center(request)
    selected_month = parse_month_str((request.GET.get("month") or "").strip()) or month_first_day(timezone.localdate())
    can_view_student_group_financials = request.user.is_superuser or getattr(request.user, "role", None) in ("director", "manager")
    can_manage_parent_link = can_view_student_group_financials

    from accounts.services.parent_telegram_link import parent_link_status as build_parent_link_status

    raw_parent_link_status = build_parent_link_status(student)
    parent_linked_at = raw_parent_link_status.get("linked_at")
    parent_link_status = {
        "is_linked": raw_parent_link_status["is_linked"],
        "telegram_id": raw_parent_link_status["telegram_id"],
        "telegram_username": raw_parent_link_status["telegram_username"],
        "linked_at_display": timezone.localtime(parent_linked_at).strftime("%d.%m.%Y %H:%M") if parent_linked_at else "",
        "parent_id": raw_parent_link_status["parent_id"],
        "parent_name": raw_parent_link_status["parent_name"],
    }

    MONTH_NAMES = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May",
        6: "Iyun", 7: "Iyul", 8: "Avgust", 9: "Sentabr", 10: "Oktyabr",
        11: "Noyabr", 12: "Dekabr"
    }

    # 🔹 Endi davomatni guruhga qarab ajratamiz
    attendances = Attendance.objects.filter(student=student).select_related("group").annotate(
        year=ExtractYear('date'),
        month=ExtractMonth('date')
    ).order_by('-date')

    daily_records = DailyLightningRecord.objects.filter(student=student)
    daily_month_lightning_map = {
        (row["group_id"], row["year"], row["month"]): {
            "plus": int(row["plus_total"] or 0),
            "minus": abs(int(row["minus_total"] or 0)),
        }
        for row in (
            daily_records.annotate(
                year=ExtractYear("date"),
                month=ExtractMonth("date"),
            ).values("group_id", "year", "month").annotate(
                plus_total=Coalesce(Sum("plus_points"), 0),
                minus_total=Coalesce(Sum("minus_points"), 0),
            )
        )
    }
    daily_day_lightning_map = {
        (row["group_id"], row["date"]): {
            "plus": int(row["plus_total"] or 0),
            "minus": abs(int(row["minus_total"] or 0)),
        }
        for row in (
            daily_records.values("group_id", "date").annotate(
                plus_total=Coalesce(Sum("plus_points"), 0),
                minus_total=Coalesce(Sum("minus_points"), 0),
            )
        )
    }

    # DailyLightningRecord mavjud bo'lmagan yozuvlar uchun Ledger fallback.
    ledger_month_lightning_map = {}
    ledger_day_lightning_map = {}
    ledger_rows = (
        Ledger.objects
        .filter(student=student)
        .exclude(group_id__isnull=True)
        .values("group_id", "sana", "ball")
    )
    for row in ledger_rows:
        dt = row.get("sana")
        if not dt:
            continue

        local_dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
        ledger_date = local_dt.date()
        group_id = row["group_id"]
        ball = int(row.get("ball") or 0)

        month_key = (group_id, ledger_date.year, ledger_date.month)
        day_key = (group_id, ledger_date)

        if month_key not in ledger_month_lightning_map:
            ledger_month_lightning_map[month_key] = {"plus": 0, "minus": 0}
        if day_key not in ledger_day_lightning_map:
            ledger_day_lightning_map[day_key] = {"plus": 0, "minus": 0}

        if ball > 0:
            ledger_month_lightning_map[month_key]["plus"] += ball
            ledger_day_lightning_map[day_key]["plus"] += ball
        elif ball < 0:
            minus_abs = abs(ball)
            ledger_month_lightning_map[month_key]["minus"] += minus_abs
            ledger_day_lightning_map[day_key]["minus"] += minus_abs

    # Asosiy manba DailyLightningRecord; unda bo'lmagan kalitlar Ledger'dan olinadi.
    month_lightning_map = dict(ledger_month_lightning_map)
    month_lightning_map.update(daily_month_lightning_map)

    day_lightning_map = dict(ledger_day_lightning_map)
    day_lightning_map.update(daily_day_lightning_map)

    # 🔹 Har bir guruh bo'yicha ajratamiz
    grouped_by_group = {}
    for a in attendances:
        grouped_by_group.setdefault(a.group, []).append(a)

    month_summaries = []
    for group, group_attendances in grouped_by_group.items():
        # Guruh bo'yicha oylik natijalarni tayyorlash
        grouped_by_month = {}
        for a in group_attendances:
            key = (a.year, a.month)
            grouped_by_month.setdefault(key, []).append(a)

        for (year, month), records in grouped_by_month.items():
            total_present = sum(1 for r in records if r.present)
            month_lightning = month_lightning_map.get((group.id, year, month), {"plus": 0, "minus": 0})
            plus_sum = month_lightning["plus"]
            minus_sum = month_lightning["minus"]

            month_summaries.append({
                "group": group.nom,  # 🔹 Guruh nomini qo'shamiz
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES.get(month, "Noma'lum oy"),
                "present_days": total_present,
                "plus": plus_sum,
                "minus": minus_sum,
                "days": [
                    {
                        "date": r.date,
                        "present": r.present,
                        "plus": day_lightning_map.get((group.id, r.date), {}).get("plus", 0),
                        "minus": day_lightning_map.get((group.id, r.date), {}).get("minus", 0),
                    }
                    for r in records
                ]
            })

    ctx = {
        "student": student,
        "month_summaries": month_summaries,
        "selected_month": selected_month,
        "can_view_student_group_financials": can_view_student_group_financials,
        "can_manage_parent_link": can_manage_parent_link,
        "parent_link_status": parent_link_status,
        "can_transfer_student": user_can_transfer_student(request.user),
        "student_group_financials": (
            _student_group_financial_cards(
                student,
                center=center,
                month=selected_month,
                include_dates=True,
            )
            if can_view_student_group_financials
            else None
        ),
    }

    return render(request, "education/student_detail.html", ctx)



@login_required
@require_http_methods(["GET", "POST"])
def transfer_student_view(request, enrollment_id: int):
    from core.tenant import get_request_center

    center = get_request_center(request)
    enrollment_qs = Enrollment.objects.select_related("student", "group", "center").filter(is_active=True)
    if center:
        enrollment_qs = enrollment_qs.filter(center=center, group__center=center, student__center=center)
    enrollment = get_object_or_404(enrollment_qs, pk=enrollment_id)

    if not user_can_transfer_student(request.user):
        messages.error(request, "Sizda o'quvchini boshqa guruhga ko'chirish huquqi yo'q.")
        return redirect("education:group_detail", pk=enrollment.group_id)

    if request.method == "POST":
        form = StudentGroupTransferForm(request.POST, old_group=enrollment.group, center=center or enrollment.center)
        if form.is_valid():
            try:
                result = transfer_student_to_group(
                    student=enrollment.student,
                    old_group=enrollment.group,
                    new_group=form.cleaned_data["new_group"],
                    transfer_date=form.cleaned_data["transfer_date"],
                    reason=form.cleaned_data["reason"],
                    user=request.user,
                )
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            except Exception:
                logger.exception("Student group transfer failed")
                messages.error(request, "Ko'chirish vaqtida xatolik yuz berdi. Eski holat saqlandi.")
            else:
                messages.success(
                    request,
                    f"{enrollment.student.get_full_name()} yangi guruhga ko'chirildi. To'lov qayta hisoblandi.",
                )
                return redirect("education:group_detail", pk=result["new_enrollment"].group_id)
        else:
            messages.error(request, "Ma'lumotlarni tekshiring: yangi guruhni tanlang va sanani to'g'ri kiriting.")
    else:
        form = StudentGroupTransferForm(
            initial={"transfer_date": timezone.localdate()},
            old_group=enrollment.group,
            center=center or enrollment.center,
        )

    return render(request, "education/student_transfer_form.html", {
        "form": form,
        "enrollment": enrollment,
        "student": enrollment.student,
        "old_group": enrollment.group,
    })



@login_required
@transaction.atomic
def add_student_to_group(request, pk: int):
    from core.tenant import get_request_center
    center = get_request_center(request)
    
    # Guruhni olish
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # Ruxsat tekshirish
    can_add = False
    if request.user.role == "director" or request.user.is_superuser:
        can_add = True
    elif center:
        if request.user.role == "manager":
            can_add = center.manager_can_add_student
        elif request.user.role == "teacher":
            can_add = center.teacher_can_add_student

    if not can_add:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "Sizda ruxsat yo'q"}, status=403)
        return HttpResponseForbidden("❌ Sizda bu amalni bajarish uchun ruxsat yo'q.")

    # Markazni aniqlash (Guruh markazi asosiy hisoblanadi)
    target_center = g.center
    # AJAX Search
    if request.method == "GET" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        query = request.GET.get("q", "").strip()
        student_qs = User.objects.filter(role="student", center=target_center)
        
        if query:
            # Ism, familya yoki telefon bo'yicha qidirish
            student_qs = student_qs.filter(
                Q(ism__icontains=query) | 
                Q(familya__icontains=query) | 
                Q(telefon1__icontains=query) |
                Q(telefon2__icontains=query)
            ).distinct()
            limit = 15
        else:
            # Bo'sh bo'lsa barcha o'quvchilar (yoki dastlabki 30 tasi)
            limit = 30
            
        results = []
        for s in student_qs.order_by('ism', 'familya')[:limit]:
            # Status aniqlash (Faqat shu markaz doirasida)
            is_in_current = Enrollment.objects.filter(group=g, student=s).exists()
            is_in_other = Enrollment.objects.filter(student=s, center=target_center).exclude(group=g).exists()
            
            results.append({
                "id": s.id,
                "full_name": s.get_full_name(),
                "phone": s.telefon1 or s.telefon2 or "Telefon kiritilmagan",
                "is_in_current": is_in_current,
                "is_in_other": is_in_other,
            })
        
        return JsonResponse({"results": results})

    # AJAX POST (Add student)
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        import json
        try:
            data = json.loads(request.body)
            student_id = data.get("student_id")
            start_date_raw = data.get("start_date")
            lesson_pattern_raw = data.get("lesson_pattern")
        except:
            student_id = request.POST.get("student_id")
            start_date_raw = request.POST.get("start_date")
            lesson_pattern_raw = request.POST.get("lesson_pattern")

        if not student_id:
            return JsonResponse({"error": "O'quvchi tanlanmagan"}, status=400)

        schedule_meta = resolve_lesson_schedule(
            parse_date(start_date_raw or "") or timezone.localdate(),
            lesson_pattern_raw,
        )
        start_date = schedule_meta["start_date"]
        lesson_pattern = schedule_meta["lesson_pattern"]

        student = get_object_or_404(User, pk=student_id, role="student", center=target_center)

        # Allaqachon guruhda bormi?
        if Enrollment.objects.filter(group=g, student=student).exists():
            return JsonResponse({
                "status": "warning",
                "message": f"'{student.get_full_name()}' allaqachon '{g.nom}' guruhida bor."
            })

        # Guruhga biriktirilgan narxni doimo ishlatamiz
        kurs_narhi = g.kurs_narxi

        # Qo'shish (EnrollmentService orqali tarix bilan)
        from education.services.enrollment_service import EnrollmentService
        enr = EnrollmentService.enroll_student(
            student=student,
            group=g,
            kurs_narxi=kurs_narhi,
            oqituvchi_foiz=g.oqituvchi_foiz or 40,
            start_date=start_date,
            lesson_pattern=lesson_pattern,
            monthly_lessons=getattr(g, "oy_dars_soni", 0) or 12,
        )

        from education.services.tuition import ensure_tuition_month
        preview_month = _preview_month_for_start_date(start_date)
        # ✅ Yangi qo'shilgan o'quvchi uchun boshlanish oyidagi snapshot to'g'ri prorata bilan yaratiladi.
        ensure_tuition_month(enr, preview_month)
        preview = tuition_month_preview(enr, preview_month)

        return JsonResponse({
            "status": "success",
            "message": f"'{student.get_full_name()}' muvaffaqiyatli qo'shildi ✅",
            "preview": _serialize_tuition_preview(preview),
            "student": {
                "id": student.id,
                "full_name": student.get_full_name(),
                "phone": student.telefon1 or student.telefon2
            },
            "info": schedule_meta["adjustment_note"],
        })

    # Standart GET render
    return render(request, "education/add_student_to_group.html", {
        "group": g,
    })



# ---------- A'zolik va o'qituvchi sahifasi ----------
@login_required
def enrollment_remove(request, pk):
    qs = Enrollment.objects.select_related("group", "student")
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        # Enrollment has center now, or filter by group__center
        qs = qs.filter(group__center=center)
    enr = get_object_or_404(qs, pk=pk)
    
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo'q.")
        return redirect("education:group_detail", pk=enr.group_id)
        
    if request.method == "POST":
        # ✅ EnrollmentService orqali o'chiramiz (tarix yopiladi)
        from education.services.enrollment_service import EnrollmentService
        EnrollmentService.remove_student(enr.student, enr.group)
        messages.success(request, "O'quvchi guruhdan chiqarildi. Tarix saqlanib qoldi.")
        
    return redirect("education:group_detail", pk=enr.group_id)



@require_POST
@login_required
def enrollment_toggle_deferred(request, pk):
    if not _can_manage(request.user):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "Ruxsat yo'q."}, status=403)
        messages.error(request, "Ruxsat yo'q.")
        return redirect("education:qarzdorlar_home")
    center = get_active_center(request)
    qs = Enrollment.objects.all()
    if center:
        qs = qs.filter(center=center)
    enr = get_object_or_404(qs, pk=pk)
    enr.is_deferred = not enr.is_deferred
    enr.save(update_fields=["is_deferred"])
    status_label = "kechiktirildi" if enr.is_deferred else "oddiy holatga qaytarildi"
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "is_deferred": enr.is_deferred,
            "message": f"{enr.student.get_full_name()} to'lovi {status_label}.",
        })
    next_url = request.POST.get("next") or reverse("education:qarzdorlar_home")
    messages.success(request, f"✅ {enr.student.get_full_name()} to'lovi {status_label}.")
    return redirect(next_url)



@login_required
def enrollment_leave(request, pk):
    """
    O'quvchini oyning o'rtasida guruhdan chiqarish — prorata to'lov bilan.
    """
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Enrollment.objects.select_related("group", "student", "group__oqituvchi")
    if center:
        qs = qs.filter(group__center=center)
    enr = get_object_or_404(qs, pk=pk)

    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo'q.")
        return redirect("education:group_detail", pk=enr.group_id)

    today = timezone.localdate()
    cur_month = today.replace(day=1)

    from education.services.tuition import (
        ensure_tuition_month, get_month_paid, get_effective_month_fee, month_last_day
    )
    tm = ensure_tuition_month(enr, cur_month)
    full_fee = enr.kurs_narhi or 0
    paid_so_far = get_month_paid(enr, cur_month)

    # Attendance-based prorata
    from education.models import Attendance
    group_sessions = Attendance.objects.filter(
        enrollment__group=enr.group,
        date__year=cur_month.year,
        date__month=cur_month.month,
    ).values_list("date", flat=True).distinct()
    total_lessons = group_sessions.count()

    student_attended = Attendance.objects.filter(
        enrollment=enr,
        date__year=cur_month.year,
        date__month=cur_month.month,
        is_present=True,
    ).count()

    if total_lessons > 0:
        prorated_fee = round(full_fee * student_attended / total_lessons)
    else:
        prorated_fee = 0

    remaining = max(0, prorated_fee - paid_so_far)
    oqituvchi_foiz = enr.oqituvchi_foiz or 0

    if request.method == "POST":
        amount_raw = request.POST.get("amount", "0").replace(" ", "").replace(",", "")
        try:
            amount = int(amount_raw)
        except (ValueError, TypeError):
            amount = 0

        if amount > 0:
            tm.fee_amount = prorated_fee
            tm.save(update_fields=["fee_amount"])
            from education.services.tuition import create_payment_and_allocate
            create_payment_and_allocate(
                enrollment=enr,
                amount=amount,
                paid_date=today,
                start_month=cur_month,
                payment_type="cash",
            )

        from education.services.enrollment_service import EnrollmentService
        EnrollmentService.remove_student(enr.student, enr.group)
        messages.success(request, f"✅ {enr.student.get_full_name()} guruhdan chiqarildi.")
        return redirect("education:group_detail", pk=enr.group_id)

    context = {
        "enr": enr,
        "full_fee": full_fee,
        "paid_so_far": paid_so_far,
        "prorated_fee": prorated_fee,
        "remaining": remaining,
        "total_lessons": total_lessons,
        "student_attended": student_attended,
        "oqituvchi_foiz": oqituvchi_foiz,
        "teacher_share": round(prorated_fee * oqituvchi_foiz / 100),
        "center_share": round(prorated_fee * (100 - oqituvchi_foiz) / 100),
        "cur_month": cur_month,
    }
    return render(request, "education/enrollment_leave.html", context)

