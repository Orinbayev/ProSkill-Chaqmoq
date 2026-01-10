# education/views.py
from datetime import datetime
from tokenize import group
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum,  F
from .models import  Group,  User
from django.utils.dateparse import parse_date
from django.utils.timezone import localdate, make_aware
from django.db.models.functions import ExtractMonth, ExtractYear
from datetime import date
from django.db.models import  Count, Q
from django.utils.timezone import localdate
from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib import messages

from education.models import Group, Attendance, Payment, Enrollment
from accounts.models import User


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils.timezone import localdate
from datetime import date
from accounts.models import User
from education.models import Group, Enrollment, Payment, Attendance
from django.db.models import Count, Prefetch, Sum
from django.core.cache import cache
from django.db.models.functions import ExtractMonth


from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
import json

from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate, timedelta

from accounts.models import User
from .forms import GroupForm, ITGroupForm, LangGroupForm
from .models import Group, Enrollment, Attendance, Payment 
from chaqmoq.models import Ledger, Rule
from django.db.models.functions import Abs, Coalesce
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

U = get_user_model()

DAILY_LIMIT = 50  # har bir o‘qituvchi → har bir o‘quvchi uchun, bugungi kun limiti





# ---------- Ruxsat helperlari ----------
def _can_manage(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _can_give_points(user, g: Group):
    return (
        user.is_superuser
        or user.role in ("director", "manager")
        or (user.role == "teacher" and g.oqituvchi_id == user.id)
    )

def _teacher_can(user, g: Group) -> bool:
    return user.is_superuser or user.role in ("director", "manager") or (
        user.role == "teacher" and g.oqituvchi_id == user.id
    )


from chaqmoq.models import Ledger

from datetime import datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from chaqmoq.models import Ledger

from education.services.tuition import month_first_day, ensure_tuition_month, get_month_paid, create_payment_and_allocate


def parse_month_str(month_str: str) -> date:
    # "2026-01" -> 2026-01-01
    if not month_str:
        return month_first_day(timezone.localdate())
    try:
        y, m = month_str.split("-")
        return date(int(y), int(m), 1)
    except Exception:
        return month_first_day(timezone.localdate())


def user_can_manage_payments(user) -> bool:
    # sizda role bor: manager/director
    return user.is_superuser or getattr(user, "role", None) in ("manager", "director")




from django.core.paginator import Paginator


from .models import Enrollment, Payment
from .permissions import user_can_manage_payments


@login_required
def tolov_oquvchilar(request):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo‘q.")
        return redirect("core:home")

    # =========================
    # GET params
    # =========================
    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()   # full | partial | unpaid | ""
    month_str = (request.GET.get("month") or "").strip()        # YYYY-MM
    per_page_raw = (request.GET.get("per_page") or "10").strip()

    # per_page (faqat ruxsat etilgan)
    allowed_per_page = {"10", "20", "50", "100"}
    if per_page_raw not in allowed_per_page:
        per_page_raw = "10"
    per_page = int(per_page_raw)

    # month default = joriy oy (1-kun)
    selected_month = parse_month_str(month_str)
    if not selected_month:
        today = timezone.localdate()
        selected_month = today.replace(day=1)

    # Template JS ishlatadi: YYYY-MM
    month_str_out = selected_month.strftime("%Y-%m")

    # =========================
    # Base queryset
    # =========================
    enrollments = Enrollment.objects.select_related("student", "group")

    if q:
        enrollments = enrollments.filter(
            Q(student__ism__icontains=q) |
            Q(student__familya__icontains=q) |
            Q(student__email__icontains=q)
        )

    # =========================
    # All-time stats (butun davr) — tez ishlashi uchun aggregate
    # =========================
    all_students_total = enrollments.count()

    paid_students_qs = (
        Payment.objects
        .filter(enrollment__in=enrollments)
        .values("enrollment_id")
        .distinct()
    )
    all_paid_students = paid_students_qs.count()
    all_never_paid_students = max(0, all_students_total - all_paid_students)

    all_paid_total = (
        Payment.objects
        .filter(enrollment__in=enrollments)
        .aggregate(s=Sum("summa"))["s"] or 0
    )
    all_payments_count = (
        Payment.objects
        .filter(enrollment__in=enrollments)
        .count()
    )

    # jami_tolangan ni N+1 qilmaslik uchun dict qilib olamiz
    sums_map = {
        x["enrollment_id"]: (x["s"] or 0)
        for x in (
            Payment.objects
            .filter(enrollment__in=enrollments)
            .values("enrollment_id")
            .annotate(s=Sum("summa"))
        )
    }

    # =========================
    # Build rows (hammasi) — pill counterlar shu yerga bog‘liq
    # =========================
    rows = []
    month_fee_total = 0
    month_paid_total = 0
    month_left_total = 0

    for e in enrollments:
        tm = ensure_tuition_month(e, selected_month)

        # fee 0 bo‘lib qolmasin (fallback)
        if not tm.fee_amount or tm.fee_amount == 0:
            fallback = (
                (getattr(e, "kurs_narhi", 0) or 0) or
                (getattr(e.group, "kurs_narxi", 0) or 0)
            )
            if fallback and fallback > 0:
                tm.fee_amount = fallback
                tm.save(update_fields=["fee_amount"])

        fee = tm.fee_amount or 0
        fee_missing = fee <= 0

        paid_this_month = get_month_paid(tm) or 0
        qoldiq = 0 if fee_missing else max(0, fee - paid_this_month)

        if fee_missing:
            status = "unpaid"
        elif paid_this_month >= fee:
            status = "full"
        elif paid_this_month > 0:
            status = "partial"
        else:
            status = "unpaid"

        jami_tolangan = sums_map.get(e.id, 0)

        # Stats (tanlangan oy)
        month_fee_total += int(fee or 0)
        month_paid_total += int(paid_this_month or 0)
        month_left_total += int(qoldiq or 0)

        rows.append({
            "enrollment": e,
            "student": e.student,
            "group": e.group,
            "month": selected_month,
            "fee": fee,
            "paid_this_month": paid_this_month,
            "qoldiq": qoldiq,
            "status": status,
            "jami_tolangan": jami_tolangan,
            "fee_missing": fee_missing,
        })

    # =========================
    # Counters (status filterdan oldin)
    # =========================
    total = len(rows)
    full_count = sum(1 for x in rows if x["status"] == "full")
    partial_count = sum(1 for x in rows if x["status"] == "partial")
    unpaid_count = sum(1 for x in rows if x["status"] == "unpaid")

    # =========================
    # Status filter (ekranga chiqadigan data)
    # =========================
    if status_filter in ("full", "partial", "unpaid"):
        data_rows = [x for x in rows if x["status"] == status_filter]
    else:
        status_filter = ""
        data_rows = rows

    # =========================
    # Pagination
    # =========================
    paginator = Paginator(data_rows, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "education/tolov_oquvchilar.html", {
        # list
        "data": page_obj.object_list,

        # filters
        "query": q,
        "selected_month": selected_month,
        "month_str": month_str_out,
        "status_filter": status_filter,

        # pills count
        "total": total,
        "full_count": full_count,
        "partial_count": partial_count,
        "unpaid_count": unpaid_count,

        # pagination
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": paginator.num_pages > 1,
        "per_page": per_page_raw,

        # stats: selected month
        "month_fee_total": month_fee_total,
        "month_paid_total": month_paid_total,
        "month_left_total": month_left_total,

        # stats: all time
        "all_students_total": all_students_total,
        "all_paid_students": all_paid_students,
        "all_never_paid_students": all_never_paid_students,
        "all_paid_total": all_paid_total,
        "all_payments_count": all_payments_count,
    })



@login_required
def create_payment(request):
    if request.method != "POST":
        return redirect("education:tolov_oquvchilar")

    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo‘q.")
        return redirect("education:tolov_oquvchilar")

    enrollment_id = request.POST.get("enrollment_id")
    next_url = request.POST.get("next") or "education:tolov_oquvchilar"

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    cash_amount = request.POST.get("cash_amount") or 0
    card_amount = request.POST.get("card_amount") or 0

    try:
        payment = create_payment_and_allocate(
            enrollment=enrollment,
            created_by=request.user,
            cash_amount=int(cash_amount or 0),
            card_amount=int(card_amount or 0),
        )
        messages.success(request, "✅ To‘lov saqlandi va oylar bo‘yicha taqsimlandi!")
    except Exception as e:
        messages.error(request, f"❌ Xatolik: {e}")

    return redirect(next_url)


@login_required
def payment_history_enrollment(request, enrollment_id: int):
    if not user_can_manage_payments(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)

    month_str = request.GET.get("month", "")
    selected_month = parse_month_str(month_str)

    enrollment = get_object_or_404(Enrollment.objects.select_related("student", "group"), id=enrollment_id)
    tm = ensure_tuition_month(enrollment, selected_month)

    fee = tm.fee_amount
    paid_this_month = get_month_paid(tm)
    qoldiq = max(0, fee - paid_this_month)

    # payments
    payments_qs = Payment.objects.filter(enrollment=enrollment).order_by("-id")

    payments = []
    for p in payments_qs:
        allocations = []
        for a in p.allocations.select_related("tuition_month").all():
            allocations.append({
                "month": a.tuition_month.month.strftime("%Y-%m"),
                "amount": a.amount,
            })

        paid_at = None
        if hasattr(p, "paid_at") and p.paid_at:
            paid_at = p.paid_at
        elif hasattr(p, "sana") and p.sana:
            # sana/vaqt bo‘lsa:
            if hasattr(p, "vaqt") and p.vaqt:
                paid_at = timezone.make_aware(timezone.datetime.combine(p.sana, p.vaqt))
            else:
                paid_at = timezone.make_aware(timezone.datetime.combine(p.sana, timezone.datetime.min.time()))
        else:
            paid_at = timezone.now()

        payments.append({
            "id": p.id,
            "paid_at": paid_at.strftime("%d.%m.%Y %H:%M"),
            "cash": int(getattr(p, "cash_amount", 0) or 0),
            "card": int(getattr(p, "card_amount", 0) or 0),
            "total": int(getattr(p, "summa", 0) or 0),
            "allocations": allocations,
            "receipt_url": f"/talim/tolov/chek/{p.id}/",
        })

    return JsonResponse({
        "student": f"{enrollment.student.ism} {enrollment.student.familya}",
        "group": getattr(enrollment.group, "nom", ""),
        "month": selected_month.strftime("%Y-%m"),
        "fee": fee,
        "paid_this_month": paid_this_month,
        "qoldiq": qoldiq,
        "payments": payments,
    })







@login_required
def payment_receipt_pdf(request, payment_id: int):
    if not user_can_manage_payments(request.user):
        return HttpResponse("Forbidden", status=403)

    p = get_object_or_404(Payment.objects.select_related("enrollment__student", "enrollment__group"), id=payment_id)
    enrollment = p.enrollment
    student = enrollment.student
    group = enrollment.group

    # PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    y = h - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "TO‘LOV CHEKI")
    y -= 18

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Chek ID: #{p.id}")
    y -= 16

    c.drawString(50, y, f"O‘quvchi: {student.ism} {student.familya}")
    y -= 16

    c.drawString(50, y, f"Guruh: {getattr(group, 'nom', '')}")
    y -= 16

    cash = int(getattr(p, "cash_amount", 0) or 0)
    card = int(getattr(p, "card_amount", 0) or 0)
    total = int(getattr(p, "summa", 0) or 0)

    c.drawString(50, y, f"Naqd: {cash:,} so‘m".replace(",", " "))
    y -= 16
    c.drawString(50, y, f"Karta: {card:,} so‘m".replace(",", " "))
    y -= 16
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Jami: {total:,} so‘m".replace(",", " "))
    y -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Taqsimot (qaysi oylarga tushdi):")
    y -= 16
    c.setFont("Helvetica", 11)

    allocations = p.allocations.select_related("tuition_month").all()
    if not allocations:
        c.drawString(55, y, "- Allocation topilmadi")
        y -= 14
    else:
        for a in allocations:
            c.drawString(55, y, f"- {a.tuition_month.month.strftime('%Y-%m')}: {a.amount:,} so‘m".replace(",", " "))
            y -= 14
            if y < 80:
                c.showPage()
                y = h - 60

    y -= 10
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 50, "Chaqmoq Academy - To‘lov nazorati tizimi")

    c.showPage()
    c.save()

    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="chek_{p.id}.pdf"'
    return resp













@login_required
def attendance_groups(request):
    """
    Barcha guruhlar ro‘yxati.
    Sidebar'dagi 📅 Guruhlar bo‘limi shu view'ga kiradi.
    """
    groups = (
        Group.objects
        .select_related("center", "oqituvchi")
        .order_by("nom")
    )
    return render(
        request,
        "education/attendance_groups.html",
        {"groups": groups},
    )

import calendar
from django.db.models import Min, Max

@login_required
def group_month_attendance(request, group_id):
    """
    Bitta guruh uchun tanlangan oy bo‘yicha davomat jadvali.
    Satrlarda o‘quvchilar, ustunlarda kunlar.
    """
    group = get_object_or_404(Group, pk=group_id)

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # Oy boshi va oxiri
    first_day = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    day_list = [first_day + timedelta(days=i) for i in range(days_in_month)]

    # Guruhdagi o‘quvchilar
    enrollments = (
        Enrollment.objects
        .filter(group=group)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    students = [e.student for e in enrollments]

    # Shu guruh bo‘yicha barcha davomatlar
    qs = (
        Attendance.objects
        .filter(group=group)
        .select_related("student")
    )

    # Yillar diapazoni (mavjud davomatlar oralig‘i)
    agg = qs.aggregate(min_date=Min("date"), max_date=Max("date"))
    if agg["min_date"] and agg["max_date"]:
        start_year = agg["min_date"].year
        end_year = agg["max_date"].year
    else:
        # Agar hali davomat bo‘lmasa ham, kamida bir yil oldin/bir yil keyin
        start_year = year - 1
        end_year = year + 1
    years = list(range(start_year, end_year + 1))

    # Tanlangan oy uchun davomatlar
    month_qs = qs.filter(date__year=year, date__month=month)

    # (student_id, date) -> Attendance
    att_map = {
        (a.student_id, a.date): a
        for a in month_qs
    }

    # Jadval satrlari: har bir hujayrada sana + status
    rows = []
    for student in students:
        cells = []
        for d in day_list:
            a = att_map.get((student.id, d))
            if not a:
                status = "none"          # umuman davomat olinmagan
            elif a.present:
                status = "present"       # kelgan (ko‘k)
            elif a.forced:
                status = "forced"        # kelmadi, pul yozilgan
            else:
                status = "absent"        # kelmagan (qizil)
            cells.append({"date": d, "status": status})
        rows.append({"student": student, "cells": cells})

    months = [(i, calendar.month_name[i]) for i in range(1, 13)]

    context = {
        "group": group,
        "rows": rows,
        "days": day_list,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "years": years,
        "months": months,
    }
    return render(
        request,
        "education/group_month_attendance.html",
        context,
    )



@require_POST
@login_required
def attendance_toggle_cell(request, group_id):
    """
    Jadvaldagi bitta hujayra ustiga bosilganda:
    none -> present -> absent -> none sikli bo‘yicha o‘zgartiramiz.
    forced (kelmadi, lekin pul yozilgan) yozuvlariga tegmaymiz.
    """
    group = get_object_or_404(Group, pk=group_id)

    student_id = request.POST.get("student_id")
    date_str = request.POST.get("date")
    current_status = request.POST.get("status", "none")

    d = parse_date(date_str)
    if not d or not student_id:
        return JsonResponse({"ok": False, "error": "Bad data"}, status=400)

    student = get_object_or_404(User, pk=student_id, role="student")

    att = Attendance.objects.filter(
        group=group,
        student=student,
        date=d,
    ).first()

    # forced bo‘lsa – o‘zgartirmaymiz
    if att and att.forced:
        return JsonResponse({"ok": True, "status": "forced"})

    # none -> present
    if current_status == "none":
        if not att:
            att = Attendance(
                group=group,
                student=student,
                date=d,
                present=True,
            )
        else:
            att.present = True
            att.forced = False

        if not att.teacher and hasattr(group, "oqituvchi"):
            att.teacher = group.oqituvchi

        att.save()
        new_status = "present"

    # present -> absent
    elif current_status == "present":
        if not att:
            att = Attendance(
                group=group,
                student=student,
                date=d,
                present=False,
            )
        else:
            att.present = False
            att.forced = False
            att.save()
        new_status = "absent"

    # absent -> none (yozuvni o‘chirib tashlaymiz)
    elif current_status == "absent":
        if att:
            att.delete()
        new_status = "none"

    else:
        new_status = current_status or "none"

    return JsonResponse({"ok": True, "status": new_status})


def points_details(request):
    student_id = request.GET.get("student")
    date_str = request.GET.get("date")
    type_ = request.GET.get("type", "plus")

    if not student_id or not date_str:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    tz = timezone.get_current_timezone()

    # Shu kunning oralig‘i (Toshkent vaqti)
    start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()), tz)
    end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()), tz)

    qs = Ledger.objects.filter(student_id=student_id, sana__range=(start, end))
    if type_ == "plus":
        qs = qs.filter(ball__gt=0)
    elif type_ == "minus":
        qs = qs.filter(ball__lt=0)

    details = []
    for l in qs.order_by("-sana"):
        # 👇 Ko‘rsatish uchun vaqt: created_at > sana
        show_dt = l.created_at if getattr(l, "created_at", None) else l.sana
        local_dt = timezone.localtime(show_dt, tz)
        tm = local_dt.strftime("%H:%M | %d-%b-%Y")

        details.append({
            "amount": l.ball,
            "rule": str(l.rule) if l.rule else "",
            "reason": getattr(l.rule, "izoh", "") if hasattr(l.rule, "izoh") else "",
            "teacher": str(l.beruvchi) if l.beruvchi else "",
            "group": str(l.group) if l.group else "",
            "time": tm,
        })

    return JsonResponse({"details": details})


from .models import Student, Category

# education/views.py
from django.shortcuts import render
from django.db.models import Q, Sum
from accounts.models import User
from education.models import Enrollment
from .models import Payment
from datetime import date

def tolovlar_home(request):
    return render(request, "education/tolovlar_home.html")



# education/views.py


# education/views.py




def payment_history(request, student_id):
    """
    O‘quvchining to‘lov tarixini, joriy oy uchun to‘lov va kurs narxini qaytaradi.
    """
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # 🔹 Shu o‘quvchining to‘lovlari
    payments = Payment.objects.filter(student_id=student_id).order_by('sana', 'vaqt')

    if not payments.exists():
        return JsonResponse({
            "kurs_narhi": 0,
            "this_month_paid": 0,
            "qoldiq": 0,
            "month": current_month,
            "year": current_year,
            "payments": []
        }, safe=False)

    # 🔹 Kurs narxi
    first_payment = payments.first()
    kurs_narhi = 0
    if first_payment.enrollment and first_payment.enrollment.kurs_narhi:
        kurs_narhi = first_payment.enrollment.kurs_narhi
    elif first_payment.group and hasattr(first_payment.group, 'kurs_narxi'):
        kurs_narhi = first_payment.group.kurs_narxi

    # 🔹 Hozirgi oy uchun jami to‘lov
    this_month_paid = payments.filter(
        sana__month=current_month,
        sana__year=current_year
    ).aggregate(total=Sum('summa'))['total'] or 0

    # 🔹 Qoldiq
    qoldiq = max(kurs_narhi - this_month_paid, 0)

    # 🔹 To‘lovlar ro‘yxati
    data = [{
        "sana": p.sana.strftime("%d.%m.%Y"),
        "vaqt": p.vaqt.strftime("%H:%M") if p.vaqt else "",
        "cash_amount": int(p.cash_amount or 0),
        "card_amount": int(p.card_amount or 0),
        "kurs_narhi": kurs_narhi
    } for p in payments]

    return JsonResponse({
        "kurs_narhi": kurs_narhi,
        "this_month_paid": this_month_paid,
        "qoldiq": qoldiq,
        "month": current_month,
        "year": current_year,
        "payments": data
    }, safe=False)




def tolov_oqituvchilar(request):
    # whatever you already show for teachers (your groups_home, etc.)
    return render(request, "education/groups_home.html", {})  # or your real context

def payment_monitor(request):
    q = request.GET.get("q", "")
    filter_type = request.GET.get("filter", "")

    payments = Payment.objects.select_related("student", "group", "enrollment")

    if q:
        payments = payments.filter(
            Q(student__ism__icontains=q) |
            Q(student__familya__icontains=q) |
            Q(student__email__icontains=q)
        )

    if filter_type == "card":
        payments = payments.filter(note__icontains="karta")
    elif filter_type == "cash":
        payments = payments.filter(note__icontains="naqd")
    elif filter_type == "full":
        payments = payments.filter(enrollment__jami_tolangan__gte=F('enrollment__kurs_narhi'))
    elif filter_type == "unpaid":
        payments = payments.filter(enrollment__jami_tolangan__lt=F('enrollment__kurs_narhi'))

    stats = []
    today = date.today()

    for p in payments:
        jamlangan = p.enrollment.jami_tolangan if p.enrollment else 0
        kurs_narhi = p.enrollment.kurs_narhi if p.enrollment else 0
        qoldiq = max(kurs_narhi - jamlangan, 0)
        is_full = jamlangan >= kurs_narhi
        is_late = (not is_full) and (p.sana.month < today.month or p.sana.year < today.year)

        stats.append({
            "id": p.id,
            "student": p.student,
            "group": p.group,
            "kurs_narhi": kurs_narhi,
            "jami_tolangan": jamlangan,
            "qoldiq": qoldiq,
            "note": getattr(p, "note", ""),
            "is_full": is_full,
            "is_late": is_late,
            "sana": p.sana,
        })

    return render(request, "education/tolov_nazorati.html", {
        "stats": stats,
        "query": q,
        "filter_type": filter_type,
    })


# ---------- HUB va ro'yxatlar ----------
@login_required
def groups_hub(request):
    """
    📘 Guruhlar markaziy sahifasi — barcha kategoriyalar ro‘yxati.
    """
    from .models import Category  # agar alohida model bo‘lsa
    categories = Category.objects.all() if hasattr(Category, "objects") else []
    return render(request, "education/groups_home.html", {
        "categories": categories,
    })

def group_delete_confirm(request, id):
    group = get_object_or_404(Group, id=id)
    if request.method == "POST":
        group.delete()
        return redirect("education:groups_home")
    return render(request, "education/group_delete_confirm.html", {"g": group})



@login_required
def edit_category(request, id):
    cat = get_object_or_404(Category, id=id)
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")

        cat.name = name
        cat.description = description

        # 🔹 Agar yangi rasm tanlangan bo‘lsa, yangisini saqlaymiz
        if image:
            cat.image = image

        cat.save()
        messages.success(request, "Bo‘lim muvaffaqiyatli tahrirlandi ✅")
        return redirect("education:groups_home")

    return render(request, "education/category_edit.html", {"cat": cat})


@login_required
def delete_category(request, id):
    cat = get_object_or_404(Category, id=id)
    if request.method == "POST":
        cat.delete()
        messages.success(request, "Bo‘lim o‘chirildi 🗑️")
        return redirect("education:groups_home")
    return render(request, "education/category_delete_confirm.html", {"cat": cat})


@login_required
def groups_by_category(request, category):
    if category not in ("lang", "it"):
        raise Http404("Noto‘g‘ri kategoriya")

    rows = (
        Group.objects.filter(category=category)
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(
        request,
        "education/groups_by_category.html",
        {"rows": rows, "category": category, "can_manage": _can_manage(request.user)},
    )


# DRY: guruh yaratish
@login_required
def create_group_for_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)

            # 🟢 To‘g‘ri maydon: ForeignKey bo‘lgan 'category_obj'
            group.category_obj = category

            # Eski 'category' maydoni ham to‘ldirilsa yaxshi
            group.category = Group.IT  # yoki Group.LANG — kerakli turga qarab
            group.save()

            messages.success(request, f"✅ '{group.nom}' guruhi {category.name} bo‘limiga qo‘shildi.")
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm()

    return render(request, "education/group_form.html", {"form": form, "category": category})

# @login_required
# def group_create_lang(request):
#     return _create_group(request, Group.LANG)


# @login_required
# def group_create_it(request):
#     return _create_group(request, Group.IT)


# (eski ro'yxatlar kerak bo'lsa)
@login_required
def guruhlar(request):
    rows = (
        Group.objects.select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(request, "education/groups.html", {"rows": rows, "can_manage": _can_manage(request.user)})


@login_required
def guruhlar_tillar(request):
    return groups_by_category(request, Group.LANG)


@login_required
def guruhlar_it(request):
    return groups_by_category(request, Group.IT)


# ---------- Bitta guruh (bitta sahifada hamma narsa) ----------
@login_required
def group_detail(request, pk: int):
    g = get_object_or_404(Group, pk=pk)

    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return HttpResponseForbidden("Siz bu guruhni ko‘ra olmaysiz.")

    date_str = request.GET.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    if not selected_date:
        selected_date = localdate()

    enrollments = (
        Enrollment.objects
        .filter(group=g)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    student_ids = [e.student_id for e in enrollments]

    # Balanslar
    bal_qs = (
        Ledger.objects
        .filter(student_id__in=student_ids)
        .values("student_id")
        .annotate(s=Coalesce(Sum("ball"), 0))
    )
    bal_map = {b["student_id"]: b["s"] for b in bal_qs}

    # Sana bo'yicha Attendance (DateTimeField bo'lsa ham ishlaydi)
    try:
        start = make_aware(datetime.combine(selected_date, datetime.min.time()))
        end   = make_aware(datetime.combine(selected_date + timedelta(days=1),
                                           datetime.min.time()))
        att_qs = Attendance.objects.filter(group=g, date__gte=start, date__lt=end)
    except Exception:
        att_qs = Attendance.objects.filter(group=g, date=selected_date)

    pres_map   = {}
    forced_map = {}
    for a in att_qs:
        pres_map[a.student_id]   = a.present
        forced_map[a.student_id] = getattr(a, "forced", False)

    # Studentga soxta fieldlar
    for e in enrollments:
        s = e.student
        s.balance       = int(bal_map.get(s.id, 0))
        s.present_today = bool(pres_map.get(s.id, False))
        s.forced_today  = bool(forced_map.get(s.id, False))

    can_add_student = request.user.role in ["director", "manager", "teacher"]

    ctx = {
        "g": g,
        "enrollments": enrollments,
        "rules_plus": Rule.objects.filter(tur=Rule.PLUS).order_by("nom"),
        "rules_minus": Rule.objects.filter(tur=Rule.MINUS).order_by("nom"),
        "can_add_student": can_add_student,
        "selected_date": selected_date.isoformat(),
        "today": localdate().isoformat(),
    }
    return render(request, "education/group_detail.html", ctx)


from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils.dateparse import parse_date

@login_required
@require_POST
def attendance_force(request):
    """
    Tanlangan guruh va sana bo‘yicha:
    ✅ kelmagan (present=False) o‘quvchilar uchun
    forced=True qilib, o‘qituvchiga pul yoziladigan dars sifatida belgilaydi.

    Frontend POST yuboradi:
      - group_id
      - date (YYYY-MM-DD)
    """
    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    # 🔴 JS dagi xabardagi "Ma'lumot yetarli emas" — mana shu joydan keladi
    if not group_id or not date_str:
        return JsonResponse({"ok": False, "error": "Maʼlumot yetarli emas"})

    date_obj = parse_date(date_str)
    if not date_obj:
        return JsonResponse({"ok": False, "error": "Sana noto‘g‘ri formatda"})

    # Guruhni olamiz
    g = get_object_or_404(Group, pk=group_id)

    # Shu guruhdagi barcha enrollments
    enrollments = Enrollment.objects.filter(group=g).select_related("student")

    # Shu sana uchun mavjud attendance yozuvlari
    att_qs = Attendance.objects.filter(group=g, date=date_obj)
    att_by_student = {a.student_id: a for a in att_qs}

    forced_count = 0

    for enr in enrollments:
        att = att_by_student.get(enr.student_id)

        if att:
            # Agar allaqachon present=True bo‘lsa, buni majburan "kelmadi" qilishni xohlamaymiz
            # (agar kerak bo‘lsa, bu qismni o‘zing o‘zgartirasan)
            if att.present:
                continue

            if not att.forced:
                att.forced = True
                att.present = False  # forced bo‘lsa ham uni "kelmadi" deb saqlab qo‘yamiz
                att.save()
                forced_count += 1
        else:
            # Hech qanday attendance yo‘q bo‘lsa, yangi "kelmadi, forced" yozuvi yaratamiz
            Attendance.objects.create(
                group=g,
                student=enr.student,
                teacher=g.oqituvchi,
                date=date_obj,
                present=False,
                forced=True,
            )
            forced_count += 1

    return JsonResponse({
        "ok": True,
        "count": forced_count,
    })


@login_required
def attend_all(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"})

    g = get_object_or_404(Group, pk=pk)

    # faqat direktor/manager/teacher
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return JsonResponse({"ok": False, "error": "ruxsat yo‘q"})

    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    # davomat qayd qilish
    students = Enrollment.objects.filter(group=g)
    count = 0

    for e in students:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True}
        )
        count += 1

    return JsonResponse({"ok": True, "count": count})

@require_POST
@login_required
def attend_all_students(request, g_id):
    # Guruhni olish
    g = get_object_or_404(Group, pk=g_id)

    # faqat shu guruh o‘qituvchisi ko‘ra olsin
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return JsonResponse({"ok": False, "error": "ruxsat yo‘q"})

    # Sana
    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    # Guruhdagi barcha o‘quvchilar
    enrollments = (
        Enrollment.objects
        .filter(group=g)
        .select_related("student")
    )

    count = 0
    for e in enrollments:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True}
        )
        count += 1

    return JsonResponse({"ok": True, "count": count})

# ---------- AJAX: Davomatni saqlash ----------
@login_required
def attendance_today(request, pk: int):
    """
    Har bir guruh uchun davomatni alohida saqlaydi.
    O‘quvchi bir kunda IT va Ingliz tilida qatnashsa — ikkita alohida Attendance yozuvi yaratiladi.
    Chaqmoqlar esa umumiy hisobda qoladi.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    # Guruhni topamiz
    g = get_object_or_404(Group, pk=pk)

    # Foydalanuvchi huquqini tekshiramiz
    if not _teacher_can(request.user, g):
        return JsonResponse({"ok": False, "error": "Ruxsat yo‘q"}, status=403)

    # Ma'lumotlarni olish
    enr_id = request.POST.get("enr_id")
    present_val = request.POST.get("present")
    date_str = request.POST.get("date")

    if not (enr_id and present_val is not None):
        return JsonResponse({"ok": False, "error": "Incomplete data"}, status=400)

    try:
        enrollment = Enrollment.objects.select_related("student").get(pk=int(enr_id), group=g)
    except Enrollment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Enrollment not found"}, status=404)

    student = enrollment.student
    present = str(present_val).lower() in ("1", "true", "yes", "on")

    # ✅ Sanani aniqlash
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            selected_date = localdate()
    else:
        selected_date = localdate()

    # ⚙️ Davomatni alohida guruhga yozamiz
    att, created = Attendance.objects.update_or_create(
        group=g,
        student=student,
        date=selected_date,
        defaults={"present": present, "teacher": request.user},
    )

    # 🔹 Endi chaqmoq tizimi (Ledger) umumiy qoladi, o‘chirmaymiz.
    # Faqat kelmagan bo‘lsa, shu guruhdagi shu kundagi yozuvlarni o‘chiramiz.
    removed_points = 0
    if not present:
        start = make_aware(datetime.combine(selected_date, datetime.min.time()))
        end = make_aware(datetime.combine(selected_date + timedelta(days=1), datetime.min.time()))
        removed_points = Ledger.objects.filter(
            student=student, group=g,
            sana__gte=start, sana__lt=end
        ).count()
        Ledger.objects.filter(
            student=student, group=g,
            sana__gte=start, sana__lt=end
        ).delete()

    return JsonResponse({
        "ok": True,
        "present": present,
        "removed_points": removed_points,
        "created": created
    })



@login_required
def group_bulk_remove(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "POST bo‘lishi shart."})

    g = get_object_or_404(Group, pk=pk)

    # ruxsat tekshirish
    if request.user.role not in ["director", "manager", "teacher", "admin"]:
        return JsonResponse({"ok": False, "msg": "Ruxsat yo‘q."})

    ids = request.POST.getlist("enrollment_ids")

    if not ids:
        return JsonResponse({"ok": False, "msg": "ID kelmagan."})

    qs = Enrollment.objects.filter(id__in=ids, group=g)
    count = qs.count()
    qs.delete()

    return JsonResponse({"ok": True, "deleted": count})




# ---------- AJAX: Chaqmoq yozish/ayirish ----------
@login_required
def group_points(request, pk: int):
    # Faqat POST
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    # JSON yoki form-data
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode())
        except Exception:
            data = {}
    else:
        data = request.POST

    # Guruhni tekshirish
    g = get_object_or_404(Group, pk=pk)
    if request.user.role == "teacher" and g.oqituvchi != request.user and not _teacher_can(request.user, g):
        return HttpResponseForbidden()

    # Ma'lumotlarni olish
    student_id = (data.get("student_id") or "").strip()
    rule_id = (data.get("rule_id") or "").strip()
    amount_raw = (data.get("amount") or "0").strip()
    date_str = (data.get("date") or "").strip()

    # Ballni parse qilish
    try:
        amount = int(amount_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Noto‘g‘ri ball kiritildi"}, status=400)

    if amount == 0:
        return JsonResponse({"ok": False, "error": "0 ball yozilmaydi"}, status=400)

    # Studentni olish
    student = get_object_or_404(User, pk=int(student_id), role="student")

    # Qoida olish
    if rule_id and rule_id.isdigit():
        rule = get_object_or_404(Rule, pk=int(rule_id))
    else:
        rule = Rule.objects.filter(nom="Erkin ball").first() or Rule.objects.create(
            nom="Erkin ball", tur=Rule.PLUS, min_baho=1, max_baho=1000000
        )

    # ✅ SANANI ANIQLASH
    if date_str:
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            parsed_date = timezone.localdate()
    else:
        parsed_date = timezone.localdate()

    sana = timezone.make_aware(datetime.combine(parsed_date, datetime.min.time()))

    # ✅ Kunlik chaqmoq limitini tekshirish
    from .models import DailyLightningSetting  # import kerak bo‘ladi
    setting = DailyLightningSetting.objects.filter(date=parsed_date, active=True).first()
    if setting and setting.max_lightning > 0:
        today_sum = Ledger.objects.filter(
            student=student,
            sana__date=parsed_date
        ).aggregate(s=Coalesce(Sum('ball'), 0))['s'] or 0

        if today_sum + amount > setting.max_lightning:
            return JsonResponse({
                "ok": False,
                "error": f"Bugun {setting.max_lightning} tadan ortiq chaqmoq berish mumkin emas."
            }, status=400)

    # ⚡ Ledger yozuvini yaratish
    record = Ledger.objects.create(
        student=student,
        beruvchi=request.user,
        group=g,
        rule=rule,
        ball=amount,
        sana=sana,
    )

    # Balansni qayta hisoblash
    balance_agg = Ledger.objects.filter(student=student).aggregate(s=Coalesce(Sum("ball"), 0))
    balance = int(balance_agg.get("s") or 0)

    return JsonResponse({
        "ok": True,
        "amount": amount,
        "balance": balance,
        "saved_date": parsed_date.strftime("%Y-%m-%d"),
        "id": record.id
    })

@login_required
def groups_home(request):
    categories = Category.objects.all().order_by("name")
    return render(request, "education/groups_home.html", {"categories": categories})


def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    groups = Group.objects.filter(category_obj=category).order_by("id")

    return render(request, "education/category_detail.html", {
        "category": category,
        "groups": groups,
        "groups_count": groups.count(),
    })

from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from education.models import Group, Dars, OylikHisobot
from accounts.models import User

@login_required
def oylik_hisobot(request):
    """Har bir o‘qituvchining oyligini avtomatik hisoblash"""
    oy = datetime.now().strftime("%B")
    yil = datetime.now().year
    oylik_data = []

    teachers = User.objects.filter(role='teacher')

    for teacher in teachers:
        guruhlar = Group.objects.filter(oqituvchi=teacher)
        jami_darslar = 0
        jami_daromad = 0

        for g in guruhlar:
            darslar_soni = Dars.objects.filter(
                guruh=g,
                oqituvchi=teacher,
                sana__month=datetime.now().month,
                sana__year=datetime.now().year
            ).count()

            dars_tolovi = g.dars_boshiga_tolov()
            jami_darslar += darslar_soni
            jami_daromad += darslar_soni * dars_tolovi

        markaz_foydasi = jami_daromad * 0.5  # misol uchun 50/50

        oylik_data.append({
            "oqituvchi": teacher.get_full_name() or teacher.username,
            "guruhlar": guruhlar.count(),
            "darslar": jami_darslar,
            "daromad": round(jami_daromad),
            "markaz_foydasi": round(markaz_foydasi),
        })

        # OylikHisobot jadvaliga yozib qo‘yish
        OylikHisobot.objects.update_or_create(
            oqituvchi=teacher,
            oy=oy,
            yil=yil,
            defaults={
                "jami_darslar": jami_darslar,
                "jami_daromad": round(jami_daromad),
                "markaz_foydasi": round(markaz_foydasi)
            }
        )

    return render(request, "education/oylik_hisobot.html", {"oylik_data": oylik_data, "oy": oy, "yil": yil})





@login_required
def group_create_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.category_obj = category
            group.save()
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm()

    return render(request, "education/group_form.html", {
        "form": form,
        "category": category
    })



from .models import Category
from django import forms
from django.contrib import messages

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "image", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Masalan: Dizayn"
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Bo‘lim haqida qisqa izoh"
            }),
        }



@login_required
def groups_home(request):
    # kategoriyalar
    categories = list(Category.objects.all().order_by("name"))

    # har bir category uchun guruhlar sonini hisoblab map qilamiz
    counts_qs = (
        Group.objects
        .values("category_obj")          # FK field nomi sizda shu: category_obj
        .annotate(c=Count("id"))
    )
    count_map = {row["category_obj"]: row["c"] for row in counts_qs}

    # template ishlatishi uchun cat.groups_count qo‘shib chiqamiz
    for cat in categories:
        cat.groups_count = count_map.get(cat.id, 0)

    return render(request, "education/groups_home.html", {
        "categories": categories,
        "categories_count": len(categories),
    })


@login_required
def add_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Bo‘lim muvaffaqiyatli qo‘shildi ✅")
            return redirect("education:groups_home")
    else:
        form = CategoryForm()
    return render(request, "education/category_add.html", {"form": form})




@login_required
def student_detail(request, student_id: int):
    student = get_object_or_404(User, pk=student_id, role="student")

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

    # 🔹 Chaqmoqlar ham guruh bo‘yicha hisoblanadi
    ledgers = Ledger.objects.filter(student=student).select_related("group").annotate(
        year=ExtractYear('sana'),
        month=ExtractMonth('sana')
    )

    # 🔹 Har bir guruh bo‘yicha ajratamiz
    grouped_by_group = {}
    for a in attendances:
        grouped_by_group.setdefault(a.group, []).append(a)

    month_summaries = []
    for group, group_attendances in grouped_by_group.items():
        # Guruh bo‘yicha oylik natijalarni tayyorlash
        grouped_by_month = {}
        for a in group_attendances:
            key = (a.year, a.month)
            grouped_by_month.setdefault(key, []).append(a)

        for (year, month), records in grouped_by_month.items():
            total_present = sum(1 for r in records if r.present)
            month_ledgers = ledgers.filter(year=year, month=month, group=group)
            plus_sum = month_ledgers.filter(ball__gt=0).aggregate(total=Sum('ball'))['total'] or 0
            minus_sum = month_ledgers.filter(ball__lt=0).aggregate(total=Sum('ball'))['total'] or 0

            month_summaries.append({
                "group": group.nom,  # 🔹 Guruh nomini qo‘shamiz
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES.get(month, "Noma’lum oy"),
                "present_days": total_present,
                "plus": plus_sum,
                "minus": abs(minus_sum),
                "days": [
                    {
                        "date": r.date,
                        "present": r.present,
                        "plus": ledgers.filter(group=group, sana__date=r.date, ball__gt=0).aggregate(total=Sum('ball'))['total'] or 0,
                        "minus": abs(ledgers.filter(group=group, sana__date=r.date, ball__lt=0).aggregate(total=Sum('ball'))['total'] or 0)
                    }
                    for r in records
                ]
            })

    ctx = {
        "student": student,
        "month_summaries": month_summaries,
    }

    return render(request, "education/student_detail.html", ctx)




# ---------- (ixtiyoriy) alohida Davomat/Chaqmoq sahifasi ----------
@login_required
def group_rollcall(request, pk):
    g = get_object_or_404(Group, pk=pk)
    if not _can_give_points(request.user, g):
        return HttpResponseForbidden()

    # sana
    date_str = request.GET.get("date") or request.POST.get("date")
    try:
        the_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else localdate()
    except Exception:
        the_date = localdate()

    students = [
        e.student for e in g.enrollments.select_related("student").order_by("student__ism", "student__familya")
    ]

    pres_map = {
        a.student_id: a.present for a in Attendance.objects.filter(group=g, date=the_date)
    }
    bal_map = {
        row["student_id"]: (row["total"] or 0)
        for row in (
            Ledger.objects.filter(student_id__in=[s.id for s in students])
            .values("student_id").annotate(total=Sum("ball"))
        )
    }

    for s in students:
        s.present = pres_map.get(s.id, False)
        s.balance = bal_map.get(s.id, 0)

    rules = Rule.objects.order_by("nom")

    if request.method == "POST" and request.POST.get("save") == "1":
        saved = 0
        for s in students:
            present = bool(request.POST.get(f"present_{s.id}"))
            Attendance.objects.update_or_create(
                group=g,
                student=s,
                date=the_date,
                defaults={"present": present, "teacher": request.user if request.user.role == "teacher" else None},
            )
            rule_id = request.POST.get(f"rule_{s.id}")
            amount_raw = request.POST.get(f"ball_{s.id}") or "0"
            try:
                amount = int(amount_raw)
            except ValueError:
                amount = 0
            if rule_id and amount:
                rule = get_object_or_404(Rule, pk=int(rule_id))
                abs_ball = abs(amount)
                if rule.min_baho <= abs_ball <= rule.max_baho:
                    signed = abs_ball if rule.tur == Rule.PLUS else -abs_ball
                    Ledger.objects.create(student=s, beruvchi=request.user, group=g, rule=rule, ball=signed)
                    saved += 1
        messages.success(request, f"Saqlash tugadi. {saved} ta chaqmoq yozildi.")
        return redirect(f"{request.path}?date={the_date.isoformat()}")

    return render(
        request,
        "education/group_rollcall.html",
        {"g": g, "date": the_date.isoformat(), "students": students, "rules": rules},
    )

@login_required
def teacher_salary_list(request):
    teachers = User.objects.filter(role='teacher').order_by('ism')
    return render(request, "education/teacher_salary_list.html", {"teachers": teachers})


# 🔹 2. O‘qituvchining barcha guruhlari
@login_required
def teacher_groups(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id, role="teacher")
    groups = Group.objects.filter(oqituvchi=teacher).prefetch_related('enrollments__student', 'attendances')

    teacher_data = []
    for group in groups:
        enrollments = []
        for e in group.enrollments.all():
            attended = group.attendances.filter(student=e.student, present=True).count()
            enrollments.append({
                "student": e.student,
                "kurs_narhi": e.kurs_narhi,
                "foiz": e.oqituvchi_foiz,
                "attended": attended,
                "daromad": e.real_oqituvchi_daromadi(),
            })
        total_income = sum(e["daromad"] for e in enrollments)

        teacher_data.append({
            "group": group,
            "enrollments": enrollments,
            "foiz": group.oqituvchi_foiz,
            "daromad": total_income,
        })

    return render(request, "education/teacher_groups.html", {
        "teacher": teacher,
        "teacher_data": teacher_data,
    })



@login_required
def teacher_salary_report(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    enrollments = group.enrollments.select_related("student")

    total_lessons = Attendance.objects.filter(group=group).values("date").distinct().count()
    per_lesson_income = group.dars_boshiga_tolov()

    student_summaries = []
    for e in enrollments:
        attended = Attendance.objects.filter(group=group, student=e.student, present=True).count()
        teacher_income = attended * per_lesson_income
        student_summaries.append({
            "student": e.student,
            "attended": attended,
            "teacher_income": teacher_income
        })

    teacher_total_income = sum(s["teacher_income"] for s in student_summaries)

    ctx = {
        "group": group,
        "student_summaries": student_summaries,
        "teacher_total_income": teacher_total_income,
        "month": timezone.now().strftime("%B"),
        "year": timezone.now().year,
    }
    return render(request, "education/teacher_salary_report.html", ctx)


# 📊 DIREKTOR HISOBOT PANELI






@login_required
def teacher_salary_summary(request):
    """
    O'qituvchilar maoshi va markaz foydasini yil/oy bo'yicha hisoblaydi.
    - Attendance: present=True YOKI forced=True bo'lgan barcha darslar hisobga olinadi.
    """

    # ================================
    # Tanlangan yil / oy
    # ================================
    today = date.today()
    selected_year = int(request.GET.get("year") or today.year)
    selected_month = int(request.GET.get("month") or today.month)

    # Oylar ro'yxati
    months = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
        (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
        (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
    ]
    chart_labels = [m[1] for m in months]

    # ================================
    # 1) Attendance: yil bo'yicha
    #    present=True VA forced=True ikkala holat ham dars hisoblanadi
    # ================================
    attendance = (
        Attendance.objects
        .annotate(
            y=ExtractYear("date"),
            m=ExtractMonth("date"),
        )
        .filter(y=selected_year)
        .filter(Q(present=True) | Q(forced=True))  # 🔥 MUHIM JOY
        .values("group_id", "student_id", "m")
        .annotate(les=Count("id"))
    )

    # (group, student, month) => darslar soni
    attendance_map = {
        (a["group_id"], a["student_id"], a["m"]): a["les"]
        for a in attendance
    }

    # ================================
    # 2) O'qituvchilar + guruhlari + enrollment
    # ================================
    teachers = (
        User.objects
        .filter(role="teacher")
        .prefetch_related(
            Prefetch(
                "group_set",
                queryset=Group.objects.prefetch_related(
                    Prefetch(
                        "enrollments",
                        queryset=Enrollment.objects.select_related("student")
                    )
                )
            )
        )
    )

    # ================================
    # Grafik uchun bo'sh massivlar (12 oy)
    # ================================
    chart_teacher_income = [0] * 12
    chart_center_income = [0] * 12
    chart_total_turnover = [0] * 12

    # ================================
    # 3) HISOB-KITOB
    # ================================
    teacher_data = []

    for teacher in teachers:

        # Tanlangan oy uchun ko'rsatkichlar
        month_lessons = 0
        month_teacher_income = 0
        month_center_profit = 0
        month_turnover = 0

        # 12 oy bo'yicha aylanib chiqamiz
        for month_num, _ in months:

            m_lessons = 0
            m_teacher_income = 0
            m_center_profit = 0
            m_turnover = 0

            for group in teacher.group_set.all():
                for enr in group.enrollments.all():

                    kurs = enr.kurs_narhi or 0
                    foiz = (enr.oqituvchi_foiz or 0) / 100

                    # Shu oyda shu o'quvchi nechta dars qilgan?
                    les = attendance_map.get((group.id, enr.student.id, month_num), 0)

                    if les > 0:
                        # 1 oy = 12 ta dars deb qabul qilingan
                        teacher_part = kurs * foiz / 12
                        center_part = kurs * (1 - foiz) / 12
                        turnover_part = kurs / 12

                        m_lessons += les
                        m_teacher_income += teacher_part * les
                        m_center_profit += center_part * les
                        m_turnover += turnover_part * les

            # 🔹 Grafiklar uchun yig'amiz
            chart_teacher_income[month_num - 1] += m_teacher_income
            chart_center_income[month_num - 1] += m_center_profit
            chart_total_turnover[month_num - 1] += m_turnover

            # 🔹 Jadval faqat tanlangan oy uchun
            if month_num == selected_month:
                month_lessons = m_lessons
                month_teacher_income = m_teacher_income
                month_center_profit = m_center_profit
                month_turnover = m_turnover

        teacher_data.append({
            "teacher": teacher.get_full_name() or teacher.username,
            "groups": teacher.group_set.count(),
            "lessons": month_lessons,
            "teacher_income": round(month_teacher_income),
            "center_profit": round(month_center_profit),
            "total_turnover": round(month_turnover),
        })

    # ================================
    # 4) AJAX JSON Response (year/month select o'zgarganda)
    # ================================
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "year": selected_year,
            "month": selected_month,
            "teacher_data": teacher_data,
            "chart_teacher_income": chart_teacher_income,
            "chart_center_income": chart_center_income,
            "chart_total_turnover": chart_total_turnover,
        })

    # ================================
    # 5) HTML render
    # ================================
    return render(request, "education/teacher_salary_summary.html", {
        "years": list(range(2024, 2036)),
        "months": months,
        "selected_year": selected_year,
        "selected_month": selected_month,
        "teacher_data": teacher_data,
        "chart_labels": chart_labels,
        "chart_teacher_income": chart_teacher_income,
        "chart_center_income": chart_center_income,
        "chart_total_turnover": chart_total_turnover,
    })

    # Tanlangan yil / oy
    # selected_year = int(request.GET.get("year", date.today().year))
    # selected_month = int(request.GET.get("month", localdate().month))

    # # Oylar nomlari
    # months = [
    #     (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
    #     (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
    #     (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
    # ]
    # chart_labels = [m[1] for m in months]

    # # ---------------------------------------------
    # #  1) Attendance ni to‘g‘ri olish (DateTimeField fix)
    # # ---------------------------------------------
    # attendance = (
    #     Attendance.objects
    #     .annotate(
    #         y=ExtractYear("date"),
    #         m=ExtractMonth("date")
    #     )
    #     .filter(y=selected_year)
    #     .values("group_id", "student_id", "m")
    #     .annotate(les=Count("id"))
    # )

    # attendance_map = {
    #     (a["group_id"], a["student_id"], a["m"]): a["les"]
    #     for a in attendance
    # }

    # # ---------------------------------------------
    # #  2) Teachers + groups + enrollments
    # # ---------------------------------------------
    # teachers = User.objects.filter(role="teacher").prefetch_related(
    #     Prefetch(
    #         "group_set",
    #         queryset=Group.objects.prefetch_related(
    #             Prefetch("enrollments", queryset=Enrollment.objects.select_related("student"))
    #         )
    #     )
    # )

    # # Grafiklar uchun 12 oy bo‘yicha bo‘sh massiv
    # chart_teacher_income = [0] * 12
    # chart_center_income = [0] * 12
    # chart_total_turnover = [0] * 12

    # teacher_data = []

    # # ---------------------------------------------
    # #  3) HISOB-KITOB
    # # ---------------------------------------------
    # for teacher in teachers:

    #     total_lessons = 0
    #     total_teacher_income = 0
    #     total_center_profit = 0
    #     total_turnover = 0

    #     for month_num, _ in months:

    #         m_lessons = 0
    #         m_teacher_income = 0
    #         m_center_profit = 0
    #         m_turnover = 0

    #         for group in teacher.group_set.all():

    #             for enr in group.enrollments.all():
    #                 kurs = enr.kurs_narhi or 0
    #                 foiz = (enr.oqituvchi_foiz or 0) / 100

    #                 # Agar dars bo‘lmasa → daromad bo‘lmaydi
    #                 les = attendance_map.get((group.id, enr.student.id, month_num), 0)

    #                 if les > 0:
    #                     teacher_part = kurs * foiz / 12
    #                     center_part = kurs * (1 - foiz) / 12
    #                     turnover_part = kurs / 12

    #                     m_lessons += les
    #                     m_teacher_income += teacher_part * les
    #                     m_center_profit += center_part * les
    #                     m_turnover += turnover_part * les

    #         # Grafik to‘ldirish
    #         idx = month_num - 1
    #         chart_teacher_income[idx] += m_teacher_income
    #         chart_center_income[idx] += m_center_profit
    #         chart_total_turnover[idx] += m_turnover

    #         total_lessons += m_lessons
    #         total_teacher_income += m_teacher_income
    #         total_center_profit += m_center_profit
    #         total_turnover += m_turnover

    #     teacher_data.append({
    #         "teacher": teacher.get_full_name() or teacher.username,
    #         "groups": teacher.group_set.count(),
    #         "lessons": total_lessons,
    #         "teacher_income": round(total_teacher_income),
    #         "center_profit": round(total_center_profit),
    #         "total_turnover": round(total_turnover),
    #     })

    # # AJAX so‘rovi (fetch)
    # if request.headers.get("x-requested-with") == "XMLHttpRequest":
    #     return JsonResponse({
    #         "year": selected_year,
    #         "month": selected_month,
    #         "teacher_data": teacher_data,
    #         "chart_teacher_income": chart_teacher_income,
    #         "chart_center_income": chart_center_income,
    #         "chart_total_turnover": chart_total_turnover,
    #     })

    # return render(request, "education/teacher_salary_summary.html", {
    #     "years": list(range(2024, 2036)),
    #     "months": months,
    #     "selected_year": selected_year,
    #     "selected_month": selected_month,
    #     "teacher_data": teacher_data,
    #     "chart_labels": chart_labels,
    #     "chart_teacher_income": chart_teacher_income,
    #     "chart_center_income": chart_center_income,
    #     "chart_total_turnover": chart_total_turnover,
    # })

@login_required
def force_absent_attendance(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    group = get_object_or_404(Group, id=group_id)
    date = parse_date(date_str)

    enrollments = Enrollment.objects.filter(group=group)
    forced_count = 0

    for enr in enrollments:
        att, created = Attendance.objects.get_or_create(
            group=group,
            student=enr.student,
            date=date,
            defaults={"present": False}
        )

        # kelgan bo‘lsa — forced qilmaymiz
        if att.present:
            continue

        # forced=True qilamiz
        if not att.forced:
            att.forced = True
            att.save()
            forced_count += 1

    return JsonResponse({"ok": True, "count": forced_count})


# ================================
#   RENDER HELPER
# ================================
def _render_salary(request, selected_year, selected_month,
                   teacher_data, chart_labels,
                   chart_teacher_income, chart_center_income, chart_total_turnover):

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "year": selected_year,
            "month": selected_month,
            "teacher_data": teacher_data,
            "chart_teacher_income": chart_teacher_income,
            "chart_center_income": chart_center_income,
            "chart_total_turnover": chart_total_turnover,
        })

    return render(request, "education/teacher_salary_summary.html", {
        "years": list(range(2024, 2036)),
        "months": [
            (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
            (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
            (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
        ],
        "selected_year": selected_year,
        "selected_month": selected_month,
        "teacher_data": teacher_data,
        "chart_labels": chart_labels,
        "chart_teacher_income": chart_teacher_income,
        "chart_center_income": chart_center_income,
        "chart_total_turnover": chart_total_turnover,
    })

@login_required
def teacher_salary_redirect(request):
    group = None

    # O‘qituvchi bo‘lsa — o‘z guruhini topadi
    if request.user.role == "teacher":
        group = Group.objects.filter(oqituvchi=request.user).first()

    # Direktor yoki superuser bo‘lsa — birinchi mavjud guruhni topadi
    elif request.user.role == "director" or request.user.is_superuser:
        group = Group.objects.first()

    # Agar topilmasa — xabar chiqar va qaytar
    if not group:
        messages.warning(request, "Hech qanday guruh topilmadi!")
        return redirect("education:groups_it")

    # Topilgan guruh bo‘yicha maosh sahifasiga yo‘naltirish
    return redirect("education:teacher_salary_report", group.id)



# ---------- CRUD ----------
@login_required
def group_create(request, category=None):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:guruhlar")

    if category == Group.LANG:
        FormCls, title = LangGroupForm, "Tillar bo‘yicha guruh yaratish"
    elif category == Group.IT:
        FormCls, title = ITGroupForm, "IT bo‘yicha guruh yaratish"
    else:
        FormCls, title = GroupForm, "Guruh yaratish"

    form = FormCls(request.POST or None)

    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)

        # 🔹 Kategoriya bo‘sh bo‘lsa, avtomatik to‘ldir
        g.category = category or Group.LANG

        # 🔹 Center avtomatik foydalanuvchidan
        if not g.center_id:
            if hasattr(request.user, "center") and request.user.center:
                g.center = request.user.center
            else:
                from accounts.models import Center
                g.center = Center.objects.first()

        # ✅ Foydalanuvchi kurs narxini kiritgan bo‘lsa — o‘sha qiymatni saqlaymiz
        if g.kurs_narxi in [None, "", 0]:
            g.kurs_narxi = 500000  # faqat bo‘sh bo‘lsa default beramiz

        # ✅ O‘qituvchi foizi
        if not g.oqituvchi_foiz:
            g.oqituvchi_foiz = 40

        # ✅ Oylik dars soni
        if not g.oy_dars_soni:
            g.oy_dars_soni = 12

        g.save()
        messages.success(request, f"✅ {g.nom} guruhi muvaffaqiyatli yaratildi.")
        return redirect("education:group_detail", pk=g.pk)

    elif request.method == "POST":
        print("❌ Forma xato:", form.errors)

    return render(request, "education/group_form.html", {"form": form, "title": title})


@login_required
def group_edit(request, pk):
    if not request.user.is_superuser and request.user.role not in ["Director", "Manager", "Teacher"]:
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:groups")

    g = get_object_or_404(Group, pk=pk)
    form = GroupForm(request.POST or None, instance=g)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "✅ Guruh yangilandi.")
        return redirect("education:group_detail", pk=g.id)

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "✏️ Guruhni tahrirlash",
    })




@login_required
def group_list(request):
    """
    Barcha guruhlar ro‘yxati.
    """
    rows = Group.objects.select_related("center", "oqituvchi").all()
    can_manage = request.user.is_superuser or request.user.role in ["Director", "Manager", "Teacher"]

    context = {
        "rows": rows,
        "can_manage": can_manage,
    }
    return render(request, "education/groups.html", context)

def get_group_price(request, pk):
    try:
        group = Group.objects.get(pk=pk)
        return JsonResponse({"price": group.kurs_narhi})
    except Group.DoesNotExist:
        return JsonResponse({"price": 0})



@login_required
def group_add(request):
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:groups")

    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "✅ Guruh muvaffaqiyatli qo‘shildi.")
        return redirect("education:groups")

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Yangi guruh qo‘shish",
    })




from django.contrib import messages

@login_required
def group_delete(request, pk):
    """
    Guruhni o‘chirish — tasdiq bilan.
    """
    group = get_object_or_404(Group, pk=pk)

    if request.method == "POST":
        category = getattr(group, "category_obj", None)
        group.delete()
        messages.success(request, "🗑️ Guruh o‘chirildi.")

        if category:
            return redirect("education:category_detail", category_id=category.id)
        return redirect("education:groups")

    return render(request, "education/group_delete_confirm.html", {"group": group})


@login_required
def add_student_to_group(request, pk: int):
    g = get_object_or_404(Group, pk=pk)

    allowed_roles = ['admin', 'manager', 'teacher', 'director']
    if request.user.role not in allowed_roles:
        return HttpResponseForbidden("❌ Sizda bu amalni bajarish uchun ruxsat yo‘q.")

    students = (
        User.objects
        .filter(role="student")
        .exclude(enrollment__group=g)
        .order_by("ism", "familya")
    )

    if request.method == "POST":
        student_ids = request.POST.getlist("student_ids")

        if not student_ids:
            messages.error(request, "❌ Hech bo‘lmaganda bitta o‘quvchi tanlang!")
            return redirect("education:add_student_to_group", pk=g.id)

        qoshilganlar = []
        mavjudlar = []

        for sid in student_ids:
            student = get_object_or_404(User, pk=sid, role="student")

            # Agar bu guruhda bo‘lsa
            if Enrollment.objects.filter(group=g, student=student).exists():
                mavjudlar.append(f"{student.ism} {student.familya}")
                continue

            # ❗ KURS NARXNI STUDENTNING O‘ZIDAN OLAMIZ
            existing_enrollment = Enrollment.objects.filter(student=student).first()
            kurs_narhi = existing_enrollment.kurs_narhi if existing_enrollment else 0

            Enrollment.objects.create(
                group=g,
                student=student,
                kurs_narhi=kurs_narhi,
                oqituvchi_foiz=g.oqituvchi.oqituvchi_foizi,
            )

            qoshilganlar.append(f"{student.ism} {student.familya}")

        if qoshilganlar:
            messages.success(request, f"✅ {len(qoshilganlar)} ta o‘quvchi guruhga qo‘shildi!")

        if mavjudlar:
            messages.warning(request, "⚠️ Allaqachon guruhda bor: " + ", ".join(mavjudlar))

        return redirect("education:group_detail", pk=g.id)

    return render(request, "education/add_student_to_group.html", {
        "g": g,
        "students": students
    })



@login_required
def teacher_groups_view(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id, role="teacher")

    groups = (
        teacher.group_set
        .prefetch_related('enrollments__student')
        .all()
    )

    teacher_data = []
    for group in groups:
        enrollments = group.enrollments.all()
        group_income = sum([enr.real_oqituvchi_daromadi() for enr in enrollments])
        group_info = {
            'name': group.name,
            'students': enrollments,
            'foiz': enrollments.first().oqituvchi_foiz if enrollments.exists() else 0,
            'daromad': group_income,
        }
        teacher_data.append(group_info)

    ctx = {
        "teacher": teacher,
        "teacher_data": teacher_data,
    }
    return render(request, "education/teacher_groups.html", ctx)


@require_POST
def toggle_attendance(request):
    student_id = request.POST.get("student_id")
    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    if not (student_id and group_id):
        return JsonResponse({"error": "Invalid data"}, status=400)

    date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()

    att, created = Attendance.objects.get_or_create(
        group_id=group_id,
        student_id=student_id,
        date=date,
        defaults={"teacher": request.user}
    )

    # Belgini o‘zgartiramiz (agar bor bo‘lsa)
    att.present = not att.present
    att.teacher = request.user
    att.save()

    return JsonResponse({
        "success": True,
        "present": att.present,
        "date": att.date.strftime("%Y-%m-%d"),
    })




# ---------- A'zolik va o'qituvchi sahifasi ----------
@login_required
def enrollment_remove(request, pk):
    enr = get_object_or_404(Enrollment.objects.select_related("group", "student"), pk=pk)
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:group_detail", pk=enr.group_id)
    if request.method == "POST":
        enr.delete()
        messages.success(request, "O‘quvchi guruhdan chiqarildi.")
    return redirect("education:group_detail", pk=enr.group_id)


@login_required
def my_groups(request):
    rows = (
        Group.objects.filter(oqituvchi=request.user)
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(request, "education/my_groups.html", {"rows": rows})
