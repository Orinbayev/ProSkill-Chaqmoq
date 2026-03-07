from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
# from multiprocessing import Value 
from django.db import models

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Count, F, Min, Max, Prefetch, Q, Sum, OuterRef, Subquery
)
from django.db.models.functions import Coalesce, TruncMonth
from django.http import (
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
    Dars,
    Enrollment,
    Group,
    OylikHisobot,
    Payment,
    PaymentAllocation,
    Student,           # agar sizda bor bo‘lsa; bo‘lmasa o‘chirib tashlang
    TuitionMonth,
)
from accounts.models import Center
from .permissions import user_can_manage_payments
from django.db import transaction
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractDay  # student_detail dagi underline ham yo‘qoladi
from urllib.parse import urlparse, parse_qs
from django.db import transaction
from urllib.parse import urlparse, parse_qs, unquote
from django.urls import reverse  # sizda reverse ishlatyapsiz, import yo‘q
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


def _attendance_adjust_rule():
    """
    Davomat OFF bo‘lganda, o‘sha kundagi ballarni 'bekor qilish' uchun
    maxsus Rule kerak bo‘ladi. (DBga 1 marta tushadi)
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

        # 1) eng to‘g‘risi: month=YYYY-MM
        m = (qs.get("month", [""])[0] or "").strip()
        if m:
            return parse_month_str(m) or fallback

        # 2) sizda ishlayotgan variant: pay_month=1..12
        pm = (qs.get("pay_month", [""])[0] or "").strip()
        if pm.isdigit():
            mm = int(pm)
            if 1 <= mm <= 12:
                # year bo‘lmasa joriy yil
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

#     # fee 0 bo‘lib qolsa fallback
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
#     Payment yaratadi va pullarni TuitionMonth’larga ketma-ket taqsimlaydi:
#     start_month -> keyingi oylar...
#     """
#     start_month = month_first_day(start_month or timezone.localdate())
#     total = int(cash_amount or 0) + int(card_amount_som or 0)

#     if total <= 0:
#         raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas.")

#     # Payment create (fieldlar turlicha bo‘lishi mumkin)
#     kwargs = {}
#     if _model_has_field(Payment, "enrollment"):
#         kwargs["enrollment"] = enrollment
#     if _model_has_field(Payment, "student"):
#         kwargs["student"] = enrollment.student
#     if _model_has_field(Payment, "group"):
#         kwargs["group"] = enrollment.group

#     if _model_has_field(Payment, "cash_amount"):
#         kwargs["cash_amount"] = int(cash_amount or 0)

#     # kartani ba’zi loyihalarda card_amount_som, ba’zida card_amount
#     if _model_has_field(Payment, "card_amount_som"):
#         kwargs["card_amount_som"] = int(card_amount_som or 0)
#     elif _model_has_field(Payment, "card_amount"):
#         kwargs["card_amount"] = int(card_amount_som or 0)

#     if _model_has_field(Payment, "summa"):
#         kwargs["summa"] = total

#     if _model_has_field(Payment, "paid_at"):
#         kwargs["paid_at"] = timezone.now()
#     else:
#         # eski fieldlar bo‘lsa
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

#     # 60 oy max (cheksiz loop bo‘lmasin)
#     for _ in range(60):
#         tm = ensure_tuition_month(enrollment, cur)
#         fee = int(getattr(tm, "fee_amount", 0) or 0)

#         # fee 0 bo‘lsa — keyingi oyga o‘tamiz
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

#     # Enrollment jami_tolangan update (agar field bo‘lsa)
#     if _model_has_field(Enrollment, "jami_tolangan"):
#         Enrollment.objects.filter(pk=enrollment.pk).update(
#             jami_tolangan=Coalesce(F("jami_tolangan"), 0) + total
#         )

#     return p

@require_POST
@login_required
def create_payment(request):
    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo‘q.")
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
            messages.success(request, f"✅ {enrollment.student.get_full_name()} uchun to‘lov saqlandi!")
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
            messages.error(request, "O‘quvchida faol kurslar topilmadi.")
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
            
            messages.success(request, f"✅ {student.get_full_name()} uchun umumiy to‘lov saqlandi!")
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
        messages.error(request, "Ruxsat yo‘q.")
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
        enr.delete()
        messages.success(request, f"🗑️ {student_name} ({group_name}) guruhdan o‘chirildi.")
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
    # nom: qolganlari nom bo‘yicha
    groups = groups.order_by(
        "-has_attendance",
        F("last_attendance").desc(nulls_last=True),
        "nom"
    )

    # ✅ Statistikalar (tepada ko‘rsatish uchun)
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
            elif getattr(a, "forced", False):
                status = "forced"
                forced_count += 1
            else:
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

    return render(request, "education/group_month_attendance.html", {
        "group": group,
        "rows": rows,
        "days": day_list,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "years": years,
        "months": months,
    })


# ==========================================
#  QARZDORLAR (YOZILAYOTGAN YANGI PAGE)
# ==========================================

@login_required
def qarzdorlar_home(request):
    from core.tenant import get_request_center

    if not user_can_manage_payments(request.user):
        messages.error(request, "Ruxsat yo‘q.")
        return redirect("core:home")

    center = get_request_center(request)

    # --- FILTERS ---
    q = (request.GET.get("q") or "").strip()
    group_id = _get_int(request.GET, "group", 0)
    min_debt = _get_int(request.GET, "min_debt", 0)
    max_debt = _get_int(request.GET, "max_debt", 0)

    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    # Base Query: Active Enrollments (student va guruh arxivda bo'lmagan)
    enrollments = (
        Enrollment.objects
        .select_related("student", "group", "group__oqituvchi", "group__category_obj")
        .filter(is_active=True, student__is_archived=False, group__is_archived=False)
    )


    if center:
        enrollments = enrollments.filter(center=center)

    if group_id:
        enrollments = enrollments.filter(group_id=group_id)

    if q:
        enrollments = enrollments.filter(
            Q(student__ism__icontains=q) |
            Q(student__familya__icontains=q) |
            Q(student__telefon1__icontains=q) |
            Q(student__telefon2__icontains=q)
        )

    # --- DEBT CALCULATION ---
    today = timezone.localdate()
    cur_month = today.replace(day=1)
    fee_field = tuition_month_fee_field()

    # ✅ [FIX] Use ONLY current month (month=cur_month), not all historical months
    # This ensures filter total matches what's shown in the table rows
    total_fee_sub = TuitionMonth.objects.filter(
        enrollment=OuterRef("pk"), month=cur_month
    ).values("enrollment").annotate(s=Sum(fee_field)).values("s")

    total_paid_sub = PaymentAllocation.objects.filter(
        tuition_month__enrollment=OuterRef("pk")
    ).values("tuition_month__enrollment").annotate(s=Sum("amount")).values("s")

    # Global total for Center (only non-archived groups)
    center_qs = Enrollment.objects.filter(
        is_active=True, student__is_archived=False, group__is_archived=False
    )
    if center: center_qs = center_qs.filter(center=center)
    
    total_center_debt = center_qs.annotate(
        f=Coalesce(Subquery(total_fee_sub), 0),
        p=Coalesce(Subquery(total_paid_sub), 0)
    ).annotate(d=F("f")-F("p")).filter(d__gt=0).aggregate(total=Sum("d"))["total"] or 0

    # Apply filter to Main Queryset
    enrollments = enrollments.annotate(
        f=Coalesce(Subquery(total_fee_sub), 0),
        p=Coalesce(Subquery(total_paid_sub), 0)
    ).annotate(calculated_debt=F("f")-F("p")).filter(calculated_debt__gt=0)

    # filtered_debt will be calculated AFTER student grouping (accurate per-student sum)
    
    rows = []
    graph_map = {m: 0 for m in range(1, 13)}
    student_map = {}  # student_id -> aggregated row

    for e in enrollments:
        # ✅ [FIX] Only use explicitly created TuitionMonth records for current month
        total_fee = TuitionMonth.objects.filter(enrollment=e, month=cur_month).aggregate(s=Sum(fee_field))["s"] or 0
        total_paid = PaymentAllocation.objects.filter(tuition_month__enrollment=e).aggregate(s=Sum("amount"))["s"] or 0
        debt = total_fee - total_paid

        if debt <= 0:
            continue
        if min_debt and debt < min_debt:
            continue
        if max_debt and debt > max_debt:
            continue

        sid = e.student_id
        group_nom = getattr(e.group, "nom", "") if e.group else ""

        if sid in student_map:
            # ✅ Same student, different group — merge into one row
            student_map[sid]["debt"] += debt
            student_map[sid]["total_fee"] += total_fee
            student_map[sid]["total_paid"] += total_paid
            if group_nom and group_nom not in student_map[sid]["group_names"]:
                student_map[sid]["group_names"].append(group_nom)
        else:
            student_map[sid] = {
                "enrollment": e,
                "created_at": e.created_at or timezone.now(),
                "student": e.student,
                "group": e.group,
                "group_names": [group_nom] if group_nom else [],
                "total_fee": total_fee,
                "total_paid": total_paid,
                "debt": debt,
                "staff": getattr(e.group, "oqituvchi", None),
            }

        e_date = (e.created_at.date() if getattr(e, "created_at", None) else today)
        m_idx = e_date.month
        if m_idx in graph_map:
            graph_map[m_idx] += debt

    rows = list(student_map.values())
    for row in rows:
        row["group_label"] = ", ".join(row["group_names"]) if row["group_names"] else "—"

    # ✅ filtered_debt = actual sum from rows (matches exactly what table shows)
    filtered_debt = sum(r["debt"] for r in rows)

    # Paginator
    from django.core.paginator import Paginator
    paginator = Paginator(rows, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Groups for filter
    groups = Group.objects.filter(is_archived=False)
    if center:
        groups = groups.filter(center=center)

    # Chart data format: [Jan..Dec]
    chart_series = [graph_map[m] for m in range(1, 13)]

    context = {
        "page_obj": page_obj,
        "groups": groups,
        "selected_group": group_id,
        "total_debt": total_center_debt,
        "filtered_debt": filtered_debt,
        "chart_data": chart_series,

        # filters
        "q": q,
        "min_debt": min_debt if min_debt else "",
        "max_debt": max_debt if max_debt else "",
        "start_date": start_date_str,
        "end_date": end_date_str,
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
    filename = f"{group.nom}_{year}-{month:02d}_attendance.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    # ✅ MUHIM: delimiter=';' (Excel RU/UZ)
    writer = csv.writer(response, delimiter=';', lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

    header = ["O'quvchi"] + [d.strftime("%d-%m-%Y") for d in day_list]
    writer.writerow(header)

    for s in students:
        row = [s.get_full_name()]
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

    student_id = request.POST.get("student_id")
    date_str = request.POST.get("date")
    current_status = request.POST.get("status", "none")

    d = parse_date(date_str)
    if not d or not student_id:
        return JsonResponse({"ok": False, "error": "Bad data"}, status=400)

    user_qs = User.objects.filter(role="student")
    if center:
        user_qs = user_qs.filter(center=center)

    student = get_object_or_404(user_qs, pk=student_id)

    att = Attendance.objects.filter(group=group, student=student, date=d).first()

    if att and getattr(att, "forced", False):
        return JsonResponse({"ok": True, "status": "forced"})

    if current_status == "none":
        if not att:
            att = Attendance(group=group, student=student, date=d, present=True)
            # Center ID ni qo'shish (migrationdan keyin)
            if hasattr(att, "center"):
                att.center = group.center
        else:
            att.present = True
            att.forced = False
        if not getattr(att, "teacher_id", None) and getattr(group, "oqituvchi_id", None):
            att.teacher = group.oqituvchi
        att.save()
        new_status = "present"

    elif current_status == "present":
        if not att:
            att = Attendance(group=group, student=student, date=d, present=False)
            if hasattr(att, "center"):
                att.center = group.center
        else:
            att.present = False
            att.forced = False
        if not getattr(att, "teacher_id", None) and getattr(group, "oqituvchi_id", None):
            att.teacher = group.oqituvchi
        att.save()
        new_status = "absent"

    elif current_status == "absent":
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
    pay_qs = base_payment_qs.select_related(
        "student", "group", "group__oqituvchi", "group__category_obj", "created_by"
    ).prefetch_related("allocations", "allocations__tuition_month")

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
    if sel_month and sel_month.isdigit():
        pay_qs = pay_qs.filter(paid_date__month=int(sel_month))

    filtered_income = pay_qs.aggregate(s=Sum("summa"))["s"] or 0

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
            # PaymentAllocation larni ham o'chiramiz (cascade bo'lmasa)
            payment.allocations.all().delete()
            payment.delete()
                 
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
    O‘quvchining (barcha kurslari bo‘yicha) to‘lov tarixini va joriy oy holatini xisoblaydi.
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
    📘 Guruhlar markaziy sahifasi — barcha kategoriyalar ro‘yxati.
    """
    from .models import Category  # agar alohida model bo‘lsa
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
        group.delete()
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

        # 🔹 Agar yangi rasm tanlangan bo‘lsa, yangisini saqlaymiz
        if image:
            cat.image = image

        cat.save()
        messages.success(request, "Bo‘lim muvaffaqiyatli tahrirlandi ✅")
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
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)

            # 🟢 To‘g‘ri maydon: ForeignKey bo‘lgan 'category_obj'
            group.category_obj = category

            # Center assignment
            from core.tenant import get_request_center
            center = get_request_center(request)
            if center:
                group.center = center

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
        return HttpResponseForbidden("Siz bu guruhni ko‘ra olmaysiz.")

    date_str = request.GET.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    if not selected_date:
        selected_date = localdate()

    enrollments = (
        Enrollment.objects
        .filter(group=g, is_active=True)
        .select_related("student", "group")   # ✅ MUHIM
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

    # ✅ Filter rules by center and role
    rules_qs = Rule.objects.filter(Q(center=center) | Q(center__isnull=True))
    if request.user.role == 'teacher':
        rules_qs = rules_qs.filter(can_teacher=True)
    elif request.user.role == 'manager':
        rules_qs = rules_qs.filter(can_manager=True)
    elif request.user.role == 'director':
        rules_qs = rules_qs.filter(can_director=True)

    ctx = {
        "g": g,
        "enrollments": enrollments,
        "rules_plus": rules_qs.filter(tur=Rule.PLUS).order_by("nom"),
        "rules_minus": rules_qs.filter(tur=Rule.MINUS).order_by("nom"),
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
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=group_id)

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
            defaults={"present": True, "forced": False, "teacher": request.user}

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
        return JsonResponse({"ok": False, "error": "ruxsat yo‘q"})

    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    adj_rule = _attendance_adjust_rule()
    start, end = _day_range(selected_date)

    enrollments = Enrollment.objects.filter(group=g).select_related("student")

    items = []
    count = 0

    for e in enrollments:
        Attendance.objects.update_or_create(
            group=g,
            student=e.student,
            date=selected_date,
            defaults={"present": True, "forced": False, "teacher": request.user, "center": g.center},
        )

        # Shu kunga qo‘yilgan adjustment bo‘lsa — delete → ball qaytadi
        adj_qs = Ledger.objects.filter(
            student=e.student,
            group=g,
            rule=adj_rule,
            sana__gte=start,
            sana__lt=end,
        )
        adj_sum = int(adj_qs.aggregate(s=Coalesce(Sum("ball"), 0))["s"] or 0)
        restored_sum = int(-adj_sum) if adj_sum else 0
        adj_qs.delete()

        balance = int(
            Ledger.objects.filter(student=e.student)
            .aggregate(s=Coalesce(Sum("ball"), 0))["s"] or 0
        )

        items.append({"student_id": e.student.id, "balance": balance, "restored_sum": restored_sum})
        count += 1

    return JsonResponse({"ok": True, "count": count, "items": items})

# ---------- AJAX: Davomatni saqlash ----------
@require_POST
@login_required
def attendance_today(request, pk: int):
    """
    status:
      - 'present' -> present=True,  forced=False  (chaqmoq mumkin)
      - 'forced'  -> present=False, forced=True   (kelmadi, pul yoziladi)
      - 'none'    -> attendance yo'q (bekor qilish)
    Backward compatible: present=1/0 yuborilsa ham ishlaydi.
    """
    g = get_object_or_404(Group, pk=pk)
    # Check center (implicit in get_object_or_404 if we filter queryset, but let's do it explicitly if needed or use standard pattern)
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center and g.center_id != center.id:
        return JsonResponse({"ok": False, "error": "Center mismatch"}, status=403)

    # faqat direktor/manager/teacher
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return JsonResponse({"ok": False, "error": "ruxsat yo‘q"}, status=403)

    enr_id = request.POST.get("enr_id")
    if not enr_id:
        return JsonResponse({"ok": False, "error": "enr_id required"}, status=400)

    # sana
    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()

    # status (yangi)
    status = (request.POST.get("status") or "").strip().lower()

    # backward compatibility (eski front bo'lsa)
    if status not in ("present", "forced", "none"):
        pv = request.POST.get("present")
        if pv is None:
            return JsonResponse({"ok": False, "error": "status/present required"}, status=400)
        status = "present" if str(pv).lower() in ("1", "true", "yes", "on") else "none"

    e = get_object_or_404(Enrollment, id=enr_id, group=g)
    student = e.student

    # shu kunlik ledgerlarni topish (shu guruh + shu student + shu sana)
    day_ledgers = Ledger.objects.filter(
        group=g,
        student=student,
        sana__date=selected_date
    )

    removed = day_ledgers.aggregate(
        removed_sum=Coalesce(Sum("ball"), 0),
        removed_count=Count("id")
    )
    removed_sum = int(removed["removed_sum"] or 0)
    removed_count = int(removed["removed_count"] or 0)

    # Agar status present bo'lmasa -> shu kundagi chaqmoqlarni bekor qilamiz
    if status != "present" and removed_count:
        day_ledgers.delete()

    # Attendance ni yaratish/yangilash/o'chirish
    if status == "none":
        Attendance.objects.filter(group=g, student=student, date=selected_date).delete()
        present = False
        forced = False

    elif status == "present":
        Attendance.objects.update_or_create(
            group=g,
            student=student,
            date=selected_date,
            defaults={
                "teacher": request.user,
                "present": True,
                "forced": False,
                "center": g.center,
            }
        )
        present = True
        forced = False

    elif status == "forced":
        Attendance.objects.update_or_create(
            group=g,
            student=student,
            date=selected_date,
            defaults={
                "teacher": request.user,
                "present": False,
                "forced": True,
                "center": g.center,
            }
        )
        present = False
        forced = True

    # yangi balans (hamma ledgerlar yig'indisi)
    bal = Ledger.objects.filter(student=student).aggregate(
        s=Coalesce(Sum("ball"), 0)
    )["s"]
    bal = int(bal or 0)

    return JsonResponse({
        "ok": True,
        "status": status,
        "present": present,
        "forced": forced,
        "removed_sum": removed_sum,
        "removed_count": removed_count,
        "balance": bal,
    })



@login_required
def group_bulk_remove(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "POST bo‘lishi shart."})

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
         qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)

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

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    g = get_object_or_404(qs, pk=pk)
    
    if request.user.role == "teacher" and g.oqituvchi != request.user and not _teacher_can(request.user, g):
        return HttpResponseForbidden()

    student_id = (data.get("student_id") or "").strip()
    rule_id = (data.get("rule_id") or "").strip()
    amount_raw = (data.get("amount") or "0").strip()
    date_str = (data.get("date") or "").strip()

    # ball parse
    try:
        amount = int(amount_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Noto‘g‘ri ball kiritildi"}, status=400)

    if amount == 0:
        return JsonResponse({"ok": False, "error": "0 ball yozilmaydi"}, status=400)

    student = get_object_or_404(User, pk=int(student_id), role="student")

    # rule
    if rule_id and rule_id.isdigit():
        rule = get_object_or_404(Rule, pk=int(rule_id))
    else:
        rule = Rule.objects.filter(nom="Erkin ball").first() or Rule.objects.create(
            nom="Erkin ball", tur=Rule.PLUS, min_baho=1, max_baho=1000000
        )

    # ✅ Rule range check
    amount_abs = abs(amount)
    if amount_abs < rule.min_baho or amount_abs > rule.max_baho:
        return JsonResponse({
            "ok": False,
            "error": f"Ushbu qoida uchun ball oralig'i: {rule.min_baho}..{rule.max_baho}"
        }, status=400)

    # sana
    if date_str:
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            parsed_date = timezone.localdate()
    else:
        parsed_date = timezone.localdate()

    # ✅ Davomatsiz chaqmoq qo‘yilmasin (faqat present=True)
    date_field = Attendance._meta.get_field("date")
    if isinstance(date_field, models.DateTimeField):
        present_exists = Attendance.objects.filter(group=g, student=student, date__date=parsed_date, present=True).exists()
    else:
        present_exists = Attendance.objects.filter(group=g, student=student, date=parsed_date, present=True).exists()

    if not present_exists:
        return JsonResponse({"ok": False, "error": "Avval davomatni belgilang (KELDI)!"}, status=400)

    # ✅ Markazning kunlik chaqmoq limiti (Center limit)
    if amount > 0 and g.center and g.center.max_daily_lightning > 0:
        today_plus = Ledger.objects.filter(
            student=student,
            sana__date=parsed_date,
            ball__gt=0
        ).aggregate(s=Coalesce(Sum("ball"), 0))["s"] or 0

        if int(today_plus) + amount > g.center.max_daily_lightning:
            return JsonResponse({
                "ok": False,
                "error": f"Bugun ushbu o'quvchi uchun {g.center.max_daily_lightning} tadan ortiq chaqmoq berish mumkin emas."
            }, status=400)

    if amount < 0 and g.center and g.center.max_daily_deduction > 0:
        # Note: amount is already negative, and ball will be negative in Ledger
        # We check the absolute sum of negative balls
        amount_abs = abs(amount)
        today_minus_abs = abs(Ledger.objects.filter(
            student=student,
            sana__date=parsed_date,
            ball__lt=0
        ).aggregate(s=Coalesce(Sum("ball"), 0))["s"] or 0)

        if int(today_minus_abs) + amount_abs > g.center.max_daily_deduction:
            return JsonResponse({
                "ok": False,
                "error": f"Bugun ushbu o'quvchidan {g.center.max_daily_deduction} tadan ortiq chaqmoq ayirish mumkin emas."
            }, status=400)

    # ✅ Kunlik chaqmoq limit
    from .models import DailyLightningSetting
    setting = DailyLightningSetting.objects.filter(date=parsed_date, active=True).first()
    if setting and setting.max_lightning and setting.max_lightning > 0:
        today_plus = Ledger.objects.filter(
            student=student,
            sana__date=parsed_date,
            ball__gt=0
        ).aggregate(s=Coalesce(Sum("ball"), 0))["s"] or 0

        if int(today_plus) + max(0, amount) > int(setting.max_lightning):
            return JsonResponse({
                "ok": False,
                "error": f"Bugun {setting.max_lightning} tadan ortiq chaqmoq berish mumkin emas."
            }, status=400)

    # sana
    now_time = timezone.localtime(timezone.now()).time()
    sana = timezone.make_aware(datetime.combine(parsed_date, now_time))
    record = Ledger.objects.create(
        student=student,
        beruvchi=request.user,
        group=g,
        rule=rule,
        ball=amount,
        sana=sana,
    )

    balance = Ledger.objects.filter(student=student).aggregate(s=Coalesce(Sum("ball"), 0))["s"] or 0

    return JsonResponse({
        "ok": True,
        "amount": amount,
        "balance": int(balance),
        "saved_date": parsed_date.strftime("%Y-%m-%d"),
        "id": record.id
    })


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
         messages.error(request, "Ruxsat yo‘q.")
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
            "oqituvchi": teacher.get_full_name() or teacher.email,
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
                "placeholder": "Bo‘lim haqida qisqa izoh"
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
    from core.tenant import get_request_center
    center = get_request_center(request)
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.center = center
            cat.save()
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
        e.student for e in g.enrollments.filter(is_active=True).select_related("student").order_by("student__ism", "student__familya")
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
                    now_local = timezone.localtime(timezone.now()).time()
                    sana = timezone.make_aware(datetime.combine(the_date, now_local))
                    Ledger.objects.create(student=s, beruvchi=request.user, group=g, rule=rule, ball=signed, sana=sana)
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

    # Oddiy, tushunarli hisob (keyin xohlasa optimallashtirib beraman)
    for t in teachers:
        groups = (
            Group.objects
            .filter(oqituvchi=t, is_archived=False)
            .prefetch_related("enrollments", "attendances")
        )

        teacher_total = 0
        for g in groups:
            for enr in g.enrollments.all():
                # siz ishlatayotgan method
                teacher_total += enr.real_oqituvchi_daromadi(year=year, month=month)

        total_all += teacher_total

        teacher_rows.append({
            "teacher": t,
            "month_salary": teacher_total,
            "groups_count": groups.count(),
        })

    return render(request, "education/teacher_salary_list.html", {
        "teachers": teacher_rows,
        "year": year,
        "month": month,
        "month_name": month_name,
        "total_all": total_all,
    })

# 🔹 2. O‘qituvchining barcha guruhlari
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

    teacher_data = []
    for group in groups:

        # ✅ shu group uchun kerakli oy attendances'ni oldindan filtrlab olamiz
        month_att = group.attendances.filter(
            date__year=year,
            date__month=month
        ).filter(Q(present=True) | Q(forced=True))

        # ✅ active/inactive hammasi kerak, chunki o'sha oyda o'qigan bo'lishi mumkin
        enrollments = []
        for enr in group.enrollments.all():

            attended = month_att.filter(student=enr.student).count()
            # Agar bu oyda umuman darsga kelmagan bo'lsa va inactive bo'lsa -> ro'yxatda ko'rsatmasak ham mayli
            # LEKIN: Agar attendance > 0 bo'lsa, albatta ko'rsatish shart.
            
            if not enr.is_active and attended == 0:
                 continue

            daromad = enr.real_oqituvchi_daromadi(year=year, month=month)

            enrollments.append({
                "student": enr.student,      # ✅ student obyekt
                "kurs_narhi": enr.kurs_narhi,
                "foiz": enr.oqituvchi_foiz,
                "attended": attended,
                "daromad": daromad,
            })

        total_income = sum(x["daromad"] for x in enrollments)

        teacher_data.append({
            "group": group,
            "enrollments": enrollments,
            "foiz": group.oqituvchi_foiz,
            "daromad": total_income,
            "students_count": len(enrollments),
        })

    return render(request, "education/teacher_groups.html", {
        "teacher": teacher,
        "teacher_data": teacher_data,
        "year": year,
        "month": month,
        "years": years,   # ✅ SHU QO‘SHILDI

    })


@login_required
def teacher_salary_report(request, group_id):
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=group_id)
    
    # ✅ Arxivlangan (inactive) o‘quvchilar ham hisobga olinishi uchun:
    # Biz .filter(is_active=True) ISHLATMAYMIZ. 
    # Chunki o‘tgan darslar uchun pul to‘lanishi shart.
    enrollments = group.enrollments.all().select_related("student")

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
    from core.tenant import get_request_center
    center = get_request_center(request)
    att_qs = Attendance.objects.all()
    if center:
        # attendance -> group -> center
        att_qs = att_qs.filter(group__center=center)

    attendance = (
        att_qs
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
    user_qs = User.objects.filter(role="teacher")
    if center:
        user_qs = user_qs.filter(center=center)

    # Guruhlar kvartirasi - faqat shu markazniki bo'lishi shart!
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)

    teachers = (
        user_qs
        .prefetch_related(
            Prefetch(
                "group_set",
                queryset=group_qs.prefetch_related(
                    Prefetch(
                        "enrollments",
                        # ✅ Tarixiy hisobda inactive enrollments ham qatnashishi kerak
                        queryset=Enrollment.objects.all().select_related("student")
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
                        lessons_per_month = group.oy_dars_soni or 12
                        teacher_part = kurs * foiz / lessons_per_month
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
            "id": teacher.id,
            "teacher": teacher.get_full_name() or teacher.email,
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

    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, id=group_id)

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
        return redirect("education:groups_home")

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
        if g.oqituvchi and getattr(g.oqituvchi, 'oqituvchi_foizi', None) is not None:
            g.oqituvchi_foiz = g.oqituvchi.oqituvchi_foizi
        elif not g.oqituvchi_foiz:
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
    if not request.user.is_superuser and request.user.role not in ["director", "manager", "teacher"]:
        messages.error(request, "Sizda ruxsat yo‘q.")
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
    Barcha guruhlar ro‘yxati.
    """
    rows = Group.objects.select_related("center", "oqituvchi").all()
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
    from core.tenant import get_request_center
    center = get_request_center(request)
    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        category = getattr(group, "category_obj", None)
        group.delete()
        messages.success(request, "🗑️ Guruh o‘chirildi.")

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
    allowed_roles = ['admin', 'manager', 'teacher', 'director']
    if request.user.role not in allowed_roles:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "Sizda ruxsat yo'q"}, status=403)
        return HttpResponseForbidden("❌ Sizda bu amalni bajarish uchun ruxsat yo‘q.")

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

        # Qo'shish
        enr = Enrollment.objects.create(
            group=g,
            student=student,
            center=target_center,
            kurs_narhi=kurs_narhi,
            oqituvchi_foiz=g.oqituvchi_foiz or 40,
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
    qs = Enrollment.objects.select_related("group", "student")
    from core.tenant import get_request_center
    center = get_request_center(request)
    if center:
        # Enrollment has center now, or filter by group__center
        qs = qs.filter(group__center=center)
    enr = get_object_or_404(qs, pk=pk)
    
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:group_detail", pk=enr.group_id)
        
    if request.method == "POST":
        # ✅ SOFT DELETE: Tarix saqlanib qolishi uchun o'chirmaymiz, faqat nofaol qilamiz.
        enr.is_active = False
        enr.save()
        messages.success(request, "O‘quvchi guruhdan chiqarildi (Arxivlandi). Tarix saqlanib qoldi.")
        
    return redirect("education:group_detail", pk=enr.group_id)


@login_required
def my_groups(request):
    rows = (
        Group.objects.filter(oqituvchi=request.user, is_archived=False)
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
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
    Kunlik va oylik daromadlarni diagramma uchun tayyorlab beradi.
    """
    if request.user.role not in ['teacher', 'director', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Bu bo'lim ushbu rol uchun emas.")
        return redirect('core:home')
        
    is_admin = request.user.role in ['director', 'manager'] or request.user.is_superuser
    
    teacher = request.user
    today = timezone.localdate()
    
    # Tanlangan yil va oy (filterdan yoki joriydan)
    selected_year = _get_int(request.GET, "year", today.year)
    selected_month = _get_int(request.GET, "month", today.month)
    
    months_list = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
        (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
        (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
    ]
    
    # 1) Davomat ma'lumotlarini olish (yil bo'yicha)
    # present=True YOKI forced=True bo'lgan holatlar daromad hisoblanadi.
    att_qs = Attendance.objects.filter(
        teacher=teacher,
        date__year=selected_year
    ).filter(Q(present=True) | Q(forced=True))
    
    # 2) O'qituvchi guruhlari va o'quvchilar narxini xaritaga yig'ish
    # Bu orqali har bir dars uchun qancha daromad tushishini bilib olamiz.
    enrollment_map = {}
    groups = Group.objects.filter(oqituvchi=teacher).prefetch_related('enrollments')
    for g in groups:
        for enr in g.enrollments.all():
            enrollment_map[(g.id, enr.student_id)] = {
                'kurs': enr.kurs_narhi or 0,
                'foiz': (enr.oqituvchi_foiz or 0) / 100,
                'lessons_per_month': g.oy_dars_soni or 12
            }
            
    # Oylik daromad (12 oy uchun)
    monthly_income = [0] * 12
    # Kunlik daromad (tanlangan oy uchun)
    _, num_days = calendar.monthrange(selected_year, selected_month)
    daily_income = [0] * num_days
    
    # Davomatlarni hisoblab chiqamiz
    attendances = att_qs.annotate(
        m=ExtractMonth('date'),
        d=ExtractDay('date')
    ).values('group_id', 'student_id', 'm', 'd')
    
    for att in attendances:
        info = enrollment_map.get((att['group_id'], att['student_id']))
        if info:
            # Bir dars uchun o'qituvchi ulushi
            income_per_lesson = (info['kurs'] * info['foiz']) / info['lessons_per_month']
            
            # Oylik yig'indiga qo'shish
            monthly_income[att['m'] - 1] += float(income_per_lesson)
            
            # Agar tanlangan oy bo'lsa, kunlik yig'indiga qo'shish
            if att['m'] == selected_month:
                daily_income[att['d'] - 1] += float(income_per_lesson)
                
    # Diagramma uchun belgilarni tayyorlash
    daily_labels = [str(d) for d in range(1, num_days + 1)]
    monthly_labels = [m[1] for m in months_list]
    
    # Hozirgi oy uchun umumiy daromad
    current_month_total = monthly_income[selected_month - 1]
    
    ctx = {
        'selected_year': selected_year,
        'selected_month': selected_month,
        'months_list': months_list,
        'daily_income': daily_income,
        'daily_labels': daily_labels,
        'monthly_income': monthly_income,
        'monthly_labels': monthly_labels,
        'current_month_total': current_month_total,
        'total_year_income': sum(monthly_income),
        'years': range(today.year - 2, today.year + 2),
        'is_admin': is_admin,
    }
    
    return render(request, "education/teacher_income_dashboard.html", ctx)
