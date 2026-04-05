from __future__ import annotations

import calendar
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
# from multiprocessing import Value 
from django.db import models

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Count, F, Min, Max, Prefetch, Q, Sum, OuterRef, Subquery
)
from django.db.models.functions import Coalesce, TruncMonth, Cast
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import localdate, make_aware
from django.views.decorators.http import require_POST, require_http_methods
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from education.services.tuition import (
    parse_month_str,
    month_first_day,
    ensure_tuition_month,
    get_month_paid,
    tuition_month_fee_field,
    tuition_month_fee,
    ensure_all_tuition_months_since_start,
    create_payment_and_allocate,
    update_payment_and_reallocate,
    _allocate_amount_forward,
    sync_tuition_fee,
)


from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

from accounts.models import User
from chaqmoq.models import Ledger, Rule
from .forms import GroupForm, ITGroupForm, LangGroupForm
from .models import (
    Attendance,
    Category,
    DailyLightningRecord,
    Dars,
    Enrollment,
    Group,
    OylikHisobot,
    Payment,
    PaymentAllocation,
    Student,
    TuitionMonth,
    StudentGroupHistory,
    FinancialMonth,
    MonthlyFinanceSnapshot,
    TeacherSalarySnapshot,
    TeacherIncome,
)
from education.services.historical_finance_service import HistoricalFinanceService
from education.services.enrollment_service import EnrollmentService
from accounts.models import Center
from .permissions import user_can_manage_payments
from django.db import transaction
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractDay  # student_detail dagi underline ham yo'qoladi
from urllib.parse import urlparse, parse_qs
from django.db import transaction
from urllib.parse import urlparse, parse_qs, unquote
from django.urls import reverse  # sizda reverse ishlatyapsiz, import yo'q
from django.db import transaction
from django.db.models import Sum, F, Value as DJValue
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from decimal import Decimal

U = get_user_model()

DAILY_LIMIT = 50  # (hozircha ishlatilmayapti, lekin qoldirdim)


def _day_range(d):
    start = make_aware(datetime.combine(d, datetime.min.time()))
    end = make_aware(datetime.combine(d + timedelta(days=1), datetime.min.time()))
    return start, end


def _accumulate_daily_lightning(*, group, student, date_value, points_delta):
    record, _ = DailyLightningRecord.objects.get_or_create(
        group=group,
        student=student,
        date=date_value,
        defaults={
            "center": getattr(group, "center", None),
            "plus_points": 0,
            "minus_points": 0,
        },
    )
    if points_delta > 0:
        record.plus_points = int(record.plus_points or 0) + int(points_delta)
    elif points_delta < 0:
        record.minus_points = int(record.minus_points or 0) + abs(int(points_delta))
    
    if not record.center_id and getattr(group, "center_id", None):
        record.center = group.center
        
    record.save(update_fields=["plus_points", "minus_points", "center", "updated_at"])
    return record


def _attendance_adjust_rule():
    """
    Davomat OFF bo'lganda, o'sha kundagi ballarni 'bekor qilish' uchun
    maxsus Rule kerak bo'ladi. (DBga 1 marta tushadi)
    """
    rule, _ = Rule.objects.get_or_create(
        nom="Davomat bekor qilindi",
        defaults={"tur": Rule.MINUS, "min_baho": 1, "max_baho": 10000},
    )
    return rule


def parse_month_yyyy_mm(s: str):
    # '2026-01' -> date(2026, 1, 1)
    try:
        y, m = s.split("-")
        y = int(y); m = int(m)
        if 1 <= m <= 12:
            return date(y, m, 1)
    except Exception:
        return None
    return None

def first_day_of_current_month():
    d = timezone.localdate()
    return date(d.year, d.month, 1)


def sync_tuition_fee(enrollment, new_fee: int):
    """
    Narx o'zgarganda: barcha TuitionMonth yozuvlarini o'chirib,
    faqat joriy oy uchun bitta yangi yozuv yaratadi.
    Narx 0 bo'lsa - TuitionMonth yaratilmaydi (qarzdorlarga tushmaydi).
    """
    from django.utils import timezone
    from education.services.tuition import tuition_month_fee_field
    fee_field = tuition_month_fee_field()
    cur_month = timezone.localdate().replace(day=1)

    # Barcha eski qarzlarni o'chiramiz
    TuitionMonth.objects.filter(enrollment=enrollment).delete()

    # Yangi narx > 0 bo'lsagina qarz yaratamiz
    if new_fee > 0:
        TuitionMonth.objects.create(
            enrollment=enrollment,
            month=cur_month,
            **{fee_field: new_fee}
        )


def _get_int(querydict, key, default=0):
    try:
        val = querydict.get(key, None)
        if val in (None, "", "None"):
            return default
        return int(val)
    except (TypeError, ValueError):
        return default

    

# ---------- Ruxsat helperlari ----------
def _can_manage(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _can_give_points(user, g: Group):
    return (
        user.is_superuser
        or user.role in ("director", "manager")
        or (user.role == "teacher" and g.oqituvchi_id == user.id)
    )

    return user.is_superuser or user.role in ("director", "manager") or (
        user.role == "teacher" and g.oqituvchi_id == user.id
    )


def get_active_center(request):
    """
    Returns the active center for the current request.
    Now fully handled by TenantMiddleware.
    """
    return getattr(request, 'center', None)



from chaqmoq.models import Ledger

from datetime import datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from chaqmoq.models import Ledger
from django.db.models import Count, Max, Q, Case, When, Value, IntegerField, F


from .models import Enrollment, TuitionMonth, PaymentAllocation





# def get_month_paid(enr: Enrollment, month: date) -> int:
#     month = month_first_day(month)
#     tm = TuitionMonth.objects.filter(enrollment=enr, month=month).first()
#     if not tm:
#         return 0
#     s = PaymentAllocation.objects.filter(tuition_month=tm).aggregate(x=Sum("amount"))["x"] or 0
#     return int(s)


def parse_month_str(s: str) -> date | None:
    """
    'YYYY-MM' -> date(YYYY, MM, 1)
    """
    if not s:
        return None
    s = s.strip()
    if len(s) != 7 or s[4] != "-":
        return None
    try:
        y = int(s[:4])
        m = int(s[5:7])
        if m < 1 or m > 12:
            return None
        return date(y, m, 1)
    except Exception:
        return None

# def user_can_manage_payments(user) -> bool:
#     # sizda role bor: manager/director
#     return user.is_superuser or getattr(user, "role", None) in ("manager", "director")


from urllib.parse import urlparse, parse_qs


def _get_month_from_next(next_url: str, fallback: date) -> date:
    try:
        qs = parse_qs(urlparse(next_url).query)

        # 1) eng to'g'risi: month=YYYY-MM
        m = (qs.get("month", [""])[0] or "").strip()
        if m:
            return parse_month_str(m) or fallback

        # 2) sizda ishlayotgan variant: pay_month=1..12
        pm = (qs.get("pay_month", [""])[0] or "").strip()
        if pm.isdigit():
            mm = int(pm)
            if 1 <= mm <= 12:
                # year bo'lmasa joriy yil
                yy = (qs.get("year", [""])[0] or "").strip()
                yy = int(yy) if yy.isdigit() else fallback.year
                return date(yy, mm, 1)

        return fallback
    except Exception:
        return fallback


from django.core.paginator import Paginator





def _can_manage(u: User) -> bool:
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _teacher_can(user: User, g: Group) -> bool:
    return (
        user.is_superuser
        or getattr(user, "role", None) in ("director", "manager")
        or (getattr(user, "role", None) == "teacher" and getattr(g, "oqituvchi_id", None) == user.id)
    )


def _can_give_points(user: User, g: Group) -> bool:
    return _teacher_can(user, g)


# ============================================================
#  TUITION (OYLIK) HELPERS
# ============================================================

def month_first_day(d: date) -> date:
    return d.replace(day=1)


# def parse_month_str(month_str: str) -> date:
#     # "2026-01" -> 2026-01-01
#     if not month_str:
#         return month_first_day(timezone.localdate())
#     try:
#         y, m = month_str.split("-")
#         return date(int(y), int(m), 1)
#     except Exception:
#         return month_first_day(timezone.localdate())


# def _get_fee_amount(enr: Enrollment) -> int:
#     # Enrollment kurs_narhi -> Group kurs_narxi/kurs_narhi fallback
#     enr_fee = getattr(enr, "kurs_narhi", None)
#     if enr_fee:
#         return int(enr_fee)
#     g = getattr(enr, "group", None)
#     if not g:
#         return 0
#     return int(getattr(g, "kurs_narxi", 0) or getattr(g, "kurs_narhi", 0) or 0)


# def ensure_tuition_month(enr: Enrollment, month: date) -> TuitionMonth:
#     month = month_first_day(month)
#     fee = _get_fee_amount(enr)

#     tm, _ = TuitionMonth.objects.get_or_create(
#         enrollment=enr,
#         month=month,
#         defaults={"fee_amount": fee},
#     )

#     # fee 0 bo'lib qolsa fallback
#     if not getattr(tm, "fee_amount", 0):
#         tm.fee_amount = fee
#         tm.save(update_fields=["fee_amount"])
#     return tm


def get_month_paid(enr: Enrollment, month: date) -> int:
    month = month_first_day(month)
    tm = TuitionMonth.objects.filter(enrollment=enr, month=month).first()
    if not tm:
        return 0
    s = PaymentAllocation.objects.filter(tuition_month=tm).aggregate(x=Sum("amount"))["x"] or 0
    return int(s)


def _add_month(d: date, n: int = 1) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def _model_has_field(model, field_name: str) -> bool:
    return any(f.name == field_name for f in model._meta.get_fields())

# def create_payment_and_allocate(
#     enrollment: Enrollment,
#     cash_amount: int,
#     card_amount_som: int,
#     created_by: User | None,
#     start_month: date | None = None,
# ) -> Payment:
#     """
#     Payment yaratadi va pullarni TuitionMonth'larga ketma-ket taqsimlaydi:
#     start_month -> keyingi oylar...
#     """
#     start_month = month_first_day(start_month or timezone.localdate())
#     total = int(cash_amount or 0) + int(card_amount_som or 0)

#     if total <= 0:
#         raise ValueError("To'lov summasi 0 bo'lishi mumkin emas.")

#     # Payment create (fieldlar turlicha bo'lishi mumkin)
#     kwargs = {}
#     if _model_has_field(Payment, "enrollment"):
#         kwargs["enrollment"] = enrollment
#     if _model_has_field(Payment, "student"):
#         kwargs["student"] = enrollment.student
#     if _model_has_field(Payment, "group"):
#         kwargs["group"] = enrollment.group

#     if _model_has_field(Payment, "cash_amount"):
#         kwargs["cash_amount"] = int(cash_amount or 0)

#     # kartani ba'zi loyihalarda card_amount_som, ba'zida card_amount
#     if _model_has_field(Payment, "card_amount_som"):
#         kwargs["card_amount_som"] = int(card_amount_som or 0)
#     elif _model_has_field(Payment, "card_amount"):
#         kwargs["card_amount"] = int(card_amount_som or 0)

#     if _model_has_field(Payment, "summa"):
#         kwargs["summa"] = total

#     if _model_has_field(Payment, "paid_at"):
#         kwargs["paid_at"] = timezone.now()
#     else:
#         # eski fieldlar bo'lsa
#         if _model_has_field(Payment, "sana"):
#             kwargs["sana"] = timezone.localdate()
#         if _model_has_field(Payment, "vaqt"):
#             kwargs["vaqt"] = timezone.localtime().time()

#     if created_by and _model_has_field(Payment, "created_by"):
#         kwargs["created_by"] = created_by

#     p = Payment.objects.create(**kwargs)

#     # Allocation: start_month dan boshlab ketma-ket oylar
#     left = total
#     cur = start_month

#     # 60 oy max (cheksiz loop bo'lmasin)
#     for _ in range(60):
#         tm = ensure_tuition_month(enrollment, cur)
#         fee = int(getattr(tm, "fee_amount", 0) or 0)

#         # fee 0 bo'lsa — keyingi oyga o'tamiz
#         if fee <= 0:
#             cur = _add_month(cur, 1)
#             continue

#         paid = get_month_paid(enrollment, cur)
#         need = max(0, fee - paid)
#         if need <= 0:
#             cur = _add_month(cur, 1)
#             continue

#         alloc = min(need, left)
#         if alloc > 0:
#             PaymentAllocation.objects.create(payment=p, tuition_month=tm, amount=alloc)
#             left -= alloc

#         if left <= 0:
#             break

#         cur = _add_month(cur, 1)

#     # Enrollment jami_tolangan update (agar field bo'lsa)
#     if _model_has_field(Enrollment, "jami_tolangan"):
#         Enrollment.objects.filter(pk=enrollment.pk).update(
#             jami_tolangan=Coalesce(F("jami_tolangan"), 0) + total
#         )

#     return p

@require_POST
@login_required
def create_payment(request):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("education:tolovlar_home")

    next_url = request.POST.get("next") or "education:tolovlar_home"
    
    enrollment_id = request.POST.get("enrollment_id")
    student_id = request.POST.get("student_id")
    month_str = request.POST.get("month")

    fallback = first_day_of_current_month()
    start_month = parse_month_str(month_str) if month_str else _get_month_from_next(next_url, fallback)
    
    cash_amount = int(Decimal(request.POST.get("cash_amount") or "0"))
    card_amount = int(Decimal(request.POST.get("card_amount") or "0"))
    note = (request.POST.get("note") or "").strip()

    if not enrollment_id and not student_id:
        messages.error(request, "ID kelmadi.")
        return redirect(next_url)

    center = get_active_center(request)

    if enrollment_id:
        qs = Enrollment.objects.all()
        if center: qs = qs.filter(center=center)
        enrollment = get_object_or_404(qs, id=enrollment_id)
        
        try:
            with transaction.atomic():
                create_payment_and_allocate(
                    enrollment=enrollment,
                    cash_amount=cash_amount,
                    card_amount_som=card_amount,
                    created_by=request.user,
                    start_month=start_month,
                    note=note,
                )
            messages.success(request, f"✅ {enrollment.student.get_full_name()} uchun to'lov saqlandi!")
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {e}")
            
    elif student_id:
        # ✅ CONSOLIDATED DISTRIBUTION LOGIC
        user_qs = User.objects.filter(role="student")
        if center: user_qs = user_qs.filter(center=center)
        student = get_object_or_404(user_qs, id=student_id)
        
        # ✅ ONLY Active and NOT ARCHIVED groups
        enrollments = Enrollment.objects.filter(student=student, is_active=True, group__is_archived=False).order_by('id')
        if not enrollments.exists():
            messages.error(request, "O'quvchida faol kurslar topilmadi.")
            return redirect(next_url)
            
        try:
            with transaction.atomic():
                # One check for the whole payment
                first_group = enrollments[0].group if enrollments else None
                main_payment = Payment.objects.create(
                    student=student,
                    group=first_group,
                    cash_amount=cash_amount,
                    card_amount=card_amount,
                    summa=cash_amount + card_amount,
                    created_by=request.user,
                    paid_date=localdate(),
                    center=center,
                    note=note,
                    payment_type="mixed" if (cash_amount > 0 and card_amount > 0) else ("card" if card_amount > 0 else "cash")
                )

                remaining_sum = cash_amount + card_amount
                
                # 1. First, pay off current month debts for all active enrollments
                for e in enrollments:
                    if remaining_sum <= 0: break
                    
                    tm = ensure_tuition_month(e, start_month)
                    fee = int(getattr(tm, "fee_amount", 0) or 0)
                    paid = int(get_month_paid(e, start_month) or 0)
                    debt = max(0, fee - paid)
                    
                    if debt > 0:
                        take = min(remaining_sum, debt)
                        _allocate_amount_forward(
                            enrollment=e,
                            payment=main_payment,
                            amount=take,
                            start_month=start_month
                        )
                        remaining_sum -= take
                
                # 2. If money still remains, apply it to the first enrollment (forward allocation)
                if remaining_sum > 0:
                    _allocate_amount_forward(
                        enrollment=enrollments[0],
                        payment=main_payment,
                        amount=remaining_sum,
                        start_month=start_month
                    )
            
            messages.success(request, f"✅ {student.get_full_name()} uchun umumiy to'lov saqlandi!")
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {e}")

    return redirect(next_url)


from decimal import Decimal, InvalidOperation
from django.db.models import Sum, F, Value


@require_POST
@login_required
def payment_update(request, payment_id: int):
    if not user_can_manage_payments(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    # from core.tenant import get_request_center
    center = get_active_center(request)
    qs = Payment.objects.select_related("enrollment")
    if center:
        qs = qs.filter(center=center)

    p = get_object_or_404(qs, id=payment_id)
    enrollment = getattr(p, "enrollment", None)
    if not enrollment:
        return JsonResponse({"ok": False, "error": "enrollment_not_found"}, status=400)

    old_total = int(getattr(p, "summa", 0) or 0)

    cash_raw = request.POST.get("cash_amount")
    card_raw = request.POST.get("card_amount")
    paid_date_raw = request.POST.get("paid_date")

    if cash_raw is None and card_raw is None and paid_date_raw is None:
        note = request.POST.get("note")
        if note is not None:
            p.note = note.strip()   # bo'sh bo'lsa ham "" bo'lib saqlanadi
            p.save(update_fields=["note"])
        return JsonResponse({"ok": True, "payment_id": p.id, "note": p.note or ""})

    from decimal import Decimal, InvalidOperation
    try:
        cash_amount = int(Decimal((request.POST.get("cash_amount") or "0").strip()))
        card_amount = int(Decimal((request.POST.get("card_amount") or "0").strip()))
    except (InvalidOperation, ValueError):
        return JsonResponse({"ok": False, "error": "summa_notogri"}, status=400)

    if cash_amount < 0 or card_amount < 0:
        return JsonResponse({"ok": False, "error": "summa_manfiy_bolmaydi"}, status=400)

    new_total = cash_amount + card_amount
    if new_total < 0:
        return JsonResponse({"ok": False, "error": "summa_manfiy_bolmaydi"}, status=400)

    month_str = (request.POST.get("month") or "").strip()
    start_month = parse_month_str(month_str) if month_str else None

    # Update metadata
    note = request.POST.get("note")
    if note is not None:
        p.note = note.strip()
    
    paid_date_str = request.POST.get("paid_date")
    if paid_date_str:
        try:
            p.paid_date = parse_date(paid_date_str)
        except Exception:
            pass
            
    p.save()

    try:
        update_payment_and_reallocate(
            payment=p,
            cash_amount=cash_amount,
            card_amount_som=card_amount,
            start_month=start_month,
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return JsonResponse({
        "ok": True,
        "payment_id": p.id,
        "old_total": old_total,
        "new_total": new_total,
        "delta": new_total - old_total,
        "start_month": (start_month or timezone.localdate().replace(day=1)).strftime("%Y-%m"),
    })


def month_start(d: date) -> date:
    return d.replace(day=1)

def parse_month_str_safe(s: str) -> date:
    """
    'YYYY-MM' -> date(YYYY,MM,1)
    bo'sh yoki xato bo'lsa -> joriy oy(1-kun)
    """
    s = (s or "").strip()
    today = timezone.localdate()
    if len(s) == 7 and s[4] == "-":
        try:
            y = int(s[:4])
            m = int(s[5:])
            return date(y, m, 1)
        except Exception:
            pass
    return month_start(today)

def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_yyyy_mm(s: str):
    """
    '2026-01' -> date(2026,1,1)
    None/invalid -> current month first day
    """
    s = (s or "").strip()
    try:
        y = int(s[:4])
        m = int(s[5:7])
        if m < 1 or m > 12:
            raise ValueError()
        return timezone.datetime(y, m, 1).date()
    except Exception:
        now = timezone.localdate()
        return timezone.datetime(now.year, now.month, 1).date()


def _first_day_of_month(d: date) -> date:
    return d.replace(day=1)


@transaction.atomic
def enrollment_edit(request, enrollment_id):
    # from core.tenant import get_request_center
    center = get_active_center(request)
    qs = Enrollment.objects.select_related("student", "group")
    if center:
        qs = qs.filter(center=center)
        
    enr = get_object_or_404(qs, id=enrollment_id)
    
    groups = Group.objects.all()
    if center:
        groups = groups.filter(center=center)

    next_url = request.POST.get("next") or request.GET.get("next") or reverse("education:qarzdorlar_home")

    # month string: ?month=2026-01
    month_str = (request.GET.get("month") or request.POST.get("month") or "").strip()
    start_month = parse_month_yyyy_mm(month_str) or first_day_of_current_month()

    if request.method == "POST":
        old_price = int(enr.kurs_narhi or 0)

        # --- student update ---
        enr.student.ism = request.POST.get("ism", "").strip()
        enr.student.familya = request.POST.get("familya", "").strip()
        enr.student.email = request.POST.get("email", "").strip()
        enr.student.save(update_fields=["ism", "familya", "email"])

        # --- group update ---
        gid = request.POST.get("group_id")
        old_group_id = enr.group_id
        if gid:
            enr.group_id = int(gid)

        # --- enrollment fields ---
        new_price = int(request.POST.get("kurs_narhi") or 0)
        enr.kurs_narhi = new_price

        oqf = request.POST.get("oqituvchi_foiz")
        
        # O'quvchi boshqa guruhga o'tkazilganda avtomatik yangi guruhning foizini oladi
        if gid and int(gid) != old_group_id:
            new_group = Group.objects.filter(id=int(gid)).first()
            if new_group:
                enr.oqituvchi_foiz = new_group.oqituvchi_foiz
                # Agar kurs narxini ham avto o'zgartirish kerak bo'lsa (lekin formadan kegan price eski bo'lsa)
                # Odatda o'quvchi o'zining eski narxida qolishi yoki yangi narxga o'tishi mumkin,
                # lekin foydalanuvchi qatiy ravishda "foiz (40%) ga tushmayapti" degan. 
                # Shuning uchun foizni yangilaymiz:
        else:
            if oqf is not None and str(oqf).strip() != "":
                enr.oqituvchi_foiz = int(oqf)

        enr.save()

        # ✅ MUHIM: Narx o'zgagan bo'lsa yoki o'zgarmasada TuitionMonth'ni yangilaymiz
        # Bu eski 50M kabi noto'g'ri qarzlarni ham to'g'irlaydi
        sync_tuition_fee(enr, new_price)

        messages.success(request, "O'quvchi ma'lumotlari muvaffaqiyatli yangilandi!")
        return redirect(next_url)

    return render(request, "education/enrollment_edit.html", {
        "enr": enr,
        "groups": groups,
        "next": next_url,
        "month": month_str,   # ✅ template uchun
    })

@login_required
@require_http_methods(["GET", "POST"])
def enrollment_delete(request, enrollment_id: int):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("core:home")

    # from core.tenant import get_request_center
    center = get_active_center(request)
    qs = Enrollment.objects.select_related("student", "group")
    if center:
        qs = qs.filter(center=center)

    enr = get_object_or_404(qs, id=enrollment_id)
    next_url = request.GET.get("next") or request.POST.get("next") or "education:tolovlar_home"

    if request.method == "POST":
        student_name = f"{enr.student.ism} {enr.student.familya}"
        group_name = getattr(enr.group, "nom", "")
        enr.delete(deleted_by=request.user)
        messages.success(request, f"🗑️ {student_name} ({group_name}) guruhdan o'chirildi.")
        return redirect(next_url)

    return render(request, "education/enrollment_delete_confirm.html", {"enr": enr, "next": next_url})



 


@login_required
def payment_history_enrollment(request, enrollment_id: int):
    if not user_can_manage_payments(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)

    today = timezone.localdate()
    cur_month = today.replace(day=1)
    
    month_str = request.GET.get("month", "")
    selected_month = parse_month_str(month_str) or cur_month

    center = get_active_center(request)
    qs = Enrollment.objects.select_related("student", "group")
    if center:
        qs = qs.filter(center=center)

    enrollment = get_object_or_404(qs, id=enrollment_id)
    fee_field = tuition_month_fee_field()

    # 1. Summary Data (up to today)
    ensure_tuition_month(enrollment, cur_month)
    tms_summary = TuitionMonth.objects.filter(enrollment=enrollment, month__lte=cur_month)
    agg_summary = tms_summary.aggregate(
        total_fee=Coalesce(Sum(fee_field), 0),
        total_paid=Coalesce(Sum("allocations__amount"), 0)
    )
    total_fee_needed = agg_summary["total_fee"] or 0
    total_paid_so_far = agg_summary["total_paid"] or 0
    overall_debt = total_fee_needed - total_paid_so_far

    # 2. Monthly Breakdown (All months including future if they have allocations)
    breakdown = []
    # Get all tuition months for this enrollment
    all_tms = TuitionMonth.objects.filter(enrollment=enrollment).order_by("month")
    
    for tm in all_tms:
        tm_fee = getattr(tm, fee_field, 0) or 0
        tm_paid = tm.allocations.aggregate(s=Sum("amount"))["s"] or 0
        tm_debt = max(0, tm_fee - tm_paid)
        
        breakdown.append({
            "month": tm.month.strftime("%Y-%m"),
            "fee": tm_fee,
            "paid": tm_paid,
            "debt": tm_debt,
            "is_future": tm.month > cur_month
        })

    # 3. Specific payments history
    payments_qs = Payment.objects.filter(enrollment=enrollment).order_by("-id")
    payments = []
    for p in payments_qs:
        allocations = []
        for a in p.allocations.select_related("tuition_month").all():
            allocations.append({
                "month": a.tuition_month.month.strftime("%Y-%m"),
                "amount": int(a.amount or 0),
            })

        # paid_at robust check
        paid_at_dt = getattr(p, "paid_at", None) or p.created_at
        if not paid_at_dt:
            sana = getattr(p, "sana", None)
            vaqt = getattr(p, "vaqt", None)
            if sana:
                dt = datetime.combine(sana, vaqt or datetime.min.time())
                paid_at_dt = timezone.make_aware(dt)
            else:
                paid_at_dt = timezone.now()

        cash = int(getattr(p, "cash_amount", 0) or 0)
        card = int(getattr(p, "card_amount_som", 0) or getattr(p, "card_amount", 0) or 0)
        total = int(getattr(p, "summa", 0) or (cash + card))

        payments.append({
            "id": p.id,
            "paid_at": timezone.localtime(paid_at_dt).strftime("%d.%m.%Y %H:%M"),
            "cash": cash,
            "card": card,
            "total": total,
            "allocations": allocations,
            "receipt_url": reverse("education:payment_receipt_pdf", args=[p.id]),
        })

    return JsonResponse({
        "student": enrollment.student.get_full_name(),
        "group": enrollment.group.nom,
        "monthly_fee": enrollment.kurs_narhi,
        "total_fee_needed": total_fee_needed,
        "total_paid_so_far": total_paid_so_far,
        "overall_debt": overall_debt,
        "breakdown": breakdown,
        "payments": payments,
    })



from django.db.models import Sum
from datetime import date



# --------- helpers (shu fayl ichida bo'lsa sariq bo'lmaydi) ----------
def _model_has_field(model_cls, field_name: str) -> bool:
    return any(f.name == field_name for f in model_cls._meta.get_fields())


def _get_fee_amount(enrollment) -> int:
    """
    fee manbasi:
    - enrollment.kurs_narhi (eng ustun)
    - group.kurs_narxi yoki group.kurs_narhi (fallback)
    """
    if not enrollment:
        return 0

    enr_fee = getattr(enrollment, "kurs_narhi", None)
    if enr_fee not in (None, ""):
        return int(enr_fee or 0)

    g = getattr(enrollment, "group", None)
    if not g:
        return 0

    return int(getattr(g, "kurs_narxi", 0) or getattr(g, "kurs_narhi", 0) or 0)


def _parse_month_str(s: str):
    try:
        if not s or len(s) < 7:
            return None
        y = int(s[:4])
        m = int(s[5:7])
        if m < 1 or m > 12:
            return None
        return date(y, m, 1)
    except Exception:
        return None

def _fmt(n: int) -> str:
    return f"{int(n or 0):,}".replace(",", " ")


def _ellipsis(text: str, limit: int = 34) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


@login_required
def payment_receipt_pdf(request, payment_id: int):
    if not user_can_manage_payments(request.user):
        return HttpResponse("Forbidden", status=403)

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Payment.objects.select_related("enrollment__student", "enrollment__group")
    if center:
        qs = qs.filter(center=center)

    p = get_object_or_404(
        qs,
        id=payment_id
    )

    enrollment = getattr(p, "enrollment", None)
    student = getattr(enrollment, "student", None)
    group = getattr(enrollment, "group", None)

    cash = int(getattr(p, "cash_amount", 0) or 0)
    card_som = int(getattr(p, "card_amount_som", 0) or getattr(p, "card_amount", 0) or 0)
    total = int(getattr(p, "summa", 0) or (cash + card_som))

    # ✅ Sana/vaqt (soat)
    paid_at = getattr(p, "paid_at", None)
    if paid_at:
        paid_at = timezone.localtime(paid_at)
    else:
        sana = getattr(p, "sana", None)
        vaqt = getattr(p, "vaqt", None)
        if sana and vaqt:
            try:
                dt = datetime.combine(sana, vaqt)
                paid_at = timezone.localtime(timezone.make_aware(dt))
            except Exception:
                paid_at = timezone.localtime(timezone.now())
        else:
            paid_at = timezone.localtime(timezone.now())

    dt_text = paid_at.strftime("%d.%m.%Y %H:%M")

    # ==== Tanlangan oy bo'yicha qarz hisoblash (month=YYYY-MM) ====
    fee_field = "fee_amount"

    month_qs = request.GET.get("month")  # masalan: 2026-01
    month_date = _parse_month_str(month_qs)

    fee_for_month = None
    paid_for_month = None
    debt_for_month = None

    if enrollment and month_date:
        tm, _ = TuitionMonth.objects.get_or_create(
            enrollment=enrollment,
            month=month_date,
            defaults={fee_field: _get_fee_amount(enrollment)}
        )

        # agar fee 0 bo'lib qolgan bo'lsa, fallback bilan yangilab qo'yamiz
        cur_fee = int(getattr(tm, fee_field, 0) or 0)
        if cur_fee <= 0:
            new_fee = _get_fee_amount(enrollment)
            if new_fee > 0:
                setattr(tm, fee_field, int(new_fee))
                tm.save(update_fields=[fee_field])
                cur_fee = new_fee

        fee_for_month = int(cur_fee or 0)
        paid_for_month = int(
            PaymentAllocation.objects.filter(tuition_month=tm).aggregate(s=Sum("amount"))["s"] or 0
        )
        debt_for_month = max(0, fee_for_month - paid_for_month)

    # allocations (shu payment bo'yicha)
    alloc_mgr = getattr(p, "allocations", None)
    allocations = list(alloc_mgr.select_related("tuition_month").all()) if alloc_mgr is not None else []

    # To'lov turi
    if cash > 0 and card_som > 0:
        pay_type = "Aralash (Naqd + Karta)"
    elif card_som > 0:
        pay_type = "Kartaga o'tkazma"
    else:
        pay_type = "Naqd to'lov"

    student_name = f"{getattr(student, 'ism', '')} {getattr(student, 'familya', '')}".strip() or "-"
    group_name = getattr(group, "nom", "") or "-"

    student_name = _ellipsis(student_name, 38)
    group_name = _ellipsis(group_name, 38)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    # =========================
    #  CHEK KARTA (markazda)
    # =========================
    card_w = 175 * mm
    card_h = 240 * mm
    x = (W - card_w) / 2
    y = (H - card_h) / 2

    # oq fon
    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # shadow (alpha bo'lsa ishlatamiz, bo'lmasa ham muammo yo'q)
    try:
        c.setFillAlpha(0.08)
    except Exception:
        pass
    c.setFillColor(colors.black)
    c.roundRect(x + 2*mm, y - 2*mm, card_w, card_h, 14, stroke=0, fill=1)
    try:
        c.setFillAlpha(1)
    except Exception:
        pass

    # card body
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setLineWidth(1)
    c.roundRect(x, y, card_w, card_h, 14, stroke=1, fill=1)

    # Header (yorqin yashil)
    header_h = 34 * mm
    c.setFillColor(colors.HexColor("#16A34A"))
    c.roundRect(x, y + card_h - header_h, card_w, header_h, 14, stroke=0, fill=1)

    # Header text
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x + 12*mm, y + card_h - 18*mm, "ChaqmoqApp")
    c.setFont("Helvetica", 10)
    c.drawRightString(x + card_w - 12*mm, y + card_h - 18*mm, "TO'LOV CHEKI")

    # Big amount
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(x + card_w/2, y + card_h - 60*mm, f"{_fmt(total)} so'm")

    # Success badge
    badge_w = 70 * mm
    badge_h = 10 * mm
    bx = x + (card_w - badge_w) / 2
    by = y + card_h - 74*mm
    c.setFillColor(colors.HexColor("#22C55E"))
    c.roundRect(bx, by, badge_w, badge_h, 6, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(x + card_w/2, by + 3.2*mm, "Muvaffaqiyatli")

    # Divider
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setLineWidth(1)
    c.line(x + 12*mm, y + card_h - 82*mm, x + card_w - 12*mm, y + card_h - 82*mm)

    # Key-value row helper
    def row(label: str, value: str, yy: float, value_color=colors.HexColor("#111827")):
        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 10)
        c.drawString(x + 12*mm, yy, label)

        c.setFillColor(value_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(x + card_w - 12*mm, yy, value)

        c.setStrokeColor(colors.HexColor("#F1F5F9"))
        c.setLineWidth(1)
        c.line(x + 12*mm, yy - 4.5*mm, x + card_w - 12*mm, yy - 4.5*mm)

    # Row spacing (siqilganroq, hammasi sig'sin)
    GAP = 10 * mm

    teacher = getattr(group, "oqituvchi", None)
    teacher_name = teacher.get_full_name() if teacher else "-"
    teacher_name = _ellipsis(teacher_name, 38)

    yy = y + card_h - 98*mm
    row("Tranzaksiya turi:", pay_type, yy); yy -= GAP
    row("O'quvchi:", student_name, yy); yy -= GAP
    row("Guruh:", group_name, yy); yy -= GAP
    row("O'qituvchi:", teacher_name, yy); yy -= GAP
    row("Naqd:", f"{_fmt(cash)} so'm", yy); yy -= GAP
    row("Karta:", f"{_fmt(card_som)} so'm", yy); yy -= GAP
    # row("Chek ID:", f"#{p.id}", yy); yy -= GAP

    # ✅ Oylik narx + Shu oy to'langan + Qarz
    if fee_for_month is not None:
        row("Oylik narx:", f"{_fmt(fee_for_month)} so'm", yy); yy -= GAP
        row("Shu oy to'langan:", f"{_fmt(paid_for_month)} so'm", yy); yy -= GAP
        debt_color = colors.HexColor("#EF4444") if (debt_for_month or 0) > 0 else colors.HexColor("#16A34A")
        row("Qarz (qoldiq):", f"{_fmt(debt_for_month)} so'm", yy, value_color=debt_color); yy -= GAP

    row("Sana:", dt_text, yy); yy -= 12*mm

    # Allocations title
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 12*mm, yy, "Taqsimot (qaysi oylarga tushdi):")
    yy -= 8*mm

    # Allocation list (qolgan joyga qarab max line)
    c.setFont("Helvetica", 10)
    bottom_limit = y + 18*mm  # footer usti
    line_h = 7 * mm
    max_lines = max(1, int((yy - bottom_limit) / line_h) - 1)

    if not allocations:
        c.setFillColor(colors.HexColor("#6B7280"))
        c.drawString(x + 14*mm, yy, "— Allocation topilmadi")
        yy -= line_h
    else:
        c.setFillColor(colors.HexColor("#0F172A"))
        for a in allocations[:max_lines]:
            tm = getattr(a, "tuition_month", None)
            m = getattr(tm, "month", None)
            enr = getattr(tm, "enrollment", None)
            g_nom = getattr(getattr(enr, "group", None), "nom", "")[:15]
            
            m_txt = m.strftime("%Y-%m") if m else "—"
            amt_txt = _fmt(int(getattr(a, "amount", 0) or 0))
            
            prefix = f"• {g_nom} ({m_txt})" if g_nom else f"• {m_txt}"
            c.drawString(x + 14*mm, yy, f"{prefix} — {amt_txt} so'm")
            yy -= line_h

        if len(allocations) > max_lines:
            c.setFillColor(colors.HexColor("#6B7280"))
            c.drawString(x + 14*mm, yy, f"... yana {len(allocations) - max_lines} ta satr bor")
            yy -= line_h

    # Footer
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(x + card_w/2, y + 10*mm, "ChaqmoqApp • To'lov nazorati tizimi")

    c.showPage()
    c.save()

    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type="application/pdf")

    # ✅ bosganda darrov yuklab olsin
    resp["Content-Disposition"] = f'attachment; filename="proskill{p.id}.pdf"'
    return resp








@login_required
def attendance_groups(request):
    q = (request.GET.get("q") or "").strip()
    
    # If the user is a teacher, force them to only see their own groups
    is_teacher = getattr(request.user, 'role', '') == 'teacher'
    if is_teacher:
        teacher_id = request.user.id
    else:
        teacher_id = _get_int(request.GET, "teacher", 0)


    # ✅ Teacher dropdown uchun
    teacher_qs = User.objects.filter(role="teacher").order_by("ism", "familya")
    
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        teacher_qs = teacher_qs.filter(center=center)
        
    teachers = teacher_qs

    # ✅ Base queryset
    groups = (
        Group.objects.filter(is_archived=False)
        .select_related("center", "oqituvchi")
        .annotate(
            attendance_count=Count("attendances", distinct=True),
            last_attendance=Max("attendances__date"),
        )
        .annotate(
            has_attendance=Case(
                When(attendance_count__gt=0, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )
    
    if center:
        groups = groups.filter(center=center)

    # ✅ Filter: teacher
    if teacher_id:
        groups = groups.filter(oqituvchi_id=teacher_id)

    # ✅ Search
    if q:
        groups = groups.filter(
            Q(nom__icontains=q) |
            Q(center__nom__icontains=q) |
            Q(oqituvchi__ism__icontains=q) |
            Q(oqituvchi__familya__icontains=q)
        )

    # ✅ Davomat qilinganlar tepada, qilinmaganlar pastda
    # -has_attendance: bor guruhlar birinchi
    # last_attendance: oxirgi davomat sanasi eng yangi birinchi
    # nom: qolganlari nom bo'yicha
    groups = groups.order_by(
        "-has_attendance",
        F("last_attendance").desc(nulls_last=True),
        "nom"
    )

    # ✅ Statistikalar (tepada ko'rsatish uchun)
    total = groups.count()
    active_count = groups.filter(attendance_count__gt=0).count()
    inactive_count = total - active_count

    return render(request, "education/attendance_groups.html", {
        "groups": groups,
        "teachers": teachers,
        "selected_teacher": teacher_id,
        "q": q,
        "total": total,
        "active_count": active_count,
        "inactive_count": inactive_count,
    })

import calendar
from django.db.models import Min, Max

@login_required
def group_month_attendance(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    day_list = [first_day + timedelta(days=i) for i in range(days_in_month)]

    enrollments = (
        Enrollment.objects
        .filter(group=group)
        .select_related("student", "group")   # ✅ MUHIM
        .order_by("student__ism", "student__familya")
    )
    students = [e.student for e in enrollments]

    qs = Attendance.objects.filter(group=group).select_related("student")

    agg = qs.aggregate(min_date=Min("date"), max_date=Max("date"))
    if agg["min_date"] and agg["max_date"]:
        start_year = agg["min_date"].year
        end_year = agg["max_date"].year
    else:
        start_year = year - 1
        end_year = year + 1
    years = list(range(start_year, end_year + 1))


    month_qs = qs.filter(date__year=year, date__month=month)

    att_map = {(a.student_id, a.date): a for a in month_qs}

    rows = []
    for student in students:
        cells = []
        present_count = 0
        absent_count = 0
        forced_count = 0

        for d in day_list:
            a = att_map.get((student.id, d))
            if not a:
                status = "none"
            elif getattr(a, "present", False):
                status = "present"
                present_count += 1
            elif getattr(a, "status", None) == "absent_excused":
                # Sababli kelmagan — pul yozilmaydi
                status = "absent_excused"
                forced_count += 1
            elif getattr(a, "forced", False):
                # Eski "forced" yozuvlar — ko'rsatish uchun saqlanadi
                status = "forced"
                forced_count += 1
            else:
                # Sababsiz kelmagan — pul yoziladi
                status = "absent"
                absent_count += 1

            cells.append({"date": d, "status": status})

        rows.append({
            "student": student,
            "cells": cells,
            "present_count": present_count,
            "absent_count": absent_count,
            "forced_count": forced_count,
        })

    months = [(i, calendar.month_name[i]) for i in range(1, 13)]

    # Ruxsat tekshiruvi: director, manager, teacher — barchasi tahrirlashi mumkin
    user = request.user
    can_edit = (
        user.is_superuser
        or getattr(user, "role", None) in ("director", "manager", "teacher")
    )

    return render(request, "education/group_month_attendance.html", {
        "group": group,
        "rows": rows,
        "days": day_list,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "years": years,
        "months": months,
        "can_edit": can_edit,
    })


# ==========================================
#  QARZDORLAR (YOZILAYOTGAN YANGI PAGE)
# ==========================================

@login_required
def qarzdorlar_home(request):
    from core.tenant import get_request_center
    from education.services.tuition import ensure_tuition_month, month_first_day, add_month

    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("core:home")

    center = get_request_center(request)

    # ─── FILTERS ────────────────────────────────────────────────────────────
    q          = (request.GET.get("q") or "").strip()
    group_id   = _get_int(request.GET, "group", 0)
    min_debt   = _get_int(request.GET, "min_debt", 0)
    max_debt   = _get_int(request.GET, "max_debt", 0)
    end_date   = (request.GET.get("end_date") or "").strip()

    allowed_page_sizes = (10, 20, 50, 100)
    per_page_raw = (request.GET.get("per_page") or "10").strip()
    try:
        per_page = int(per_page_raw)
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in allowed_page_sizes:
        per_page = 10

    # ─── JORIY OY ANIQLASH ──────────────────────────────────────────────────
    today     = timezone.localdate()
    cur_month = today.replace(day=1)

    sel_month = request.GET.get("pay_month")
    if sel_month and sel_month.isdigit():
        m = int(sel_month)
        if 1 <= m <= 12:
            cur_month = cur_month.replace(month=m)

    fee_field = tuition_month_fee_field()

    # ─── FAOL ENROLLMENT'LAR ─────────────────────────────────────────────────
    # Faqat:  is_active=True  +  student NOT archived  +  group NOT archived
    active_enrs_qs = (
        Enrollment.objects
        .select_related("student", "group")
        .filter(is_active=True, student__is_archived=False, group__is_archived=False)
    )
    if center:
        active_enrs_qs = active_enrs_qs.filter(center=center)

    # ─── TUITIONMONTH AUTO-ENSURE (joriy oy) ────────────────────────────────
    # Har bir faol enrollment uchun JORIY OY TuitionMonth yozuvi bo'lishini
    # kafolatlaymiz. `ensure_tuition_month` soft-deleted ni tiklaydi, 0-fee ni
    # to'g'rilaydi — shuning uchun bulk_create dan ustunroq.
    for enr in active_enrs_qs:
        ensure_tuition_month(enr, cur_month)

    # ─── SUBQUERY: fee va paid (faqat TANLANGAN OY) ──────────────────────────
    total_fee_sub = (
        TuitionMonth.objects
        .filter(enrollment=OuterRef("pk"), month=cur_month)
        .values("enrollment")
        .annotate(s=Sum(fee_field))
        .values("s")
    )
    total_paid_sub = (
        PaymentAllocation.objects
        .filter(
            tuition_month__enrollment=OuterRef("pk"),
            tuition_month__month=cur_month,
        )
        .values("tuition_month__enrollment")
        .annotate(s=Sum("amount"))
        .values("s")
    )

    # ─── ENROLLMENTS (FILTER UCHUN BASE) ─────────────────────────────────────
    enrs_base = active_enrs_qs
    if group_id:
        enrs_base = enrs_base.filter(group_id=group_id)

    # ─── JAMI MARKAZ QARZ SUMMASI ────────────────────────────────────────────
    total_center_debt = (
        enrs_base
        .annotate(f=Coalesce(Subquery(total_fee_sub), 0),
                  p=Coalesce(Subquery(total_paid_sub), 0))
        .annotate(d=F("f") - F("p"))
        .filter(d__gt=0)
        .aggregate(total=Sum("d"))["total"] or 0
    )

    # ─── ANNOTATE QARZ ──────────────────────────────────────────────────────
    enrs_annotated = (
        enrs_base
        .annotate(f=Coalesce(Subquery(total_fee_sub), 0),
                  p=Coalesce(Subquery(total_paid_sub), 0))
        .annotate(calculated_debt=F("f") - F("p"))
    )

    # ─── STUDENT MAP (student bo'yicha guruhlash) ────────────────────────────
    graph_map   = {m: 0 for m in range(1, 13)}
    student_map = {}   # {student_id: row_dict}

    for e in enrs_annotated:
        sid  = e.student_id
        debt = int(e.calculated_debt or 0)
        f    = int(e.f or 0)
        p    = int(e.p or 0)

        if sid not in student_map:
            student_map[sid] = {
                "student":     e.student,
                "group_names": [],
                "total_fee":   0,
                "total_paid":  0,
                "debt":        0,
                "enrollment":  e,
                "group":       e.group,
                "staff":       getattr(e.group, "oqituvchi", None),
            }

        row = student_map[sid]
        row["total_fee"]  += f
        row["total_paid"] += p
        row["debt"]       += debt

        if e.group:
            gnom = getattr(e.group, "nom", "")
            if gnom and gnom not in row["group_names"]:
                row["group_names"].append(gnom)

        # Grafik: enrollment oy bo'yicha
        try:
            m_idx = e.created_at.month if e.created_at else today.month
        except Exception:
            m_idx = today.month
        if m_idx in graph_map and debt > 0:
            graph_map[m_idx] += debt

    # ─── GROUP LABEL ─────────────────────────────────────────────────────────
    for r in student_map.values():
        r["group_label"] = ", ".join(r["group_names"]) if r["group_names"] else "—"

    # ─── QIDIRUV: ism/familya/telefon bo'yicha ───────────────────────────────
    all_rows = list(student_map.values())
    if q:
        ql = q.lower()
        all_rows = [
            r for r in all_rows
            if ql in (r["student"].ism or "").lower()
            or ql in (r["student"].familya or "").lower()
            or ql in (r["student"].telefon1 or "").lower()
            or ql in (r["student"].telefon2 or "").lower()
        ]

    # ─── STATISTIKA ──────────────────────────────────────────────────────────
    debtors_count  = 0
    paid_count     = 0
    no_group_count = 0
    debtor_rows    = []

    for r in all_rows:
        if not r["group_names"]:
            no_group_count += 1
            continue
        if r["debt"] > 0:
            # Min/Max qarz filterlari
            if min_debt and r["debt"] < min_debt:
                continue
            if max_debt and r["debt"] > max_debt:
                continue
            debtors_count += 1
            debtor_rows.append(r)
        else:
            paid_count += 1
            # To'lov qilganlar → qarzdorlar ro'yxatiga kirmaydi
            # Ular "To'lovlar" bo'limida ko'rinadi

    display_rows = debtor_rows

    filtered_debt   = sum(r["debt"] for r in display_rows)
    chart_series    = [graph_map[m] for m in range(1, 13)]

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
        "q":              q,
        "min_debt":       min_debt if min_debt else "",
        "max_debt":       max_debt if max_debt else "",
        "end_date":       end_date,
        "pay_month":      sel_month,
        "per_page":       per_page,
        "page_size_options": allowed_page_sizes,
        "uz_months": [
            (1, "Yanvar"),   (2, "Fevral"),   (3, "Mart"),    (4, "Aprel"),
            (5, "May"),      (6, "Iyun"),     (7, "Iyul"),    (8, "Avgust"),
            (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
        ],
        "stats_summary": {
            "total":    len(all_rows),
            "debtors":  debtors_count,
            "paid":     paid_count,
            "no_group": no_group_count,
        },
    }

    return render(request, "education/qarzdorlar.html", context)
    
import csv
from django.http import HttpResponse
from datetime import date, timedelta
import calendar


@login_required
def group_month_attendance_export(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    day_list = [first_day + timedelta(days=i) for i in range(days_in_month)]

    enrollments = (
        Enrollment.objects
        .filter(group=group)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    students = [e.student for e in enrollments]

    month_qs = (Attendance.objects
                .filter(group=group, date__year=year, date__month=month)
                .select_related("student"))

    att_map = {(a.student_id, a.date): a for a in month_qs}

    # ✅ Excel uchun UTF-8 BOM
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    safe_group_name = "".join(ch for ch in (group.nom or "") if ch.isalnum() or ch in ("-", "_", " "))
    safe_group_name = safe_group_name.strip() or f"group-{group.id}"
    filename = f"{safe_group_name}_{year}-{month:02d}_attendance.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    # ✅ MUHIM: delimiter=';' (Excel RU/UZ)
    writer = csv.writer(response, delimiter=';', lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

    def _csv_safe(value):
        text = "" if value is None else str(value)
        if text.startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text

    header = ["O'quvchi"] + [d.strftime("%d-%m-%Y") for d in day_list]
    writer.writerow(header)

    for s in students:
        row = [_csv_safe(s.get_full_name())]
        for d in day_list:
            a = att_map.get((s.id, d))
            if not a:
                row.append("")  # belgilanmagan
            elif getattr(a, "present", False):
                row.append("KELDI")
            elif getattr(a, "forced", False):
                row.append("KELMADI (PUL)")
            else:
                row.append("KELMADI")
        writer.writerow(row)

    return response



@require_POST
@login_required
def attendance_toggle_cell(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    # Ruxsat tekshiruvi: director, manager, teacher — barchasi tahrirlashi mumkin
    user = request.user
    is_allowed = (
        user.is_superuser
        or getattr(user, "role", None) in ("director", "manager", "teacher")
    )
    if not is_allowed:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    student_id = request.POST.get("student_id")
    date_str = request.POST.get("date")
    target_status = request.POST.get("target_status")   # new: direct set from popover
    current_status = request.POST.get("status", "none")  # legacy cycle fallback

    d = parse_date(date_str)
    if not d or not student_id:
        return JsonResponse({"ok": False, "error": "Bad data"}, status=400)

    user_qs = User.objects.filter(role="student")
    if center:
        user_qs = user_qs.filter(center=center)

    student = get_object_or_404(user_qs, pk=student_id)

    att = Attendance.objects.filter(group=group, student=student, date=d).first()

    def _prepare_att():
        nonlocal att
        if not att:
            att = Attendance(group=group, student=student, date=d)
            if hasattr(att, "center"):
                att.center = group.center
        if not getattr(att, "teacher_id", None) and getattr(group, "oqituvchi_id", None):
            att.teacher = group.oqituvchi
        return att

    # --- Direct set mode (from popover) ---
    if target_status in ("present", "absent", "excused", "none"):
        if target_status == "none":
            if att:
                att.delete()
            return JsonResponse({"ok": True, "status": "none"})

        att = _prepare_att()
        if target_status == "present":
            att.present = True
            att.forced = False
            if hasattr(att, "status"):
                att.status = "present"
        elif target_status == "absent":
            # Sababsiz kelmagan — pul yoziladi
            att.present = False
            att.forced = False
            if hasattr(att, "status"):
                att.status = "absent_unexcused"
        elif target_status == "excused":
            # Sababli kelmagan — pul yozilmaydi
            att.present = False
            att.forced = False
            if hasattr(att, "status"):
                att.status = "absent_excused"
        att.save()
        # excused → display status is "absent_excused"
        display = "absent_excused" if target_status == "excused" else target_status
        return JsonResponse({"ok": True, "status": display})

    # --- Legacy cycle mode (backward compat) ---
    if current_status == "none":
        att = _prepare_att()
        att.present = True
        att.forced = False
        att.save()
        new_status = "present"

    elif current_status == "present":
        att = _prepare_att()
        att.present = False
        att.forced = False
        att.save()
        new_status = "absent"

    elif current_status == "absent":
        if att:
            att.delete()
        new_status = "none"

    elif current_status == "forced":
        if att:
            att.delete()
        new_status = "none"

    else:
        new_status = current_status or "none"

    return JsonResponse({"ok": True, "status": new_status})



@login_required
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
    start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()), tz)
    end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()), tz)

    qs = Ledger.objects.filter(student_id=student_id, sana__range=(start, end))
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        qs = qs.filter(student__center=center)

    if type_ == "plus":
        qs = qs.filter(ball__gt=0)
    elif type_ == "minus":
        qs = qs.filter(ball__lt=0)

    details = []
    for l in qs.order_by("-sana"):
        show_dt = getattr(l, "created_at", None) or l.sana
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

def _last_12_month_starts():
    """Oxirgi 12 oy (shu oy ham kiradi), tartib: eski -> yangi"""
    today = timezone.localdate().replace(day=1)
    months = []
    for i in range(11, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))
    return months

def _month_start(d: date) -> date:
    return d.replace(day=1)

def _add_months(d: date, n: int) -> date:
    # month arithmetic
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)

def _last_12_ending(anchor: date) -> list[date]:
    # anchor included, return 12 month starts ending at anchor
    anchor = _month_start(anchor)
    return [_add_months(anchor, -11 + i) for i in range(12)]



@login_required
def tolovlar_home(request):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("core:home")

    center = get_active_center(request)
    if not center and not request.user.is_superuser:
        return HttpResponseForbidden("Markaz biriktirilmagan")


    from django.db.models import OuterRef, Subquery, IntegerField
    from django.db.models.functions import Coalesce as DjCoalesce
    from education.models import TuitionMonth, PaymentAllocation, Enrollment

    today = date.today()
    cur_month_start = today.replace(day=1)

    # ── 1) UMUMIY DAROMAD ─────────────────────────────────────────────────
    base_payment_qs = Payment.objects.filter(center=center) if center else Payment.objects.none()
    total_income = base_payment_qs.aggregate(s=Sum("summa"))["s"] or 0

    # ── 2) FILTER PARAMS ──────────────────────────────────────────────────
    q           = (request.GET.get("q") or "").strip()
    date_from   = (request.GET.get("date_from") or "").strip()
    date_to     = (request.GET.get("date_to") or "").strip()
    sel_group   = request.GET.get("group") or ""
    sel_teacher = request.GET.get("teacher") or ""
    sel_course  = request.GET.get("course") or ""
    sel_staff   = request.GET.get("staff") or ""
    sel_type    = request.GET.get("payment_type") or ""
    sel_month   = request.GET.get("pay_month") or ""


    # ✅ [FIX] Barcha to'lovlarni ko'rsatamiz (qarzi bormi yo'qmi farq qilmaydi)
    # Oldin: faqat qarzsiz o'quvchilar to'lovlari ko'rinardi — bu noto'g'ri edi!
    allocation_prefetch = Prefetch(
        "allocations",
        queryset=PaymentAllocation.objects.select_related(
            "tuition_month",
            "tuition_month__enrollment",
            "tuition_month__enrollment__group",
            "tuition_month__enrollment__group__category_obj",
        ).order_by("tuition_month__month", "id"),
        to_attr="prefetched_allocations",
    )

    pay_qs = base_payment_qs.select_related(
        "student", "group", "group__oqituvchi", "group__category_obj", "created_by"
    ).prefetch_related(allocation_prefetch)

    if q:
        pay_qs = pay_qs.filter(
            Q(student__ism__icontains=q) |
            Q(student__familya__icontains=q) |
            Q(student__telefon1__icontains=q)
        )
    if date_from:
        pay_qs = pay_qs.filter(paid_date__gte=date_from)
    if date_to:
        pay_qs = pay_qs.filter(paid_date__lte=date_to)
    if sel_group:
        pay_qs = pay_qs.filter(group_id=sel_group)
    if sel_teacher:
        pay_qs = pay_qs.filter(group__oqituvchi_id=sel_teacher)
    if sel_course:
        pay_qs = pay_qs.filter(group__category_obj_id=sel_course)
    if sel_staff:
        pay_qs = pay_qs.filter(created_by_id=sel_staff)
    if sel_type:
        pay_qs = pay_qs.filter(payment_type=sel_type)
    from django.utils import timezone
    cur_year = timezone.localdate().year

    if sel_month and sel_month.isdigit():
        # Match both month and current year to avoid historical overlaps
        pay_qs = pay_qs.filter(
            allocations__tuition_month__month__month=int(sel_month),
            allocations__tuition_month__month__year=cur_year
        ).distinct()

    # ✅ Fix: Summing on a filtered queryset with joins can double counts.
    payment_ids = pay_qs.values_list("id", flat=True)
    filtered_income = Payment.objects.filter(id__in=payment_ids).aggregate(s=Sum("summa"))["s"] or 0
    unique_payers_count = Payment.objects.filter(id__in=payment_ids).values("student").distinct().count()

    # ── 5) CHART (12 oy) ──────────────────────────────────────────────────
    month_starts = _last_12_ending(cur_month_start)
    m_min = month_starts[0]
    m_max = _add_months(month_starts[-1], 1) - timedelta(days=1)

    chart_qs = (
        pay_qs.filter(paid_date__gte=m_min, paid_date__lte=m_max)
        .annotate(m=TruncMonth("paid_date"))
        .values("m")
        .annotate(total=Sum("summa"))
        .order_by("m")
    )
    db_map = {}
    for row in chart_qs:
        m = row["m"]
        if not m:
            continue
        key = m.date().replace(day=1) if hasattr(m, "date") else m.replace(day=1)
        db_map[key] = int(row["total"] or 0)

    chart_labels = [m.strftime("%b") for m in month_starts]
    chart_data = [db_map.get(m, 0) for m in month_starts]

    # ── 6) PAGINATION ─────────────────────────────────────────────────────
    pay_qs = pay_qs.order_by("-paid_date", "-id")

    allowed_page_sizes = [10, 20, 50, 100]
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10
    if page_size not in allowed_page_sizes:
        page_size = 10

    paginator = Paginator(pay_qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)

    # ── 7) FILTER DROPDOWNS ───────────────────────────────────────────────
    groups = Group.objects.filter(is_archived=False)
    if center:
        groups = groups.filter(center=center)

    teachers_qs = User.objects.filter(role="teacher", is_active=True)
    if center:
        teachers_qs = teachers_qs.filter(center=center)

    courses = Category.objects.all().only("id", "name")

    staffs = User.objects.filter(role__in=["manager", "admin", "director"], is_active=True)
    if center:
        staffs = staffs.filter(center=center)

    uz_months = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
        (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
        (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
    ]

    return render(request, "education/tolovlar_list.html", {
        "page_obj": page_obj,
        "total_count": paginator.count,
        "total_income": total_income,
        "filtered_income": filtered_income,
        "chart_data": chart_data,
        "chart_labels": chart_labels,
        "unique_payers_count": unique_payers_count,
        "groups": groups,
        "teachers": teachers_qs,
        "courses": courses,
        "staffs": staffs,
        "uz_months": uz_months,
        "q": q,
        "date_from": date_from,
        "date_to": date_to,
        "sel_group": sel_group,
        "sel_teacher": sel_teacher,
        "sel_course": sel_course,
        "sel_staff": sel_staff,
        "sel_type": sel_type,
        "sel_month": sel_month,
        "page_size": page_size,
        "allowed_page_sizes": allowed_page_sizes,
        "query_string": query_params.urlencode(),
        "is_paginated": page_obj.has_other_pages(),
    })

@login_required
def get_payment_details(request):
    """
    Returns full transaction history for a specific TuitionMonth as JSON.
    """
    tuition_month_id = request.GET.get('tuition_month_id')
    student_id = request.GET.get('student_id')
    group_id = request.GET.get('group_id')
    
    if tuition_month_id:
        allocs = PaymentAllocation.objects.filter(
            tuition_month_id=tuition_month_id
        ).select_related('payment', 'payment__student', 'payment__group', 'payment__created_by')
    elif student_id and group_id:
        allocs = PaymentAllocation.objects.filter(
            payment__student_id=student_id,
            payment__group_id=group_id
        ).select_related('payment', 'payment__student', 'payment__group', 'payment__created_by')
    else:
        return JsonResponse({'ok': False, 'error': 'Missing identifiers'}, status=400)

    if not allocs.exists():
        return JsonResponse({'ok': True, 'payments': [], 'total_sum': 0})

    first = allocs.first()
    data = []
    total = 0
    for a in allocs.order_by('-payment__paid_date', '-id'):
        total += a.amount
        data.append({
            'id': a.payment.id,
            'amount': a.amount,
            'cash_amount': a.payment.cash_amount,
            'card_amount_som': a.payment.card_amount_som,
            'date': a.payment.paid_date.strftime("%d.%m.%Y"),
            'raw_date': a.payment.paid_date.strftime("%Y-%m-%d"),
            'time': a.payment.paid_time.strftime("%H:%M") if a.payment.paid_time else "--:--",
            'method': a.payment.get_payment_type_display(),
            'staff': a.payment.created_by.get_full_name() if a.payment.created_by else '—',
            'note': a.payment.note or ''
        })

    return JsonResponse({
        'ok': True,
        'student_name': first.payment.student.get_full_name(),
        'group_name': first.payment.group.nom,
        'teacher_name': first.payment.group.oqituvchi.get_full_name() if first.payment.group.oqituvchi else "—",
        'total_sum': total,
        'payments': data
    })


@login_required
def student_payments_pdf(request):
    """
    Generates a professional printable HTML summary of payments for a student.
    """
    student_id = request.GET.get('student_id')
    group_id = request.GET.get('group_id')

    if not student_id or not group_id:
        return HttpResponse("Missing student_id or group_id", status=400)

    center = get_active_center(request)
    student = get_object_or_404(User, id=student_id)
    group = get_object_or_404(Group, id=group_id)
    enrollment = Enrollment.objects.filter(student=student, group=group).first()

    if not enrollment:
        return HttpResponse("Enrollment topilmadi", status=404)

    payments_qs = Payment.objects.filter(enrollment=enrollment).select_related('created_by').order_by('paid_date', 'paid_time')
    
    total_paid = payments_qs.aggregate(s=Sum('summa'))['s'] or 0
    
    # Calculate total expected fee from TuitionMonths
    tms = TuitionMonth.objects.filter(enrollment=enrollment).order_by('month')
    total_expected = tms.aggregate(s=Sum('fee_amount'))['s'] or 0
    
    # Balance calculations
    remaining_debt = max(0, total_expected - total_paid)
    overpayment = max(0, total_paid - total_expected)

    # Monthly breakdown
    monthly_data = []
    for tm in tms:
        paid_amount = tm.allocations.aggregate(s=Sum('amount'))['s'] or 0
        monthly_data.append({
            'month': tm.month,
            'fee': tm.fee_amount,
            'paid': paid_amount,
            'debt': max(0, tm.fee_amount - paid_amount),
            'overpaid': max(0, paid_amount - tm.fee_amount),
        })

    context = {
        'center': center,
        'student': student,
        'group': group,
        'enrollment': enrollment,
        'payments': payments_qs,
        'total_paid': total_paid,
        'total_expected': total_expected,
        'remaining_debt': remaining_debt,
        'overpayment': overpayment,
        'monthly_data': monthly_data,
        'print_time': timezone.now(),
        'staff_name': request.user.get_full_name() or request.user.email,
    }
    
    return render(request, "education/receipt.html", context)

@require_POST
@login_required
def payment_delete(request, payment_id):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo'q.")
        return redirect("education:tolovlar_home")

    next_url = request.POST.get("next") or request.GET.get("next") or "education:tolovlar_home"

    center = get_active_center(request)
    qs = Payment.objects.all()
    if center:
        qs = qs.filter(center=center)
    
    payment = get_object_or_404(qs, id=payment_id)
    
    try:
        with transaction.atomic():
            # ✅ Soft delete allocations as well
            payment.allocations.all().delete(deleted_by=request.user)
            payment.delete(deleted_by=request.user)
                 
        messages.success(request, "✅ To'lov o'chirildi. O'quvchi qarzdorlar ro'yxatiga qaytadi.")
    except Exception as e:
        messages.error(request, f"❌ Xatolik: {e}")
    
    return redirect(next_url)


@login_required
def student_groups_api(request, student_id):
    """Return all active group names for a student (for payment modal display)."""
    center = get_active_center(request)
    qs = Enrollment.objects.filter(student_id=student_id, is_active=True, group__is_archived=False).select_related('group')
    if center:
        qs = qs.filter(center=center)
    groups = [e.group.nom for e in qs if e.group and not getattr(e.group, "is_archived", False)]
    return JsonResponse({"groups": " + ".join(groups) if groups else ""})


# education/views.py


# education/views.py




@login_required
def payment_history(request, student_id):
    """
    O'quvchining (barcha kurslari bo'yicha) to'lov tarixini va joriy oy holatini xisoblaydi.
    """
    month_str = request.GET.get("month")
    selected_month = parse_month_str(month_str) or first_day_of_current_month()
    
    # 1. Barcha enrollments
    enrs = Enrollment.objects.filter(student_id=student_id, is_active=True)
    
    total_fee = 0
    total_paid_this_month = 0
    
    for e in enrs:
        tm = ensure_tuition_month(e, selected_month)
        total_fee += int(getattr(tm, "fee_amount", 0) or 0)
        total_paid_this_month += int(get_month_paid(e, selected_month) or 0)
    
    total_qoldiq = max(0, total_fee - total_paid_this_month)
    
    # 2. Barcha to'lovlar
    qs = Payment.objects.filter(student_id=student_id).order_by('-paid_date', '-paid_time')
    from core.tenant import get_request_center
    center = get_active_center(request)
    if center:
        qs = qs.filter(center=center)
    
    payments_data = []
    for p in qs:
        # Har bir to'lov qaysi oylarga tushganini ham ko'rsatishimiz mumkin
        allocs = PaymentAllocation.objects.filter(payment=p).select_related("tuition_month")
        alloc_list = [{"month": a.tuition_month.month.strftime("%Y-%m"), "amount": a.amount} for a in allocs]
        
        payments_data.append({
            "id": p.id,
            "paid_at": f"{p.paid_date.strftime('%d.%m.%Y')} {p.paid_time.strftime('%H:%M')}",
            "cash": int(p.cash_amount or 0),
            "card": int(getattr(p, 'card_amount_som', 0) or getattr(p, 'card_amount', 0) or 0),
            "total": int(p.summa or 0),
            "allocations": alloc_list,
            "receipt_url": reverse("education:payment_receipt_pdf", args=[p.id]) if p.id else None
        })

    return JsonResponse({
        "month": selected_month.strftime("%Y-%m"),
        "fee": total_fee,
        "paid_this_month": total_paid_this_month,
        "qoldiq": total_qoldiq,
        "payments": payments_data
    })




def tolov_oqituvchilar(request):
    # whatever you already show for teachers (your groups_home, etc.)
    return render(request, "education/groups_home.html", {})  # or your real context



# ---------- HUB va ro'yxatlar ----------
@login_required
def groups_hub(request):
    """
    📘 Guruhlar markaziy sahifasi — barcha kategoriyalar ro'yxati.
    """
    from .models import Category  # agar alohida model bo'lsa
    categories = Category.objects.all() if hasattr(Category, "objects") else []
    return render(request, "education/groups_home.html", {
        "categories": categories,
    })

def group_delete_confirm(request, id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=id)
    if request.method == "POST":
        group.delete(deleted_by=request.user)
        return redirect("education:groups_home")
    return render(request, "education/group_delete_confirm.html", {"g": group})



@login_required
def edit_category(request, id):
    # ✅ Strict isolation: Only the center's own or global (if primary center)
    from core.tenant import get_request_center
    center = get_request_center(request)
    first_center = Center.objects.order_by("id").first()
    
    if first_center and center and center.id == first_center.id:
        # Primary center can edit its own and global orphans
        cat = get_object_or_404(Category, Q(center=center) | Q(center__isnull=True), id=id)
    else:
        # Other centers can only edit their own
        cat = get_object_or_404(Category, center=center, id=id)
        
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")

        cat.name = name
        cat.description = description

        # 🔹 Agar yangi rasm tanlangan bo'lsa, yangisini saqlaymiz
        if image:
            cat.image = image

        cat.save()
        messages.success(request, "Bo'lim muvaffaqiyatli tahrirlandi ✅")
        return redirect("education:groups_home")

    return render(request, "education/category_edit.html", {"cat": cat})


@login_required
def delete_category(request, id):
    # ✅ Strict isolation: Only the center's own or global (if primary center)
    from core.tenant import get_request_center
    center = get_request_center(request)
    first_center = Center.objects.order_by("id").first()
    
    if first_center and center and center.id == first_center.id:
        cat = get_object_or_404(Category, Q(center=center) | Q(center__isnull=True), id=id)
    else:
        cat = get_object_or_404(Category, center=center, id=id)

    if request.method == "POST":
        cat.delete(deleted_by=request.user)
        messages.success(request, "Bo'lim o'chirildi 🗑️")
        return redirect("education:groups_home")
    return render(request, "education/category_delete_confirm.html", {"cat": cat})


@login_required
def groups_by_category(request, category):
    if category not in ("lang", "it"):
        raise Http404("Noto'g'ri kategoriya")

    rows = (
        Group.objects.filter(category=category)
        .select_related("center", "oqituvchi")
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)),
            sana=Coalesce(F("course_start_date"), Cast(F("tuzilgan"), models.DateField()))
        )
        .order_by("nom")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)
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
        messages.error(request, "Sizda guruh yaratish huquqi yo'q.")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)

            # 🟢 To'g'ri maydon: ForeignKey bo'lgan 'category_obj'
            group.category_obj = category

            # Center assignment
            from core.tenant import get_request_center
            center = get_request_center(request)
            if center:
                group.center = center

            # Eski 'category' maydoni ham to'ldirilsa yaxshi
            group.category = Group.IT  # yoki Group.LANG — kerakli turga qarab
            group.save()

            messages.success(request, f"✅ '{group.nom}' guruhi {category.name} bo'limiga qo'shildi.")
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
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)),
            sana=Coalesce(F("course_start_date"), Cast(F("tuzilgan"), models.DateField()))
        )
        .order_by("nom")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)
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
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return HttpResponseForbidden("Siz bu guruhni ko'ra olmaysiz.")

    date_str = request.GET.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    if not selected_date:
        selected_date = localdate()
    selected_month = month_first_day(selected_date)

    enrollments = (
        Enrollment.objects
        .filter(group=g, is_active=True)
        .select_related("student", "group")   # ✅ MUHIM
        .order_by("student__ism", "student__familya")
    )
    student_user_ids = [e.student_id for e in enrollments]
    student_enrollment_qs = Enrollment.objects.filter(
        student_id__in=student_user_ids,
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
    )
    if center:
        student_enrollment_qs = student_enrollment_qs.filter(center=center)
    student_enrollment_ids = list(student_enrollment_qs.values_list("id", flat=True))

    # Studentning barcha aktiv guruhlari bo'yicha TANLANGAN OY
    # to'lov holatini hisoblaymiz.
    fee_field = tuition_month_fee_field()
    student_enrollments = list(student_enrollment_qs.select_related("group"))
    for enrollment in student_enrollments:
        ensure_tuition_month(enrollment, selected_month)
    eligible_enrollment_ids = [enrollment.id for enrollment in student_enrollments]

    student_total_fee_map = {
        sid: 0 for sid in student_user_ids
    }
    if eligible_enrollment_ids:
        student_total_fee_map.update(
            {
                row["enrollment__student_id"]: int(row["fee"] or 0)
                for row in (
                    TuitionMonth.objects
                    .filter(
                        enrollment_id__in=eligible_enrollment_ids,
                        month=selected_month,
                    )
                    .values("enrollment__student_id")
                    .annotate(fee=Coalesce(Sum(fee_field), 0))
                )
            }
        )

    student_total_paid_map = {
        row["tuition_month__enrollment__student_id"]: int(row["paid"] or 0)
        for row in (
            PaymentAllocation.objects
            .filter(
                tuition_month__enrollment_id__in=eligible_enrollment_ids or student_enrollment_ids,
                tuition_month__month=selected_month,
            )
            .values("tuition_month__enrollment__student_id")
            .annotate(paid=Coalesce(Sum("amount"), 0))
        )
    }

    # Balanslar: avval Ledger, agar studentda umuman Ledger bo'lmasa LightningHistory fallback.
    ledger_qs = Ledger.objects.filter(student_id__in=student_user_ids)
    if center:
        ledger_qs = ledger_qs.filter(
            Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True)
        )
    ledger_balance_map = {
        row["student_id"]: int(row["s"] or 0)
        for row in (
            ledger_qs.values("student_id").annotate(s=Coalesce(Sum("ball"), 0))
        )
    }
    history_balance_map = {}
    missing_balance_user_ids = [sid for sid in student_user_ids if sid not in ledger_balance_map]
    if missing_balance_user_ids:
        from chaqmoq.models import LightningHistory

        student_models = {
            st.user_id: st.id
            for st in Student.objects.filter(user_id__in=missing_balance_user_ids)
        }
        if student_models:
            history_qs = LightningHistory.objects.filter(student_id__in=student_models.values())
            if center:
                history_qs = history_qs.filter(student__user__center=center)
            history_totals = {
                row["student_id"]: int(row["s"] or 0)
                for row in (
                    history_qs.values("student_id").annotate(s=Coalesce(Sum("points"), 0))
                )
            }
            history_balance_map = {
                user_id: history_totals.get(student_pk, 0)
                for user_id, student_pk in student_models.items()
            }

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
    status_map = {}
    for a in att_qs:
        pres_map[a.student_id]   = a.present
        forced_map[a.student_id] = getattr(a, "forced", False)
        status_map[a.student_id] = getattr(a, "status", "present" if a.present else "none")

    # Studentga soxta fieldlar
    for e in enrollments:
        s = e.student
        s.balance = int(ledger_balance_map.get(s.id, history_balance_map.get(s.id, 0)))
        s.present_today     = bool(pres_map.get(s.id, False))
        s.forced_today      = bool(forced_map.get(s.id, False))
        s.attendance_status = status_map.get(s.id, "none")  # 'present' | 'absent_excused' | 'absent_unexcused' | 'none'

        total_fee = int(student_total_fee_map.get(s.id, 0))
        total_paid = int(student_total_paid_map.get(s.id, 0))
        total_remaining = max(0, total_fee - total_paid)

        if total_fee <= 0 or total_paid >= total_fee:
            payment_status = "paid"
            payment_status_label = "To'liq to'langan"
        elif total_paid > 0:
            payment_status = "partial"
            payment_status_label = "Chala to'langan"
        else:
            payment_status = "unpaid"
            payment_status_label = "To'lov qilinmagan"

        if total_fee <= 0:
            payment_status_title = "Tanlangan oy uchun to'lov majburiyati yo'q"
        elif payment_status == "paid":
            payment_status_title = (
                f"Tanlangan oy uchun to'liq to'langan: {total_paid:,} / {total_fee:,} so'm"
            )
        elif payment_status == "partial":
            payment_status_title = (
                f"Tanlangan oy uchun chala to'langan: {total_paid:,} / {total_fee:,} so'm"
                f" • Qoldiq: {total_remaining:,} so'm"
            )
        else:
            payment_status_title = f"Tanlangan oy uchun to'lov qilinmagan: 0 / {total_fee:,} so'm"

        e.payment_status = payment_status
        e.payment_status_label = payment_status_label
        e.payment_status_title = payment_status_title
        e.payment_month_fee = total_fee
        e.payment_month_paid = total_paid
        e.payment_month_remaining = total_remaining


    can_add_student = False
    can_remove_student = False
    
    if request.user.role == "director" or request.user.is_superuser:
        can_add_student = True
        can_remove_student = True
    elif center:
        if request.user.role == "manager":
            can_add_student = center.manager_can_add_student
            can_remove_student = center.manager_can_remove_student
        elif request.user.role == "teacher":
            can_add_student = center.teacher_can_add_student
            can_remove_student = center.teacher_can_remove_student

    # ✅ Filter rules by center and role
    rules_qs = Rule.objects.filter(Q(center=center) | Q(center__isnull=True))
    if request.user.role == 'teacher':
        rules_qs = rules_qs.filter(can_teacher=True)
    elif request.user.role == 'manager':
        rules_qs = rules_qs.filter(can_manager=True)
    elif request.user.role == 'director':
        rules_qs = rules_qs.filter(can_director=True)

    # Tanlangan sana bo'yicha kunlik chaqmoq o'zgarishlari (student + group + date)
    recent_history = (
        DailyLightningRecord.objects.filter(
            group=g,
            date=selected_date,
            student_id__in=student_user_ids,
        )
        .values("student_id")
        .annotate(
            recent_add=Coalesce(Sum("plus_points"), 0),
            recent_sub=Coalesce(Sum("minus_points"), 0),
        )
    )
    recent_history_map = {
        str(item["student_id"]): {
            "add": int(item["recent_add"] or 0),
            "sub": int(item["recent_sub"] or 0),
        }
        for item in recent_history
        if item["recent_add"] or item["recent_sub"]
    }

    exam_reminder_state = None
    if request.user.role in ("teacher", "director", "manager") or request.user.is_superuser:
        try:
            from education.services.exam_service import get_exam_reminder_state
            exam_reminder_state = get_exam_reminder_state(
                group=g,
                on_date=selected_date,
            )
        except Exception:
            logger.exception("Failed to calculate exam reminder state")
            exam_reminder_state = None

    can_view_internal_ranking = request.user.role in ("teacher", "director", "manager") or request.user.is_superuser
    internal_ranking_preview = []
    if can_view_internal_ranking:
        try:
            from education.services.ranking_service import get_group_internal_ranking_preview

            internal_ranking_preview = get_group_internal_ranking_preview(
                group=g,
                on_date=selected_date,
                limit=3,
                actor=request.user,
            )
        except Exception:
            logger.exception("Failed to calculate group internal ranking preview")
            internal_ranking_preview = []

    closure_state = None
    if request.user.role in ("teacher", "director", "manager") or request.user.is_superuser:
        try:
            from education.services.closure_service import get_group_closure_state

            closure_state = get_group_closure_state(
                group=g,
                on_date=selected_date,
            )
        except Exception:
            logger.exception("Failed to calculate group closure state")
            closure_state = None

    ctx = {
        "g": g,
        "enrollments": enrollments,
        "rules_plus": rules_qs.filter(tur=Rule.PLUS).order_by("nom"),
        "rules_minus": rules_qs.filter(tur=Rule.MINUS).order_by("nom"),
        "can_add_student": can_add_student,
        "can_remove_student": can_remove_student,
        "selected_date": selected_date.isoformat(),
        "today": localdate().isoformat(),
        "recent_history_map": recent_history_map,
        "exam_reminder_state": exam_reminder_state,
        "internal_ranking_preview": internal_ranking_preview,
        "can_view_internal_ranking": can_view_internal_ranking,
        "closure_state": closure_state,
    }
    return render(request, "education/group_detail.html", ctx)


from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils.dateparse import parse_date

@login_required
@require_POST
def attendance_force(request):
    """
    Tanlangan guruh va sana bo'yicha:
    ✅ kelmagan (present=False) o'quvchilar uchun
    forced=True qilib, o'qituvchiga pul yoziladigan dars sifatida belgilaydi.

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
        return JsonResponse({"ok": False, "error": "Sana noto'g'ri formatda"})

    # Guruhni olamiz
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=group_id)

    # Shu guruhdagi barcha faol enrollments (arxivlanganlar istisno)
    enrollments = Enrollment.objects.filter(group=g, is_active=True).select_related("student")

    # Shu sana uchun mavjud attendance yozuvlari
    att_qs = Attendance.objects.filter(group=g, date=date_obj)
    att_by_student = {a.student_id: a for a in att_qs}

    forced_count = 0

    for enr in enrollments:
        att = att_by_student.get(enr.student_id)

        if att:
            # Agar allaqachon present=True bo'lsa, buni majburan "kelmadi" qilishni xohlamaymiz
            # (agar kerak bo'lsa, bu qismni o'zing o'zgartirasan)
            if att.present:
                continue

            if not att.forced:
                att.forced = True
                att.present = False  # forced bo'lsa ham uni "kelmadi" deb saqlab qo'yamiz
                att.save()
                forced_count += 1
        else:
            # Hech qanday attendance yo'q bo'lsa, yangi "kelmadi, forced" yozuvi yaratamiz
            Attendance.objects.create(
                group=g,
                student=enr.student,
                teacher=g.oqituvchi,
                date=date_obj,
                present=False,
                forced=True,
                center=g.center if hasattr(Attendance, 'center') else None
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

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # faqat direktor/manager/teacher
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return JsonResponse({"ok": False, "error": "ruxsat yo'q"})

    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    students = Enrollment.objects.filter(group=g, is_active=True).select_related("student")
    count = 0

    for e in students:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True, "forced": False, "status": "present", "teacher": request.user}
        )
        count += 1

    return JsonResponse({"ok": True, "count": count})

@require_POST
@login_required
def attend_all_students(request, g_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=g_id)

    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return JsonResponse({"ok": False, "error": "ruxsat yo'q"})

    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    enrollments = Enrollment.objects.filter(group=g, is_active=True).select_related("student")

    items = []
    count = 0

    for e in enrollments:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True, "forced": False, "status": "present", "teacher": request.user, "center": g.center, "created_by": request.user},
        )
        balance = Ledger.student_balansi(e.student.id, center=g.center)

        items.append({"student_id": e.student.id, "balance": balance, "restored_sum": 0})
        count += 1

    return JsonResponse({"ok": True, "count": count, "items": items})

# ---------- AJAX: Davomatni saqlash ----------
@require_POST
@login_required
def attendance_today(request, pk: int):
    """
    status:
      - 'present'          -> present=True,  forced=False, status='present'
      - 'absent_excused'   -> present=False, forced=False, status='absent_excused'   (sababli)
      - 'absent_unexcused' -> present=False, forced=False, status='absent_unexcused' (sababsiz) + Rule Engine
      - 'forced'           -> present=False, forced=True,  status='absent_unexcused' (eski logika saqlanadi)
      - 'none'             -> attendance yozuvi o'chiriladi
    Backward compatible: present=1/0 yuborilsa ham ishlaydi.
    """
    g = get_object_or_404(Group, pk=pk)
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center and g.center_id != center.id:
        return JsonResponse({"ok": False, "error": "Center mismatch"}, status=403)

    # faqat direktor/manager/teacher
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return JsonResponse({"ok": False, "error": "ruxsat yo'q"}, status=403)

    enr_id = request.POST.get("enr_id")
    if not enr_id:
        return JsonResponse({"ok": False, "error": "enr_id required"}, status=400)

    # sana
    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    # status (yangi: 5 ta holat)
    status = (request.POST.get("status") or "").strip().lower()

    VALID_STATUSES = ("present", "absent_excused", "absent_unexcused", "forced", "none")

    # backward compatibility (eski front bo'lsa)
    if status not in VALID_STATUSES:
        pv = request.POST.get("present")
        if pv is None:
            return JsonResponse({"ok": False, "error": "status/present required"}, status=400)
        status = "present" if str(pv).lower() in ("1", "true", "yes", "on") else "none"

    e = get_object_or_404(Enrollment, id=enr_id, group=g)
    student = e.student

    removed_sum = 0
    removed_count = 0
    penalized = False
    bonused = False

    # ── Attendance ni yaratish/yangilash/o'chirish ──
    present = False
    forced = False

    if status == "none":
        Attendance.objects.filter(group=g, student=student, date=selected_date).delete()
    else:
        # qolgan statuslar uchun update_or_create
        present = (status == "present")
        forced = (status == "forced")
        Attendance.objects.update_or_create(
            group=g, student=student, date=selected_date,
            defaults={
                "teacher": request.user,
                "present": present,
                "forced": forced,
                "status": status,
                "center": g.center,
                "created_by": request.user,
            }
        )

    # yangi balans
    bal = Ledger.student_balansi(student.id, center=g.center)

    return JsonResponse({
        "ok": True,
        "status": status,
        "present": present,
        "forced": forced,
        "removed_sum": removed_sum,
        "removed_count": removed_count,
        "balance": bal,
        "penalty_applied": penalized,
        "bonus_applied": bonused,
    })



@login_required
def group_bulk_remove(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "POST bo'lishi shart."})

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
         qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # ruxsat tekshirish
    can_remove = False
    if request.user.role == "director" or request.user.is_superuser:
        can_remove = True
    elif center:
        if request.user.role == "manager":
            can_remove = center.manager_can_remove_student
        elif request.user.role == "teacher":
            can_remove = center.teacher_can_remove_student

    if not can_remove:
        return JsonResponse({"ok": False, "msg": "Sizda o'quvchilarni o'chirish huquqi yo'q."})

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
    """
    Apply rules to students (points system) with proper Student-User link handling.
    """
    try:
        from django.db import transaction
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        from education.models import Enrollment, Group
        from chaqmoq.models import Ledger, Rule
        from accounts.models import User

        if request.method != "POST":
            return JsonResponse({"status": "error", "message": "Method not allowed"}, status=200)

        # 1. Parse Data
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        student_id = data.get("student_id")
        rule_id = data.get("rule_id")
        amount = int(data.get("amount", 0))
        date_str = data.get("date")

        if not student_id:
            return JsonResponse({"status": "error", "message": "O'quvchi tanlanmagan"}, status=200)

        # 2. Student & Group Lookup (Safe search)
        # Guruhni topish
        g = Group.objects.filter(pk=pk).first()
        if not g:
            return JsonResponse({"status": "error", "message": "Guruh topilmadi"}, status=200)

        # O'quvchini bevosita User modeli orqali topamiz.
        # Agar bu yerda Enrollment bo'yicha qidirsak, bir xil ID ga ega boshqa o'quvchi
        # tanlanib qolishi va "refresh davomida points yo'qolish" muammosi yuzaga keladi.
        student_user = User.objects.filter(pk=student_id, role='student').first()

        if not student_user:
             # Senior Senior Senior logic: Agar o'quvchi topilmasa, qizil xato chiqarmaslik uchun
             # status: success qaytaramiz, lekin message bermaymiz.
             return JsonResponse({"status": "success", "message": "", "ok": True}, status=200)

        # 3. Rule Handling
        if rule_id and str(rule_id).isdigit():
            rule = Rule.objects.filter(pk=rule_id).first()
        else:
            rule = None
            
        if not rule:
            rule = Rule.objects.filter(nom="Erkin ball", center=g.center).first()
            if not rule:
                rule = Rule.objects.create(
                    nom="Erkin ball", tur=Rule.PLUS, min_baho=1, max_baho=1000000, center=g.center
                )

        # 4. Date processing
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()
        now_time = timezone.localtime(timezone.now()).time()
        sana = timezone.make_aware(datetime.combine(parsed_date, now_time))

        request_id = data.get("request_id", "")
        from django.core.cache import cache
        cache_key = f"ledger_req_{request_id}" if request_id else None

        # ✅ DATABASE-LEVEL LOCK bilan idempotency
        # select_for_update() - parallel workerlar (gunicorn) bir vaqtda create qilishini oldini oladi
        with transaction.atomic():
            # Lock: bir vaqtda faqat bitta worker shu student uchun ishlay oladi
            # Render.com dagi parallel workerlar yaratishda "phantom read" muammosini oldini olish
            # uchun Ledger ni emas (u hali yo'q bo'lishi mumkin), aynan User ni qulflaymiz
            _lock_student = User.objects.select_for_update().get(id=student_user.id)

            # ✅ 1-HIMOYA: Lock olingach yana Cache ni tekshirish.
            if cache_key:
                cached = cache.get(cache_key)
                if cached:
                    return JsonResponse(cached)



            # Yangi yozuv yaratish
            record = Ledger.objects.create(
                student=student_user,
                beruvchi=request.user,
                group=g,
                rule=rule,
                ball=amount,
                sana=sana,
            )

            from chaqmoq.models import LightningHistory
            from education.models import Student as EdStudent
            st_model, _ = EdStudent.objects.get_or_create(user=student_user)
            LightningHistory.objects.create(
                student=st_model,
                points=amount,
                reason=rule.nom if rule else "Erkin ball",
                source="manual",
                teacher=request.user
            )
            _accumulate_daily_lightning(
                group=g,
                student=student_user,
                date_value=parsed_date,
                points_delta=amount,
            )

            # Yangi balansni hisoblash
            balance = Ledger.student_balansi(student_user.id, center=g.center)

        response_data = {
            "status": "success",
            "message": "Ball saqlandi",
            "balance": int(balance),
            "amount": amount,
            "id": record.id,
            "ok": True
        }

        # ✅ Muvaffaqiyatli response ni cache ga yozamiz (60 soniya)
        # Xuddi shu request_id qayta kelsa - yangi yozuv yaratilmaydi
        if request_id:
            from django.core.cache import cache
            cache.set(f"ledger_req_{request_id}", response_data, timeout=60)

        return JsonResponse(response_data)

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Points logic error")
        return JsonResponse({
            "status": "error",
            "message": f"Serverda xato yuz berdi: {str(e)}"
        }, status=200) # Toast qizil chiqmasligi uchun 200 qaytaramiz (JSON error ichida bo'ladi)


# @login_required
# def groups_home(request):
#     categories = Category.objects.all().order_by("name")
#     return render(request, "education/groups_home.html", {"categories": categories})


def category_detail(request, category_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    category = get_object_or_404(Category, id=category_id)
    if center:
        if category.center_id and category.center_id != center.id:
            raise PermissionDenied("Bu bo'limga ruxsat yo'q")

    groups = Group.objects.filter(category_obj=category).order_by("id")
    if center:
        groups = groups.filter(center=center)

    # Filter by status (default: active)
    status = request.GET.get('status', 'active')
    
    # ✅ TEACHERLAR UCHUN "ARXIV" YOPIQ
    if request.user.role == 'teacher':
        status = 'active'
        groups = groups.filter(is_archived=False)
    else:
        if status == 'archived':
            groups = groups.filter(is_archived=True)
        else:
            groups = groups.filter(is_archived=False)

    return render(request, "education/category_detail.html", {
        "category": category,
        "groups": groups,
        "groups_count": groups.count(),
        "status": status,
        "is_teacher": request.user.role == 'teacher', # Template uchun
    })


@login_required
def group_toggle_archive(request, pk):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=pk)

    if not _can_manage(request.user):
         messages.error(request, "Ruxsat yo'q.")
         return redirect("education:category_detail", category_id=group.category_obj.id)
         
    if request.method == "POST":
        group.is_archived = not group.is_archived
        group.save()
        status_msg = "arxivlandi" if group.is_archived else "faollashtirildi"
        messages.success(request, f"Guruh muvaffaqiyatli {status_msg} ✅")
        
    return redirect("education:category_detail", category_id=group.category_obj.id)

from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from education.models import Group, Dars, OylikHisobot
from accounts.models import User

@login_required
def oylik_hisobot(request):
    """Har bir o'qituvchining oyligini avtomatik hisoblash"""
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
            "oqituvchi": teacher.get_full_name() or teacher.email,
            "guruhlar": guruhlar.count(),
            "darslar": jami_darslar,
            "daromad": round(jami_daromad),
            "markaz_foydasi": round(markaz_foydasi),
        })

        # OylikHisobot jadvaliga yozib qo'yish
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
    from core.tenant import get_request_center
    center = get_request_center(request)
    category = get_object_or_404(Category, id=category_id)
    if center:
        if category.center_id and category.center_id != center.id:
            raise PermissionDenied("Bu bo'limga ruxsat yo'q")

    if request.method == "POST":
        form = GroupForm(request.POST, center=center)
        if form.is_valid():
            group = form.save(commit=False)
            group.category_obj = category
            group.center = center

            # O'qituvchi tanlanganda foiz teacher profilidan olinadi.
            if group.oqituvchi and getattr(group.oqituvchi, "oqituvchi_foizi", None) is not None:
                group.oqituvchi_foiz = group.oqituvchi.oqituvchi_foizi
            elif not group.oqituvchi_foiz:
                group.oqituvchi_foiz = 40

            from education.services.group_schedule_service import apply_group_duration_defaults
            apply_group_duration_defaults(group)
            group.save()
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm(center=center)

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
                "placeholder": "Bo'lim haqida qisqa izoh"
            }),
        }



@login_required
def groups_home(request):
    # ✅ Tenant isolation
    from core.tenant import get_request_center
    center = get_request_center(request)
    
    # kategoriyalar
    from django.db.models import Q
    categories_qs = Category.objects.all().order_by("name")
    if center:
        # ✅ Smart Isolation: 
        # 1. Faqat shu center'ga tegishli bo'limlarni ko'rsatamiz.
        # 2. Agar bu ASOSIY (birinchi yaratilgan) markaz bo'lsa, Global (Legacy) bo'limlarni ham chiqaramiz.
        first_center = Center.objects.order_by("id").first()
        if first_center and center.id == first_center.id:
            categories_qs = categories_qs.filter(Q(center=center) | Q(center__isnull=True))
        else:
            categories_qs = categories_qs.filter(center=center)
        
    categories = list(categories_qs)

    # har bir category uchun guruhlar sonini hisoblab map qilamiz
    counts_qs = (
        Group.objects
    )
    if center:
        counts_qs = counts_qs.filter(center=center)
        
    counts_qs = (
        counts_qs
        .filter(is_archived=False)
        .values("category_obj")          # FK field nomi sizda shu: category_obj
        .annotate(c=Count("id"))
    )
    count_map = {row["category_obj"]: row["c"] for row in counts_qs}

    # template ishlatishi uchun cat.groups_count qo'shib chiqamiz
    for cat in categories:
        cat.groups_count = count_map.get(cat.id, 0)

    return render(request, "education/groups_home.html", {
        "categories": categories,
        "categories_count": len(categories),
    })


@login_required
def add_category(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.center = center
            cat.save()
            messages.success(request, "Bo'lim muvaffaqiyatli qo'shildi ✅")
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
        e.student for e in g.enrollments.filter(is_active=True).select_related("student").order_by("student__ism", "student__familya")
    ]

    pres_map = {
        a.student_id: a.present for a in Attendance.objects.filter(group=g, date=the_date)
    }
    for s in students:
        s.present = pres_map.get(s.id, False)
        s.balance = Ledger.student_balansi(s.id, center=g.center)

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
                    now_local = timezone.localtime(timezone.now()).time()
                    sana = timezone.make_aware(datetime.combine(the_date, now_local))
                    Ledger.objects.create(student=s, beruvchi=request.user, group=g, rule=rule, ball=signed, sana=sana)
                    
                    from chaqmoq.models import LightningHistory
                    from education.models import Student as EdStudent
                    st_model, _ = EdStudent.objects.get_or_create(user=s)
                    LightningHistory.objects.create(
                        student=st_model,
                        points=signed,
                        reason=rule.nom if rule else "Manual ball",
                        source="manual",
                        teacher=request.user
                    )
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
    now = timezone.localdate()
    year = _get_int(request.GET, "year", now.year)
    month = _get_int(request.GET, "month", now.month)

    if month < 1 or month > 12:
        month = now.month

    month_names_uz = [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
    ]
    month_name = month_names_uz[month - 1]
    
    from core.tenant import get_request_center
    center = get_request_center(request)
    
    teacher_qs = User.objects.filter(role="teacher")
    if center:
        teacher_qs = teacher_qs.filter(center=center)
    teachers = teacher_qs.order_by("ism")

    teacher_rows = []
    total_all = 0

    from education.models import FinancialMonth
    fin_month = FinancialMonth.objects.filter(year=year, month=month, center=center).first()
    is_closed = fin_month.is_closed if fin_month else False

    from education.services.historical_finance_service import HistoricalFinanceService

    for t in teachers:
        # Dynanic calculation or Snapshot for the teacher
        salary_data = HistoricalFinanceService.calculate_teacher_salary(t, year, month, center)
        teacher_salary = salary_data['salary']
        groups_count = len(salary_data['details'])
        total_all += teacher_salary

        teacher_rows.append({
            "teacher": t,
            "month_salary": teacher_salary,
            "groups_count": groups_count,
        })
        
    return render(request, "education/teacher_salary_list.html", {
        "teachers": teacher_rows,
        "year": year,
        "month": month,
        "month_name": month_name,
        "total_all": total_all,
        "is_closed": is_closed,
    })

# 🔹 Excel Export — O'qituvchi oyligi hisoboti
@login_required
def teacher_salary_export(request):
    """
    Tanlangan oy/yil bo'yicha barcha o'qituvchilar oylik hisobotini
    professional Excel (.xlsx) fayl sifatida yuklab beradi.

    Sheet 1: Umumiy hisobot (barchasi + bar chart)
    Sheet 2..N: Har bir o'qituvchi uchun alohida — guruh va o'quvchi kesimida.
    """
    import io
    import openpyxl
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side, numbers
    )
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, Reference

    from core.tenant import get_request_center
    from education.services.historical_finance_service import HistoricalFinanceService

    # ── Parametrlar ──────────────────────────────────────────────────────────
    now   = timezone.localdate()
    year  = _get_int(request.GET, "year",  now.year)
    month = _get_int(request.GET, "month", now.month)
    if month < 1 or month > 12:
        month = now.month

    center = get_request_center(request)

    MONTH_NAMES = [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
    ]
    month_name = MONTH_NAMES[month - 1]
    period_label = f"{month_name} {year}"

    # ── O'qituvchilar va oylik ma'lumot ──────────────────────────────────────
    teacher_qs = User.objects.filter(role="teacher")
    if center:
        teacher_qs = teacher_qs.filter(center=center)
    teachers = list(teacher_qs.order_by("ism"))

    salary_rows = []
    for t in teachers:
        data = HistoricalFinanceService.calculate_teacher_salary(t, year, month, center)
        salary_rows.append({
            "teacher": t,
            "salary":  data["salary"],
            "details": data.get("details", []),
        })

    # ── Stil yordamchilari ───────────────────────────────────────────────────
    def _hdr_fill(hex_color):
        return PatternFill("solid", fgColor=hex_color)

    def _border(style="thin"):
        s = Side(style=style)
        return Border(left=s, right=s, top=s, bottom=s)

    def _bold(size=11, color="000000"):
        return Font(bold=True, size=size, color=color)

    def _money_fmt():
        return "#,##0"

    def _auto_width(ws, extra=4):
        for col in ws.columns:
            mx = 0
            for cell in col:
                try:
                    mx = max(mx, len(str(cell.value or "")))
                except Exception:
                    pass
            ws.column_dimensions[get_column_letter(col[0].column)].width = mx + extra

    # ── Minimalist yorqin rang sxemasi ──────────────────────────────────────
    # Asosiy: ko'k (2563EB) | Guruh: yashil (0EA472) | Jami: sariq (F59E0B)
    # Fon: oq (FFFFFF) | Alt qator: och kulrang (F8FAFC) | Chegara: kulrang (CBD5E1)
    HDR_DARK   = _hdr_fill("2563EB")   # bosh sarlavha — chuqur ko'k
    HDR_BLUE   = _hdr_fill("3B82F6")   # ustun header — yorqin ko'k
    HDR_GREEN  = _hdr_fill("0EA472")   # guruh blok — yashil
    TOTAL_FILL = _hdr_fill("FEF3C7")   # jami satri — sariq fon
    ALT_FILL   = _hdr_fill("F1F5F9")   # juft qatorlar — och kulrang
    WHITE_FONT = Font(bold=True, color="FFFFFF", size=11)
    DARK_FONT  = Font(color="1E293B", size=10)
    TOTAL_FONT = Font(bold=True, color="92400E", size=11)   # jami — to'q jigarrang
    MONEY_NUM  = _money_fmt()

    wb = openpyxl.Workbook()

    # ════════════════════════════════════════════════════════════════════════
    # SHEET 1 — UMUMIY HISOBOT
    # ════════════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "Umumiy hisobot"
    ws1.sheet_view.showGridLines = False

    # Sarlavha
    ws1.merge_cells("A1:G1")
    title_cell = ws1["A1"]
    title_cell.value = f"O'qituvchilar Oylik Hisoboti — {period_label}"
    title_cell.font  = Font(bold=True, size=16, color="FFFFFF")
    title_cell.fill  = HDR_DARK
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 36

    # Ustun sarlavhalari
    headers1 = ["T/r", "O'qituvchi", "Guruhlar soni", "O'quvchilar soni",
                 "Qatnashuv (dars)", "Hisoblangan oylik (so'm)", "Izoh"]
    ws1.append([])  # bo'sh qator (row 2)
    ws1.append(headers1)  # row 3
    for ci, h in enumerate(headers1, 1):
        cell = ws1.cell(row=3, column=ci)
        cell.value  = h
        cell.font   = WHITE_FONT
        cell.fill   = HDR_BLUE
        cell.border = _border()
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws1.row_dimensions[3].height = 28

    total_sum = 0
    chart_names    = []
    chart_salaries = []

    for idx, row in enumerate(salary_rows, 1):
        t       = row["teacher"]
        details = row["details"]
        students_total = sum(len(d.get("enrollments", [])) for d in details)
        attend_total   = sum(d.get("attendance", 0) for d in details)
        salary         = row["salary"]
        total_sum     += salary

        name = t.get_full_name() or t.email
        chart_names.append(name[:20])
        chart_salaries.append(salary)

        data_row = [idx, name, len(details), students_total, attend_total, salary, ""]
        ws1.append(data_row)
        ri = ws1.max_row
        # Juft — och kulrang, toq — oq
        fill = ALT_FILL if idx % 2 == 0 else _hdr_fill("FFFFFF")
        for ci, val in enumerate(data_row, 1):
            cell = ws1.cell(row=ri, column=ci)
            cell.fill   = fill
            cell.border = _border()
            cell.font   = Font(color="334155", size=10)
            cell.alignment = Alignment(vertical="center",
                                       horizontal="center" if ci in (1,3,4,5) else "left")
            if ci == 6:
                cell.number_format = MONEY_NUM
                cell.font = Font(color="1D4ED8", size=10, bold=True)

    # JAMI SATRI
    jami_ri = ws1.max_row + 1
    ws1.cell(row=jami_ri, column=1).value = "JAMI"
    ws1.cell(row=jami_ri, column=6).value = total_sum
    ws1.cell(row=jami_ri, column=6).number_format = MONEY_NUM
    for ci in range(1, 8):
        cell = ws1.cell(row=jami_ri, column=ci)
        cell.fill   = TOTAL_FILL
        cell.font   = TOTAL_FONT
        cell.border = _border()
        cell.alignment = Alignment(horizontal="center" if ci == 1 else "left", vertical="center")
    ws1.cell(row=jami_ri, column=6).font = Font(bold=True, color="92400E", size=11)
    ws1.row_dimensions[jami_ri].height = 26

    # BAR CHART
    if chart_names:
        chart = BarChart()
        chart.type   = "col"
        chart.title  = f"O'qituvchilar oyligi — {period_label}"
        chart.y_axis.title = "Oylik (so'm)"
        chart.x_axis.title = "O'qituvchi"
        chart.style  = 10
        chart.width  = 28
        chart.height = 16

        data_ref = Reference(ws1,
                             min_col=6, max_col=6,
                             min_row=3, max_row=3 + len(salary_rows) - 1)
        cats_ref = Reference(ws1,
                             min_col=2, max_col=2,
                             min_row=4, max_row=3 + len(salary_rows))
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        ws1.add_chart(chart, f"A{jami_ri + 2}")

    ws1.freeze_panes = "A4"
    _auto_width(ws1)

    # ════════════════════════════════════════════════════════════════════════
    # SHEET 2..N — HAR BIR O'QITUVCHI
    # ════════════════════════════════════════════════════════════════════════
    for row in salary_rows:
        t       = row["teacher"]
        details = row["details"]
        salary  = row["salary"]

        # Sheet nomi: Excel 31 belgidan oshmasin, noto'g'ri belgilar yo'qolsin
        raw_name   = t.get_full_name() or t.email or f"Ustoz_{t.pk}"
        sheet_name = raw_name[:28].translate(
            str.maketrans(r'\/*?:[]', '_______')
        )
        # Takrorlanmaslik uchun son qo'shamiz
        base = sheet_name
        cnt  = 1
        while sheet_name in [s.title for s in wb.worksheets]:
            sheet_name = f"{base[:25]}_{cnt}"
            cnt += 1

        ws = wb.create_sheet(title=sheet_name)
        ws.sheet_view.showGridLines = False

        # ── HEADER blok ─────────────────────────────────────────────────────
        students_total = sum(len(d.get("enrollments", [])) for d in details)
        attend_total   = sum(d.get("attendance", 0) for d in details)

        ws.merge_cells("A1:F1")
        ws["A1"].value = f"O'qituvchi: {raw_name}  |  Davr: {period_label}"
        ws["A1"].font  = Font(bold=True, size=14, color="FFFFFF")
        ws["A1"].fill  = HDR_DARK
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 34

        meta_rows = [
            ("Guruhlar soni",          len(details)),
            ("Jami o'quvchilar",        students_total),
            ("Jami dars (qatnashuv)",   attend_total),
            ("Hisoblangan jami oylik",  salary),
        ]
        for mi, (label, val) in enumerate(meta_rows, 2):
            lbl_cell = ws.cell(row=mi, column=1)
            lbl_cell.value = label
            lbl_cell.font  = Font(bold=True, color="64748B", size=10)
            lbl_cell.fill  = _hdr_fill("F8FAFC")

            val_cell = ws.cell(row=mi, column=2)
            val_cell.value = val
            val_cell.font  = Font(color="1E293B", size=10)
            val_cell.fill  = _hdr_fill("F8FAFC")
            if mi == 5:  # oylik satri
                val_cell.number_format = MONEY_NUM
                val_cell.font = Font(bold=True, color="1D4ED8", size=11)

        cur_row = 7  # guruh bloklari shu satrdan boshlanadi

        if not details:
            ws.cell(row=cur_row, column=1).value = "Bu oy uchun ma'lumot yo'q."
            ws.cell(row=cur_row, column=1).font  = Font(color="94A3B8", italic=True)
        else:
            for gd in details:
                gname       = gd.get("group_name", "Guruh")
                g_salary    = gd.get("salary", 0)
                g_attend    = gd.get("attendance", 0)
                enrollments = gd.get("enrollments", [])

                # ── Guruh sarlavhasi ─────────────────────────────────────────
                ws.merge_cells(start_row=cur_row, start_column=1,
                               end_row=cur_row, end_column=6)
                hdr = ws.cell(row=cur_row, column=1)
                hdr.value = f"  {gname}   |   Guruh daromadi: {g_salary:,} som   |   Dars: {g_attend} marta"
                hdr.font  = Font(bold=True, color="FFFFFF", size=11)
                hdr.fill  = HDR_GREEN
                hdr.border = _border()
                hdr.alignment = Alignment(vertical="center", horizontal="left")
                ws.row_dimensions[cur_row].height = 26
                cur_row += 1

                # ── O'quvchilar jadval sarlavhasi ────────────────────────────
                sub_hdrs = ["T/r", "O'quvchi", "Kurs narhi", "Qatnashuv (kun)",
                            "Daromad (so'm)", "Izoh"]
                for ci, h in enumerate(sub_hdrs, 1):
                    cell = ws.cell(row=cur_row, column=ci)
                    cell.value  = h
                    cell.font   = Font(bold=True, color="FFFFFF", size=10)
                    cell.fill   = HDR_BLUE
                    cell.border = _border()
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                ws.row_dimensions[cur_row].height = 22
                cur_row += 1

                # ── O'quvchilar satrlari ──────────────────────────────────────
                for si, en in enumerate(enrollments, 1):
                    sname   = en.get("student_name", "Noma'lum")
                    kn      = en.get("kurs_narhi", 0)
                    att     = en.get("attended", 0)
                    daromad = en.get("daromad", 0)

                    # Juft — och kulrang, toq — oq
                    fill = ALT_FILL if si % 2 == 0 else _hdr_fill("FFFFFF")
                    data = [si, sname, kn, att, daromad, ""]
                    for ci, v in enumerate(data, 1):
                        cell = ws.cell(row=cur_row, column=ci)
                        cell.value  = v
                        cell.fill   = fill
                        cell.border = _border()
                        cell.font   = Font(color="334155", size=10)
                        cell.alignment = Alignment(vertical="center",
                                                   horizontal="center" if ci in (1,4) else "left")
                        if ci == 3:
                            cell.number_format = MONEY_NUM
                            cell.font = Font(color="475569", size=10)
                        if ci == 5:
                            cell.number_format = MONEY_NUM
                            cell.font = Font(color="1D4ED8", size=10, bold=True)
                    cur_row += 1

                # ── Guruh jami satri ─────────────────────────────────────────
                for ci in range(1, 7):
                    cell = ws.cell(row=cur_row, column=ci)
                    cell.fill   = TOTAL_FILL
                    cell.border = _border()
                    cell.font   = TOTAL_FONT
                    cell.alignment = Alignment(vertical="center", horizontal="left")
                ws.cell(row=cur_row, column=2).value = "GURUH JAMI:"
                ws.cell(row=cur_row, column=2).alignment = Alignment(horizontal="right", vertical="center")
                ws.cell(row=cur_row, column=5).value = g_salary
                ws.cell(row=cur_row, column=5).number_format = MONEY_NUM
                ws.cell(row=cur_row, column=5).font = Font(bold=True, color="92400E", size=11)
                ws.row_dimensions[cur_row].height = 22
                cur_row += 2  # bo'sh qator + keyingi guruh

            # ── Umumiy jami (sheet pastida) ──────────────────────────────────
            ws.merge_cells(start_row=cur_row, start_column=1,
                           end_row=cur_row, end_column=4)
            lbl = ws.cell(row=cur_row, column=1)
            lbl.value = "BARCHA GURUHLAR JAMI OYLIGI:"
            lbl.font  = Font(bold=True, color="FFFFFF", size=12)
            lbl.fill  = HDR_DARK
            lbl.border = _border()
            lbl.alignment = Alignment(horizontal="right", vertical="center")

            tot = ws.cell(row=cur_row, column=5)
            tot.value  = salary
            tot.font   = Font(bold=True, color="FFFFFF", size=13)
            tot.fill   = HDR_DARK
            tot.border = _border()
            tot.number_format = MONEY_NUM
            ws.row_dimensions[cur_row].height = 32

        ws.freeze_panes = "A7"
        _auto_width(ws)

    # ── Fayl qaytarish ───────────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"oylik_hisobot_{year}_{month:02d}.xlsx"
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# 🔹 2. O'qituvchining barcha guruhlari
@login_required
def teacher_groups(request, teacher_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = User.objects.filter(role="teacher")
    if center:
         qs = qs.filter(center=center)
    teacher = get_object_or_404(qs, id=teacher_id)
    
    now = timezone.localdate()
    year = _get_int(request.GET, "year", now.year)
    month = _get_int(request.GET, "month", now.month)
    if month < 1 or month > 12:
        month = now.month

    years = list(range(now.year - 3, now.year + 4))

    groups = (
        Group.objects
        .filter(oqituvchi=teacher, is_archived=False)
        .prefetch_related(
            "enrollments__student",
            "attendances",
        )
    )

    from education.services.historical_finance_service import HistoricalFinanceService
    salary_data = HistoricalFinanceService.calculate_teacher_salary(teacher, year, month, center)
    
    teacher_data = []
    
    for gcd in salary_data['details']:
        # Fetch group object to pass to template (template still uses `group` var)
        group_obj = Group.objects.filter(id=gcd['group_id']).first()
        if not group_obj: continue
        
        enrollments = []
        for en in gcd.get('enrollments', []):
            enrollments.append({
                "student_name": en.get('student_name', 'Noma\'lum'),
                "kurs_narhi": en.get('kurs_narhi', 0),
                "foiz": en.get('foiz', 0),
                "attended": en.get('attended', 0),
                "daromad": en.get('daromad', 0)
            })
            
        teacher_data.append({
            "group": group_obj,
            "enrollments": enrollments,
            "foiz": gcd.get('fi', getattr(teacher, 'oqituvchi_foizi', 0) or group_obj.oqituvchi_foiz),
            "daromad": gcd['salary'],
            "students_count": len(enrollments),
        })

    jami_umumiy_daromad = salary_data['salary']

    return render(request, "education/teacher_groups.html", {
        "teacher": teacher,
        "teacher_data": teacher_data,
        "year": year,
        "month": month,
        "years": years,
        "jami_umumiy_daromad": jami_umumiy_daromad,
        "is_locked": salary_data['is_locked'],
    })


@login_required
def teacher_salary_report(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=group_id)
    
    now = timezone.localdate()
    year = _get_int(request.GET, "year", now.year)
    month = _get_int(request.GET, "month", now.month)
    
    from education.services.historical_finance_service import HistoricalFinanceService
    salary_data = HistoricalFinanceService.calculate_teacher_salary(group.oqituvchi, year, month, center)
    
    student_summaries = []
    teacher_total_income = 0
    
    for gcd in salary_data['details']:
        if gcd['group_id'] == group.id:
            teacher_total_income = gcd['salary']
            for en in gcd.get('enrollments', []):
                student_summaries.append({
                    "student_name": en.get('student_name', 'Noma\'lum'),
                    "attended": en.get('attended', 0),
                    "teacher_income": en.get('daromad', 0)
                })
            break

    ctx = {
        "group": group,
        "student_summaries": student_summaries,
        "teacher_total_income": teacher_total_income,
        "month": month,
        "year": year,
        "is_locked": salary_data['is_locked'],
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
    # 2) O'qituvchilar va ularning hisob-kitobi (Yagona To'g'ri Manba)
    # ================================
    from core.tenant import get_request_center
    center = get_request_center(request)
    
    user_qs = User.objects.filter(role="teacher", is_archived=False)
    if center:
        user_qs = user_qs.filter(center=center)
        
    teachers = user_qs.order_by('ism', 'familya', 'id')

    # ================================
    # Grafik uchun bo'sh massivlar (12 oy)
    # ================================
    chart_teacher_income = [0] * 12
    chart_center_income = [0] * 12
    chart_total_turnover = [0] * 12

    # ================================
    # 3) HISOB-KITOB (HistoricalFinanceService orqali)
    # ================================
    teacher_data = []

    for teacher in teachers:
        yearly_stats = HistoricalFinanceService.get_yearly_teacher_stats(teacher, selected_year, center)
        
        # Hamma oylar bo'yicha markazning umumiy summasini grafik uchun yig'amiz
        for m in range(12):
            chart_teacher_income[m] += yearly_stats[m]['salary']
            chart_center_income[m] += yearly_stats[m]['center_profit']
            chart_total_turnover[m] += yearly_stats[m]['turnover']
            
        # Jadval uchun faqat tanlangan oyni olamiz
        m_stat = yearly_stats[selected_month - 1]
        
        # O'qituvchining nechta guruhi bor?
        groups_count = teacher.group_set.filter(is_archived=False).count()

        teacher_data.append({
            "id": teacher.id,
            "teacher": teacher.get_full_name() or teacher.email,
            "groups": groups_count,
            "lessons": m_stat['lessons'],
            "teacher_income": int(m_stat['salary']),
            "center_profit": int(m_stat['center_profit']),
            "total_turnover": int(m_stat['turnover']),
        })

    # ================================
    # 4) AJAX JSON Response (year/month select o'zgarganda)
    # ================================
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "year": int(selected_year),
            "month": int(selected_month),
            "teacher_data": teacher_data,
            "chart_labels": chart_labels,
            "chart_teacher_income": [float(x) for x in chart_teacher_income],
            "chart_center_income": [float(x) for x in chart_center_income],
            "chart_total_turnover": [float(x) for x in chart_total_turnover],
        })

    # ================================
    # 5) HTML render
    # ================================
    return render(request, "education/teacher_salary_summary.html", {
        "years": list(range(2024, 2036)),
        "months": months,
        "selected_year": int(selected_year),
        "selected_month": int(selected_month),
        "teacher_data": teacher_data,
        "chart_labels": chart_labels,
        "chart_teacher_income": chart_teacher_income,
        "chart_center_income": chart_center_income,
        "chart_total_turnover": chart_total_turnover,
        # Safely pass data as JSON strings
        "teacher_data_json": json.dumps(teacher_data),
        "chart_labels_json": json.dumps(chart_labels),
        "chart_teacher_income_json": json.dumps([float(x) for x in chart_teacher_income]),
        "chart_center_income_json": json.dumps([float(x) for x in chart_center_income]),
        "chart_total_turnover_json": json.dumps([float(x) for x in chart_total_turnover]),
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
    # #  1) Attendance ni to'g'ri olish (DateTimeField fix)
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

    # # Grafiklar uchun 12 oy bo'yicha bo'sh massiv
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

    #                 # Agar dars bo'lmasa → daromad bo'lmaydi
    #                 les = attendance_map.get((group.id, enr.student.id, month_num), 0)

    #                 if les > 0:
    #                     teacher_part = kurs * foiz / 12
    #                     center_part = kurs * (1 - foiz) / 12
    #                     turnover_part = kurs / 12

    #                     m_lessons += les
    #                     m_teacher_income += teacher_part * les
    #                     m_center_profit += center_part * les
    #                     m_turnover += turnover_part * les

    #         # Grafik to'ldirish
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

    # # AJAX so'rovi (fetch)
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

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=group_id)

    date = parse_date(date_str)

    enrollments = Enrollment.objects.filter(group=group, is_active=True)
    forced_count = 0

    for enr in enrollments:
        att, created = Attendance.objects.get_or_create(
            group=group,
            student=enr.student,
            date=date,
            defaults={"present": False}
        )

        # kelgan bo'lsa — forced qilmaymiz
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

    # O'qituvchi bo'lsa — o'z guruhini topadi
    if request.user.role == "teacher":
        group = Group.objects.filter(oqituvchi=request.user).first()

    # Direktor yoki superuser bo'lsa — birinchi mavjud guruhni topadi
    elif request.user.role == "director" or request.user.is_superuser:
        group = Group.objects.first()

    # Agar topilmasa — xabar chiqar va qaytar
    if not group:
        messages.warning(request, "Hech qanday guruh topilmadi!")
        return redirect("education:groups_it")

    # Topilgan guruh bo'yicha maosh sahifasiga yo'naltirish
    return redirect("education:teacher_salary_report", group.id)



# ---------- CRUD ----------
@login_required
def group_create(request, category=None):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo'q.")
        return redirect("education:groups_home")

    if category == Group.LANG:
        FormCls, title = LangGroupForm, "Tillar bo'yicha guruh yaratish"
    elif category == Group.IT:
        FormCls, title = ITGroupForm, "IT bo'yicha guruh yaratish"
    else:
        FormCls, title = GroupForm, "Guruh yaratish"

    from core.tenant import get_request_center
    center = get_request_center(request) or getattr(request.user, "center", None)
    form = FormCls(request.POST or None, center=center)

    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)

        # 🔹 Kategoriya bo'sh bo'lsa, avtomatik to'ldir
        g.category = category or Group.LANG

        # 🔹 Center avtomatik foydalanuvchidan
        if not g.center_id:
            if center:
                g.center = center
            elif hasattr(request.user, "center") and request.user.center:
                g.center = request.user.center
            else:
                from accounts.models import Center
                g.center = Center.objects.first()

        # ✅ Foydalanuvchi kurs narxini kiritgan bo'lsa — o'sha qiymatni saqlaymiz
        if g.kurs_narxi in [None, "", 0]:
            g.kurs_narxi = 500000  # faqat bo'sh bo'lsa default beramiz

        # ✅ O'qituvchi foizi
        if g.oqituvchi and getattr(g.oqituvchi, 'oqituvchi_foizi', None) is not None:
            g.oqituvchi_foiz = g.oqituvchi.oqituvchi_foizi
        elif not g.oqituvchi_foiz:
            g.oqituvchi_foiz = 40

        # ✅ Oylik dars soni
        if not g.oy_dars_soni:
            g.oy_dars_soni = 12

        from education.services.group_schedule_service import apply_group_duration_defaults
        apply_group_duration_defaults(g)
        g.save()
        messages.success(request, f"✅ {g.nom} guruhi muvaffaqiyatli yaratildi.")
        return redirect("education:group_detail", pk=g.pk)

    elif request.method == "POST":
        print("❌ Forma xato:", form.errors)

    return render(request, "education/group_form.html", {"form": form, "title": title})


@login_required
def group_edit(request, pk):
    if not request.user.is_superuser and request.user.role not in ["director", "manager", "teacher"]:
        messages.error(request, "Sizda ruxsat yo'q.")
        return redirect("education:groups")

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

    # Eski qiymatlarni forma o'zgartirmasdan oldin saqlab qolamiz
    old_foiz = g.oqituvchi_foiz
    old_narx = g.kurs_narxi
    old_oqituvchi_id = g.oqituvchi_id

    form = GroupForm(request.POST or None, instance=g, center=center)

    if request.method == "POST" and form.is_valid():
        updated_group = form.save(commit=False)
        
        # Agar o'qituvchi o'zgargan bo'lsa, mos foizni avtomatik olamiz
        if updated_group.oqituvchi and updated_group.oqituvchi_id != old_oqituvchi_id:
            teacher_foiz = getattr(updated_group.oqituvchi, 'oqituvchi_foizi', None)
            if teacher_foiz is not None:
                updated_group.oqituvchi_foiz = teacher_foiz

        from education.services.group_schedule_service import apply_group_duration_defaults
        apply_group_duration_defaults(updated_group)
        updated_group.save()
        
        # Agar guruhning foizi yoki narxi o'zgargan bo'lsa, joriy o'quvchilarga ham ta'sir qilsin
        if updated_group.oqituvchi_foiz != old_foiz or updated_group.kurs_narxi != old_narx:
            from education.models import Enrollment
            enrollments = Enrollment.objects.filter(group=updated_group)
            update_data = {}
            if updated_group.oqituvchi_foiz != old_foiz:
                update_data["oqituvchi_foiz"] = updated_group.oqituvchi_foiz
            if updated_group.kurs_narxi != old_narx:
                update_data["kurs_narhi"] = updated_group.kurs_narxi
                
            if update_data:
                enrollments.update(**update_data)
                
        messages.success(request, "✅ Guruh yangilandi.")
        return redirect("education:group_detail", pk=g.id)

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Guruhni tahrirlash",
        "description": "Guruh ma'lumotlarini tahrirlash",
    })




@login_required
def group_list(request):
    """
    Barcha guruhlar ro'yxati.
    """
    rows = (
        Group.objects
        .select_related("center", "oqituvchi")
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)),
            sana=Coalesce(F("course_start_date"), Cast(F("tuzilgan"), models.DateField()))
        )
        .order_by("-id")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    page_num = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', '10')

    if page_size == "all":
        paginator = Paginator(rows, max(1, rows.count()))
    else:
        try:
            page_size = int(page_size)
            if page_size < 1:
                page_size = 10
        except ValueError:
            page_size = 10
        paginator = Paginator(rows, page_size)

    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    can_manage = request.user.is_superuser or request.user.role in ["director", "manager", "teacher"]

    context = {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_size,
        "can_manage": can_manage,
    }
    return render(request, "education/groups.html", context)

def get_group_price(request, pk):
    try:
        qs = Group.objects.all()
        from core.tenant import get_request_center
        center = get_request_center(request)
        if center:
            qs = qs.filter(center=center)
        group = qs.get(pk=pk)
        return JsonResponse({
            "price": group.kurs_narxi,
            "oqituvchi_foiz": group.oqituvchi_foiz
        })
    except Group.DoesNotExist:
        return JsonResponse({"price": 0})



@login_required
def group_add(request):
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo'q.")
        return redirect("education:groups")

    from core.tenant import get_request_center
    center = get_request_center(request) or getattr(request.user, "center", None)
    form = GroupForm(request.POST or None, center=center)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        if not group.center_id:
            group.center = center

        # O'qituvchi tanlanganda foiz teacher profilidan olinadi.
        if group.oqituvchi and getattr(group.oqituvchi, "oqituvchi_foizi", None) is not None:
            group.oqituvchi_foiz = group.oqituvchi.oqituvchi_foizi
        elif not group.oqituvchi_foiz:
            group.oqituvchi_foiz = 40

        from education.services.group_schedule_service import apply_group_duration_defaults
        apply_group_duration_defaults(group)
        group.save()
        messages.success(request, "✅ Guruh muvaffaqiyatli qo'shildi.")
        return redirect("education:groups")

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Yangi guruh qo'shish",
    })




from django.contrib import messages

@login_required
def group_delete(request, pk):
    """
    Guruhni o'chirish — tasdiq bilan.
    """
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        category = getattr(group, "category_obj", None)
        group.delete()
        messages.success(request, "🗑️ Guruh o'chirildi.")

        if category:
            return redirect("education:category_detail", category_id=category.id)
        return redirect("education:groups")

    return render(request, "education/group_delete_confirm.html", {"group": group})


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
        except:
            student_id = request.POST.get("student_id")

        if not student_id:
            return JsonResponse({"error": "O'quvchi tanlanmagan"}, status=400)

        student = get_object_or_404(User, pk=student_id, role="student", center=target_center)

        # Allaqachon guruhda bormi?
        if Enrollment.objects.filter(group=g, student=student).exists():
            return JsonResponse({
                "status": "warning",
                "message": f"'{student.get_full_name()}' allaqachon '{g.nom}' guruhida bor."
            })

        # Kurs narxini aniqlash (studentning shu markazdagi boshqa guruhidan yoki default guruh narxi)
        existing_enr = Enrollment.objects.filter(student=student, center=target_center).first()
        kurs_narhi = existing_enr.kurs_narhi if existing_enr else g.kurs_narxi

        # Qo'shish (EnrollmentService orqali tarix bilan)
        from education.services.enrollment_service import EnrollmentService
        enr = EnrollmentService.enroll_student(
            student=student,
            group=g,
            kurs_narxi=kurs_narhi,
            oqituvchi_foiz=g.oqituvchi_foiz or 40
        )

        from education.services.tuition import ensure_tuition_month
        from django.utils import timezone
        # ✅ Yangi qo'shilgan o'quvchi avtomatik joriy oy uchn qarzdor bo'lishini ta'minlash
        ensure_tuition_month(enr, timezone.localdate())

        return JsonResponse({
            "status": "success",
            "message": f"'{student.get_full_name()}' muvaffaqiyatli qo'shildi ✅",
            "student": {
                "id": student.id,
                "full_name": student.get_full_name(),
                "phone": student.telefon1 or student.telefon2
            }
        })

    # Standart GET render
    return render(request, "education/add_student_to_group.html", {
        "group": g,
    })



@login_required
def teacher_groups_view(request, teacher_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = User.objects.filter(role="teacher")
    if center:
        qs = qs.filter(center=center)
    teacher = get_object_or_404(qs, id=teacher_id)

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
    # Validate center
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center and att.group.center_id != center.id:
        return JsonResponse({"error": "Center mismatch"}, status=403)

    # Belgini o'zgartiramiz (agar bor bo'lsa)
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


@login_required
def my_groups(request):
    rows = (
        Group.objects.filter(oqituvchi=request.user, is_archived=False)
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments", filter=Q(enrollments__is_active=True, enrollments__is_deleted=False)))
        .order_by("nom")
    )
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        rows = rows.filter(center=center)
    return render(request, "education/my_groups.html", {"rows": rows})


@login_required
def teacher_income_dashboard(request):
    """
    O'qituvchining shaxsiy daromadlari panelini ko'rsatadi.
    Snapshot tizimi yordamida o'tgan oylar ma'lumotlari muzlatilgan (immutable).
    """
    if request.user.role not in ['teacher', 'director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Bu bo'lim ushbu rol uchun emas.")
        return redirect('core:home')
        
    is_admin = request.user.role in ['director', 'manager'] or request.user.is_superuser
    
    # Agar admin bo'lsa va teacher_id berilgan bo'lsa - o'shani ko'ramiz
    teacher_id = request.GET.get('teacher_id')
    if is_admin and teacher_id:
        teacher = get_object_or_404(User, id=teacher_id, role='teacher')
    else:
        teacher = request.user

    today = timezone.localdate()
    selected_year = _get_int(request.GET, "year", today.year)
    selected_month = _get_int(request.GET, "month", today.month)
    
    from core.tenant import get_request_center
    center = get_request_center(request)

    # HistoricalFinanceService orqali ma'lumotlarni olish (snapshot yoki dinamik)
    salary_data = HistoricalFinanceService.calculate_teacher_salary(teacher, selected_year, selected_month, center)
    
    # Get all 12 months for the yearly chart efficiently
    monthly_income = HistoricalFinanceService.get_yearly_teacher_salary(teacher, selected_year, center)
    total_year_income = sum(monthly_income)
    
    # Get daily breakdown for the selected month (now returned by the service)
    _, num_days = calendar.monthrange(selected_year, selected_month)
    daily_income_long = salary_data.get('daily_breakdown', [0] * 31)
    daily_income = daily_income_long[:num_days]

    # Yearly labels for JS
    monthly_labels = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
    daily_labels = [str(i) for i in range(1, num_days + 1)]

    # Selectors options
    years = range(today.year - 2, today.year + 2)
    months_list = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
        (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
        (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr")
    ]

    ctx = {
        'teacher': teacher,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'salary_data': salary_data,
        'daily_income': daily_income,
        'monthly_income': monthly_income,
        'total_year_income': total_year_income,
        'daily_labels': daily_labels,
        'monthly_labels': monthly_labels,
        'years': years,
        'months_list': months_list,
        'is_locked': salary_data.get('is_locked', False),
        'is_admin': is_admin,
    }
    
    if is_admin:
        ctx['teachers_list'] = User.objects.filter(role='teacher', is_active=True)
    
    return render(request, "education/teacher_income_dashboard.html", ctx)


@login_required
def close_finance_month_view(request):
    """View to close (lock) or open (unlock) a financial month for a center."""
    if request.user.role not in ['director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda bu bo'limga ruxsat yo'q.")
        return redirect('education:teacher_income_dashboard')

    if request.method == "POST":
        year = int(request.POST.get('year'))
        month = int(request.POST.get('month'))
        action = request.POST.get('action', 'lock')
        
        from core.tenant import get_request_center
        center = get_request_center(request)
        
        if action == 'unlock':
            HistoricalFinanceService.open_month(center, year, month, request.user)
            messages.success(request, f"{year}-yil {month}-oy muvaffaqiyatli ochildi. Endi oyliklar avtomatik (jonli) tarzda hisoblanadi.")
        else:
            HistoricalFinanceService.close_month(center, year, month, request.user)
            messages.success(request, f"{year}-yil {month}-oy muvaffaqiyatli yopildi va qotirildi. Endi o'zgarishlar tasir qilmaydi.")
        
    return redirect(f"{reverse('education:teacher_salary_list')}?year={year}&month={month}")

@login_required
def fix_all_incomes(request):
    """
    Global/Production muhitda o'tgan oydagi eski Attendance malumotlarini 
    TeacherIncome tizimiga generator qilib beruvchi bir martalik master funktsiya
    """
    from education.models import Attendance, TeacherIncome, Enrollment
    from django.db import transaction
    
    all_attendances = Attendance.objects.all().select_related('group', 'student', 'teacher', 'group__center')
    
    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for i, att in enumerate(all_attendances):
            # 1. To'lanadigan holatmi?
            is_billable = att.status == 'present' or att.status == 'absent_unexcused' or getattr(att, 'forced', False) or getattr(att, 'present', False)

            if not is_billable:
                TeacherIncome.objects.filter(attendance=att).delete()
                continue
            
            # 2. Enrollmentni topish
            enrollment = Enrollment.all_objects.filter(
                group=att.group,
                student=att.student
            ).order_by('-is_active', '-created_at').first()

            if not enrollment:
                TeacherIncome.objects.filter(attendance=att).delete()
                continue

            teacher = att.group.oqituvchi if att.group else None
            if not teacher:
                continue

            foiz = getattr(teacher, 'oqituvchi_foizi', 0)
            if foiz is None or foiz == 0:
                foiz = enrollment.oqituvchi_foiz
                
            kurs_narhi = enrollment.kurs_narhi or 0
            
            oy_dars_soni = att.group.oy_dars_soni or 12
            if oy_dars_soni <= 0: oy_dars_soni = 12

            if kurs_narhi > 0 and foiz > 0:
                total_per_lesson = kurs_narhi / oy_dars_soni
                amount = round(total_per_lesson * (foiz / 100))
                center_amount = round(total_per_lesson * ((100 - foiz) / 100))
                total_amount = round(total_per_lesson)
            else:
                amount = 0
                center_amount = 0
                total_amount = 0

            obj, created = TeacherIncome.objects.update_or_create(
                attendance=att,
                defaults={
                    'center': att.center or (att.group.center if att.group else None),
                    'teacher': teacher,
                    'group': att.group,
                    'amount': amount,
                    'center_amount': center_amount,
                    'total_amount': total_amount
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1

    messages.success(request, f"🚀 Barcha daromadlar qayta hisoblandi! Yangi tizim qo'llandi. Yaratildi: {created_count}, Yangilandi: {updated_count}.")
    return redirect('education:teacher_income_dashboard')


# =============================================================================
# PHASE 1: Exam foundation module (backward-compatible, non-blocking)
# =============================================================================


def _director_or_manager(user):
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager")


def _teacher_can_view_settings(user):
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager", "teacher")


def _teacher_or_management_can_access_group(user, group: Group):
    if user.is_superuser or getattr(user, "role", None) in ("director", "manager"):
        return True
    return getattr(user, "role", None) == "teacher" and group.oqituvchi_id == user.id


def _decode_exam_session_note(raw_text: str) -> dict:
    """
    Backward-compatible parser:
    - yangi format: {"task": "...", "comment": "..."} (JSON)
    - eski format: oddiy text (task sifatida olinadi)
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {"task": "", "comment": ""}
    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            return {
                "task": (payload.get("task") or "").strip(),
                "comment": (payload.get("comment") or "").strip(),
            }
    except Exception:
        pass
    return {"task": raw_text, "comment": ""}


def _encode_exam_session_note(task: str, comment: str) -> str:
    task = (task or "").strip()
    comment = (comment or "").strip()
    if not task and not comment:
        return ""
    return json.dumps({"task": task, "comment": comment}, ensure_ascii=False)


@login_required
def exam_settings_view(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")

    if not _teacher_can_view_settings(request.user):
        return HttpResponseForbidden("Sizda bu bo'limga ruxsat yo'q.")

    from .forms import CenterExamSettingForm
    from education.services.exam_service import get_or_create_center_exam_settings

    settings_obj = get_or_create_center_exam_settings(center)
    can_edit = _director_or_manager(request.user)
    form = CenterExamSettingForm(request.POST or None, instance=settings_obj)

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Teacher bu sozlamalarni o'zgartira olmaydi.")
        if form.is_valid():
            obj = form.save(commit=False)
            obj.center = center
            obj.updated_by = request.user
            obj.save()
            from education.services.audit_service import log_education_event
            log_education_event(
                center=center,
                actor=request.user,
                action_type="director_settings_change",
                entity=obj,
                message="Exam settings updated",
            )
            messages.success(request, "Imtihon sozlamalari saqlandi.")
            return redirect("education:exam_settings")

    return render(
        request,
        "education/exam_settings.html",
        {"form": form, "settings_obj": settings_obj, "can_edit": can_edit},
    )


@login_required
@require_POST
def exam_reminder_action(request, group_id: int):
    from core.tenant import get_request_center
    center = get_request_center(request)

    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    from education.models import ExamReminderLog
    from education.services.exam_service import (
        create_or_get_exam_session_from_reminder,
        create_or_update_exam_session_decision,
        get_exam_reminder_state,
        log_exam_reminder_action,
    )

    action = (request.POST.get("action") or "").strip().lower()
    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    note = (request.POST.get("note") or "").strip()

    if action not in {ExamReminderLog.ACTION_YES, ExamReminderLog.ACTION_NO, ExamReminderLog.ACTION_LATER}:
        messages.error(request, "Noto'g'ri action.")
        return redirect("education:group_detail", pk=group.id)

    reminder_state = get_exam_reminder_state(group=group, on_date=selected_date)
    target_checkpoint = int(reminder_state.get("target_lesson_number") or 0)

    if action == ExamReminderLog.ACTION_YES:
        if not reminder_state.get("enabled"):
            messages.info(request, "Imtihon tizimi o'chiq. Sozlamani director yoqishi kerak.")
            return redirect("education:group_detail", pk=group.id)
        if not reminder_state.get("due"):
            messages.info(request, "Hozircha majburiy imtihon darsi emas, lekin davomat davom etadi.")
            return redirect("education:group_detail", pk=group.id)
        session = create_or_get_exam_session_from_reminder(
            group=group,
            teacher=request.user,
            attendance_date=selected_date,
            created_by=request.user,
            decision_note=note,
            lesson_number_reference=target_checkpoint or reminder_state.get("target_lesson_number"),
        )
        messages.success(request, "Imtihon sessiyasi ochildi. Natijalarni kiriting.")
        return redirect("education:exam_session_entry", session_id=session.id)

    if not reminder_state.get("enabled"):
        messages.info(request, "Imtihon tizimi o'chiq. Sozlamani director yoqishi kerak.")
        return redirect("education:group_detail", pk=group.id)
    if not reminder_state.get("due"):
        messages.info(request, "Hozircha bu nazorat bosqichi bo'yicha amal talab qilinmaydi.")
        return redirect("education:group_detail", pk=group.id)

    decision_session = create_or_update_exam_session_decision(
        group=group,
        teacher=request.user,
        attendance_date=selected_date,
        actor=request.user,
        decision=action,
        decision_note=note,
        lesson_number_reference=target_checkpoint,
    )

    log_exam_reminder_action(
        group=group,
        teacher=request.user,
        action=action,
        attendance_date=selected_date,
        note=note,
        metadata={
            "session_id": decision_session.id,
            "target_checkpoint": target_checkpoint,
        },
    )
    if action == ExamReminderLog.ACTION_NO:
        messages.warning(request, "Imtihon o'tkazilmagan deb qayd etildi.")
    else:
        messages.info(request, "Imtihon eslatmasi keyinroq uchun saqlandi.")
    return redirect("education:group_detail", pk=group.id)


@login_required
def exam_session_entry(request, session_id: int):
    from core.tenant import get_request_center
    center = get_request_center(request)
    from .forms import ExamResultRowForm
    from education.models import ExamSession, ExamResult
    from education.services.exam_service import (
        get_exam_session_progress,
        get_or_create_center_exam_settings,
        save_exam_session_task_files,
        save_exam_results_batch,
    )

    qs = ExamSession.objects.select_related("group", "teacher", "center").prefetch_related("task_files")
    if center:
        qs = qs.filter(center=center)
    session = get_object_or_404(qs, pk=session_id)

    if not _teacher_or_management_can_access_group(request.user, session.group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    settings_obj = get_or_create_center_exam_settings(session.center)
    enrollments = (
        Enrollment.objects.filter(group=session.group, is_active=True)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )
    existing_results = {
        r.student_id: r
        for r in ExamResult.objects.filter(session=session).select_related("student")
    }
    for enr in enrollments:
        enr.existing_result = existing_results.get(enr.student_id)

    parsed_note = _decode_exam_session_note(session.decision_note)
    session_task_default = parsed_note["task"]
    session_comment_default = parsed_note["comment"]

    if request.method == "POST":
        session_task = (request.POST.get("session_task") or "").strip()
        session_comment = (request.POST.get("session_comment") or "").strip()
        session_note = _encode_exam_session_note(session_task, session_comment)
        if session.decision_note != session_note:
            session.decision_note = session_note
            session.updated_by = request.user
            session.save(update_fields=["decision_note", "updated_by", "updated_at"])

        session_task_default = session_task
        session_comment_default = session_comment

        uploaded_task_file_count = 0
        session_task_files = request.FILES.getlist("session_task_files") or []
        if session_task_files and settings_obj.exam_file_upload_enabled:
            try:
                uploaded_task_file_count = save_exam_session_task_files(
                    session=session,
                    actor=request.user,
                    files=session_task_files,
                )
                if uploaded_task_file_count:
                    messages.success(request, f"{uploaded_task_file_count} ta umumiy task fayli yuklandi.")
            except ValueError as exc:
                messages.error(request, str(exc))
        elif session_task_files and not settings_obj.exam_file_upload_enabled:
            messages.warning(request, "Task fayl yuklash markaz sozlamasida o'chiq.")

        rows = []
        row_errors = []
        for enr in enrollments:
            sid = enr.student_id
            existing_result = existing_results.get(sid)
            work_files = request.FILES.getlist(f"work_files_{sid}") or []
            task_files = request.FILES.getlist(f"task_files_{sid}") or []
            result_value = (request.POST.get(f"result_{sid}", "") or "").strip()
            legacy_percent = (request.POST.get(f"percent_{sid}", "") or "").strip()
            legacy_score = (request.POST.get(f"score_{sid}", "") or "").strip()
            if not result_value:
                result_value = legacy_percent or legacy_score
            row_teacher_comment = (request.POST.get(f"teacher_comment_{sid}") or "").strip() or session_comment
            row_assignment = (request.POST.get(f"assignment_description_{sid}") or "").strip() or session_task

            has_any_input = bool(result_value or work_files or task_files)
            if not has_any_input:
                continue
            if existing_result is None and not result_value:
                continue

            # Ball yozilmasa, mavjud qiymatni o'chirib yubormaslik uchun oldingi qiymatni saqlaymiz.
            effective_value = result_value
            if not effective_value and existing_result:
                if existing_result.percent is not None:
                    effective_value = str(existing_result.percent)
                elif existing_result.score is not None:
                    effective_value = str(existing_result.score)

            row_form = ExamResultRowForm(
                {
                    "score": effective_value,
                    "percent": effective_value,
                    "teacher_comment": row_teacher_comment,
                    "assignment_description": row_assignment,
                    "absent_in_exam": False,
                    "retake_recommended": bool(request.POST.get(f"retake_{sid}")),
                },
                require_result=settings_obj.exam_result_required,
            )
            if not row_form.is_valid():
                row_errors.append((enr.student.get_full_name(), row_form.errors.as_text()))
                continue
            rows.append(
                {
                    "student": enr.student,
                    "score": row_form.cleaned_data.get("score"),
                    "percent": row_form.cleaned_data.get("percent"),
                    "teacher_comment": row_form.cleaned_data.get("teacher_comment"),
                    "assignment_description": row_form.cleaned_data.get("assignment_description"),
                    "absent_in_exam": row_form.cleaned_data.get("absent_in_exam"),
                    "retake_recommended": row_form.cleaned_data.get("retake_recommended"),
                    "work_files": work_files,
                    "task_files": task_files,
                }
            )

        if row_errors:
            for student_name, err in row_errors:
                messages.error(request, f"{student_name}: {err}")
        elif not rows and not uploaded_task_file_count:
            messages.info(request, "Hozircha saqlash uchun yangi natija yo'q.")
        else:
            try:
                saved_count = save_exam_results_batch(
                    session=session,
                    actor=request.user,
                    rows=rows,
                )
                messages.success(request, f"{saved_count} ta o'quvchi bo'yicha imtihon natijalari saqlandi.")
                return redirect("education:exam_session_entry", session_id=session.id)
            except ValueError as exc:
                messages.error(request, str(exc))

    session_progress = get_exam_session_progress(session=session)

    return render(
        request,
        "education/exam_session_entry.html",
        {
            "session": session,
            "group": session.group,
            "enrollments": enrollments,
            "existing_results": existing_results,
            "exam_settings": settings_obj,
            "session_task_default": session_task_default,
            "session_comment_default": session_comment_default,
            "session_progress": session_progress,
        },
    )


@login_required
def group_exam_history(request, group_id: int):
    from core.tenant import get_request_center
    from education.models import ExamSession

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    sessions = ExamSession.objects.filter(group=group).select_related("teacher", "created_by").order_by("-exam_date", "-id")
    status_filter = (request.GET.get("status") or "").strip()
    if status_filter in {ExamSession.STATUS_DRAFT, ExamSession.STATUS_COMPLETED, ExamSession.STATUS_CANCELLED}:
        sessions = sessions.filter(status=status_filter)

    return render(
        request,
        "education/group_exam_history.html",
        {
            "group": group,
            "sessions": sessions,
            "status_filter": status_filter,
        },
    )


@login_required
def teacher_exam_history(request):
    from core.tenant import get_request_center
    from education.models import ExamSession

    center = get_request_center(request)
    role = getattr(request.user, "role", None)
    if not request.user.is_superuser and role not in ("director", "manager", "teacher"):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    sessions = ExamSession.objects.select_related("group", "teacher", "center").order_by("-exam_date", "-id")
    if center:
        sessions = sessions.filter(center=center)

    if role == "teacher" and not request.user.is_superuser:
        sessions = sessions.filter(teacher=request.user)
    else:
        teacher_id = _get_int(request.GET, "teacher", 0)
        if teacher_id:
            sessions = sessions.filter(teacher_id=teacher_id)

    group_id = _get_int(request.GET, "group", 0)
    if group_id:
        sessions = sessions.filter(group_id=group_id)

    back_group_id = _get_int(request.GET, "back_group", 0)
    if not back_group_id and group_id:
        back_group_id = group_id

    date_from = parse_date(request.GET.get("date_from") or "")
    date_to = parse_date(request.GET.get("date_to") or "")
    if date_from:
        sessions = sessions.filter(exam_date__gte=date_from)
    if date_to:
        sessions = sessions.filter(exam_date__lte=date_to)

    teachers = User.objects.filter(role="teacher", center=center).order_by("ism", "familya") if center else User.objects.none()
    groups = Group.objects.filter(center=center).order_by("nom") if center else Group.objects.none()
    return render(
        request,
        "education/teacher_exam_history.html",
        {
            "sessions": sessions,
            "teachers": teachers,
            "groups": groups,
            "back_group_id": back_group_id,
            "filters": {
                "teacher": _get_int(request.GET, "teacher", 0),
                "group": group_id,
                "back_group": back_group_id,
                "date_from": date_from.isoformat() if date_from else "",
                "date_to": date_to.isoformat() if date_to else "",
            },
        },
    )


@login_required
def exam_session_detail(request, session_id: int):
    from core.tenant import get_request_center
    from education.models import ExamResult, ExamSession

    center = get_request_center(request)
    qs = ExamSession.objects.select_related("group", "teacher", "center")
    if center:
        qs = qs.filter(center=center)
    session = get_object_or_404(qs, pk=session_id)

    if not _teacher_or_management_can_access_group(request.user, session.group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    results = (
        ExamResult.objects.filter(session=session)
        .select_related("student", "teacher")
        .prefetch_related("files")
        .order_by("student__ism", "student__familya")
    )

    return render(
        request,
        "education/exam_session_detail.html",
        {
            "session": session,
            "group": session.group,
            "results": results,
        },
    )


@login_required
def failed_students_list(request):
    from core.tenant import get_request_center
    from .forms import ExamResultFollowUpForm
    from education.models import CertificateRecord, ExamResult
    from education.services.audit_service import log_education_event

    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    center = get_request_center(request)
    qs = ExamResult.objects.select_related("student", "group", "teacher", "session")
    if center:
        qs = qs.filter(center=center)
    qs = qs.filter(passed=False)

    group_id = _get_int(request.GET, "group", 0)
    teacher_id = _get_int(request.GET, "teacher", 0)
    date_from = parse_date(request.GET.get("date_from") or "")
    date_to = parse_date(request.GET.get("date_to") or "")
    percent_min = request.GET.get("percent_min")
    percent_max = request.GET.get("percent_max")
    follow_up_status = (request.GET.get("follow_up_status") or "").strip()
    follow_up_pending = (request.GET.get("follow_up_pending") or "").strip().lower() in {"1", "true", "yes", "on"}

    if group_id:
        qs = qs.filter(group_id=group_id)
    if teacher_id:
        qs = qs.filter(teacher_id=teacher_id)
    if date_from:
        qs = qs.filter(exam_date__gte=date_from)
    if date_to:
        qs = qs.filter(exam_date__lte=date_to)
    if percent_min not in (None, ""):
        try:
            qs = qs.filter(percent__gte=Decimal(str(percent_min)))
        except Exception:
            pass
    if percent_max not in (None, ""):
        try:
            qs = qs.filter(percent__lte=Decimal(str(percent_max)))
        except Exception:
            pass
    valid_follow_statuses = {choice[0] for choice in ExamResult.FOLLOW_UP_CHOICES}
    if follow_up_status in valid_follow_statuses:
        qs = qs.filter(follow_up_status=follow_up_status)
    if follow_up_pending:
        qs = qs.filter(follow_up_status=ExamResult.FOLLOW_UP_PENDING)

    if request.method == "POST":
        result_id = _get_int(request.POST, "result_id", 0)
        result = get_object_or_404(qs, pk=result_id)
        follow_form = ExamResultFollowUpForm(request.POST, instance=result)
        if follow_form.is_valid():
            updated = follow_form.save(commit=False)
            updated.follow_up_updated_by = request.user
            updated.follow_up_updated_at = timezone.now()
            updated.save(update_fields=["follow_up_status", "follow_up_note", "follow_up_updated_by", "follow_up_updated_at", "updated_at"])
            log_education_event(
                center=updated.center,
                actor=request.user,
                action_type="exam_followup_updated",
                entity=updated,
                payload={"follow_up_status": updated.follow_up_status},
            )
            messages.success(request, "Nazorat holati yangilandi.")
        else:
            messages.error(request, "Nazorat formasi xato.")
        q = request.META.get("QUERY_STRING")
        return redirect(f"{request.path}?{q}" if q else request.path)

    rows = qs.order_by("-exam_date", "-id")
    groups = Group.objects.filter(center=center).order_by("nom") if center else Group.objects.none()
    teachers = User.objects.filter(role="teacher", center=center).order_by("ism", "familya") if center else User.objects.none()
    follow_up_choices = ExamResult.FOLLOW_UP_CHOICES

    return render(
        request,
        "education/failed_students_list.html",
        {
            "rows": rows,
            "groups": groups,
            "teachers": teachers,
            "follow_up_choices": follow_up_choices,
            "filters": {
                "group": group_id,
                "teacher": teacher_id,
                "date_from": date_from.isoformat() if date_from else "",
                "date_to": date_to.isoformat() if date_to else "",
                "percent_min": percent_min or "",
                "percent_max": percent_max or "",
                "follow_up_status": follow_up_status,
                "follow_up_pending": follow_up_pending,
            },
        },
    )


@login_required
def group_internal_ranking(request, group_id: int):
    from core.tenant import get_request_center
    from education.services.ranking_service import INTERNAL_RANKING_WEIGHTS, build_group_internal_ranking

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    selected_date = parse_date(request.GET.get("date") or "") or localdate()
    rows = build_group_internal_ranking(
        group=group,
        on_date=selected_date,
        actor=request.user,
        persist=True,
    )

    return render(
        request,
        "education/group_internal_ranking.html",
        {
            "group": group,
            "selected_date": selected_date,
            "rows": rows,
            "weights": INTERNAL_RANKING_WEIGHTS,
        },
    )


@login_required
def group_completion_recommendations(request, group_id: int):
    from core.tenant import get_request_center
    from education.services.ranking_service import build_group_completion_recommendations

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    selected_date = parse_date(request.GET.get("date") or "") or localdate()
    recommendation_payload = build_group_completion_recommendations(
        group=group,
        on_date=selected_date,
        actor=request.user,
        persist=True,
    )
    rows = recommendation_payload["rows"]
    selected_status = (request.GET.get("status") or "").strip()
    valid_statuses = {"eligible", "needs_review", "not_eligible"}
    if selected_status in valid_statuses:
        rows = [row for row in rows if row["completion_recommendation"] == selected_status]

    days_to_estimated_end = None
    days_to_estimated_end_abs = None
    if group.estimated_end_date:
        days_to_estimated_end = (group.estimated_end_date - selected_date).days
        days_to_estimated_end_abs = abs(days_to_estimated_end)

    return render(
        request,
        "education/group_completion_recommendations.html",
        {
            "group": group,
            "selected_date": selected_date,
            "rows": rows,
            "thresholds": recommendation_payload["thresholds"],
            "selected_status": selected_status,
            "days_to_estimated_end": days_to_estimated_end,
            "days_to_estimated_end_abs": days_to_estimated_end_abs,
        },
    )


@login_required
@require_POST
def group_closure_action(request, group_id: int):
    from core.tenant import get_request_center
    from education.services.closure_service import apply_group_closure_action

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    action = (request.POST.get("action") or "").strip().lower()
    if action not in {"yes", "no", "later"}:
        messages.error(request, "Noto'g'ri action.")
        return redirect("education:group_detail", pk=group.id)

    if action == "yes" and not _director_or_manager(request.user):
        return HttpResponseForbidden("Guruhni yopish faqat director/manager uchun ruxsat etilgan.")

    selected_date = parse_date(request.POST.get("date") or "") or localdate()
    note = (request.POST.get("note") or "").strip()

    workflow = apply_group_closure_action(
        group=group,
        actor=request.user,
        action=action,
        on_date=selected_date,
        note=note,
    )

    if workflow.status == workflow.STATUS_CLOSED:
        messages.success(request, "Guruhni yopish jarayoni yakunlandi. Tarixiy ma'lumotlar saqlandi.")
    elif workflow.status == workflow.STATUS_CONTINUE:
        messages.info(request, "Guruh davom etadi. Attendance va payment flow o'zgarmaydi.")
    else:
        messages.info(request, "Closure eslatmasi keyinga qoldirildi.")
    return redirect("education:group_detail", pk=group.id)


@login_required
def certificate_templates_view(request):
    from core.tenant import get_request_center
    from .forms import CertificateTemplateForm
    from education.models import CertificateTemplate
    from education.services.audit_service import log_education_event

    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")

    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    form = CertificateTemplateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.center = center
        obj.uploaded_by = request.user
        obj.save()
        if obj.is_active:
            CertificateTemplate.objects.filter(center=center, template_type=obj.template_type).exclude(pk=obj.pk).update(
                is_active=False
            )
        log_education_event(
            center=center,
            actor=request.user,
            action_type="certificate_template_uploaded",
            entity=obj,
            payload={"template_type": obj.template_type},
        )
        messages.success(request, "Shablon saqlandi.")
        return redirect("education:certificate_templates")

    templates = CertificateTemplate.objects.filter(center=center).order_by("-updated_at")
    return render(
        request,
        "education/certificate_templates.html",
        {
            "form": form,
            "templates": templates,
        },
    )


@login_required
@require_POST
def certificate_template_activate(request, template_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateTemplate
    from education.services.audit_service import log_education_event

    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    center = get_request_center(request)
    qs = CertificateTemplate.objects.all()
    if center:
        qs = qs.filter(center=center)
    template = get_object_or_404(qs, pk=template_id)

    CertificateTemplate.objects.filter(center=template.center, template_type=template.template_type).update(is_active=False)
    template.is_active = True
    template.save(update_fields=["is_active", "updated_at"])

    log_education_event(
        center=template.center,
        actor=request.user,
        action_type="certificate_template_activated",
        entity=template,
        payload={"template_type": template.template_type},
    )
    messages.success(request, "Shablon faol qilib belgilandi.")
    return redirect("education:certificate_templates")


@login_required
def group_certificate_candidates(request, group_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateRecord
    from education.services.ranking_service import build_group_completion_recommendations

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    selected_date = parse_date(request.GET.get("date") or "") or localdate()
    recommendation_payload = build_group_completion_recommendations(
        group=group,
        on_date=selected_date,
        actor=request.user,
        persist=True,
    )
    rows = recommendation_payload["rows"]
    existing_certs = {
        cert.student_id: cert
        for cert in CertificateRecord.objects.filter(group=group, status=CertificateRecord.STATUS_ISSUED).select_related(
            "student"
        )
    }
    for row in rows:
        row["certificate"] = existing_certs.get(row["student"].id)

    return render(
        request,
        "education/group_certificate_candidates.html",
        {
            "group": group,
            "selected_date": selected_date,
            "rows": rows,
            "thresholds": recommendation_payload["thresholds"],
            "can_issue": _director_or_manager(request.user),
        },
    )


@login_required
@require_POST
def issue_certificate_action(request, group_id: int, student_id: int):
    from core.tenant import get_request_center
    from .forms import CertificateIssueForm
    from education.services.certificate_service import issue_certificate_for_student

    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)
    student = get_object_or_404(User.objects.filter(role="student"), pk=student_id)

    if not Enrollment.objects.filter(group=group, student=student, is_active=True).exists():
        return HttpResponseForbidden("Student bu guruhda faol emas.")

    form = CertificateIssueForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Sertifikat berish formasi xato.")
        return redirect("education:group_certificate_candidates", group_id=group.id)

    cert = issue_certificate_for_student(
        group=group,
        student=student,
        actor=request.user,
        certificate_type=form.cleaned_data["certificate_type"],
        note=form.cleaned_data.get("note", ""),
        request=request,
    )
    messages.success(request, f"Sertifikat yaratildi: {cert.certificate_number}")
    return redirect("education:certificate_detail", certificate_id=cert.id)


@login_required
def certificate_detail(request, certificate_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateRecord
    from education.services.certificate_service import user_can_view_certificate

    center = get_request_center(request)
    qs = CertificateRecord.objects.select_related("group", "student", "center", "template", "summary")
    if center:
        qs = qs.filter(center=center)
    cert = get_object_or_404(qs, pk=certificate_id)

    if not user_can_view_certificate(request.user, cert):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    return render(
        request,
        "education/certificate_detail.html",
        {
            "cert": cert,
        },
    )


@login_required
def certificate_download_pdf(request, certificate_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateRecord
    from education.services.certificate_service import (
        PDF_LAYOUT_VERSION,
        regenerate_certificate_pdf,
        user_can_view_certificate,
    )

    center = get_request_center(request)
    qs = CertificateRecord.objects.select_related("group", "student", "center", "summary")
    if center:
        qs = qs.filter(center=center)
    cert = get_object_or_404(qs, pk=certificate_id)

    if not user_can_view_certificate(request.user, cert):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    metadata = cert.metadata if isinstance(cert.metadata, dict) else {}
    layout_version = metadata.get("pdf_layout_version")
    if (not cert.pdf_file) or layout_version != PDF_LAYOUT_VERSION:
        cert = regenerate_certificate_pdf(record=cert, request=request)

    cert.pdf_file.open("rb")
    return FileResponse(
        cert.pdf_file,
        as_attachment=True,
        filename=f"{cert.certificate_number}.pdf",
        content_type="application/pdf",
    )


def certificate_verify(request, certificate_number: str):
    from education.models import CertificateRecord
    from education.services.certificate_service import record_verification_hit

    cert = get_object_or_404(
        CertificateRecord.objects.select_related("group", "student", "center"),
        certificate_number=certificate_number,
    )

    record_verification_hit(record=cert, request=request)
    return render(
        request,
        "education/certificate_verify.html",
        {
            "cert": cert,
        },
    )


@login_required
def student_exam_report(request, student_id: int):
    from core.tenant import get_request_center
    center = get_request_center(request)
    student = get_object_or_404(User.objects.filter(role="student"), pk=student_id)

    viewer = request.user
    if viewer.role == "student" and viewer.id != student.id:
        return HttpResponseForbidden("Siz faqat o'zingizning natijangizni ko'ra olasiz.")
    if viewer.role == "parent" and student not in viewer.children.all():
        return HttpResponseForbidden("Siz faqat farzandingizning natijalarini ko'ra olasiz.")
    if viewer.role == "teacher":
        teaches_student = Enrollment.objects.filter(
            student=student,
            group__oqituvchi=viewer,
            is_active=True,
        ).exists()
        if not teaches_student:
            return HttpResponseForbidden("Siz bu o'quvchining natijasini ko'ra olmaysiz.")
    if viewer.role not in ("student", "parent", "teacher", "director", "manager") and not viewer.is_superuser:
        return HttpResponseForbidden("Ruxsat yo'q.")

    from education.models import ExamResult
    from education.services.exam_service import get_student_exam_summary
    from education.services.ranking_service import get_student_academic_summaries

    qs = ExamResult.objects.select_related("group", "teacher", "session").filter(student=student)
    if center:
        qs = qs.filter(center=center)
    certificate_qs = CertificateRecord.objects.select_related("group", "center").filter(student=student)
    if center:
        certificate_qs = certificate_qs.filter(center=center)

    summary = get_student_exam_summary(student=student)
    academic_summaries = get_student_academic_summaries(student=student, center=center)
    return render(
        request,
        "education/student_exam_report.html",
        {
            "student": student,
            "results": qs.order_by("-exam_date", "-id"),
            "summary": summary,
            "academic_summaries": academic_summaries,
            "certificates": certificate_qs.order_by("-created_at", "-id"),
        },
    )
