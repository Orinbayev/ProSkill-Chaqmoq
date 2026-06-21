"""
Render Shell da ishlatish:
    python manage.py shell < scripts/bulk_pay_proskill_debtors.py

BOSQICH 1 — DRY RUN (hech narsa o'zgarmaydi):
    CONFIRM = False  qoldiring, ishga tushiring, natijani ko'ring.

BOSQICH 2 — HAQIQIY YOZUV:
    Quydagi CONFIRM = True qiling, TO'LOV_SANA va TO'LOV_TURI ni tekshiring,
    keyin qayta ishga tushiring.
"""

import os, sys, django
# Render Shell da bu qator shart emas (django allaqachon setup), lekin zararsiz.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_prod")

# ═══════════════════════════════════════════════════════
#  SOZLAMALAR — faqat shu yerda o'zgartiring
# ═══════════════════════════════════════════════════════
CENTER_SLUG   = "proskill"          # qaysi markaz
TO_LOV_SANA  = "2026-06-21"        # to'lov sanasi (YYYY-MM-DD)
TO_LOV_TURI  = "cash"              # "cash" | "card" | "mixed"
IZOH          = "Eski qarz — to'lov bo'limiga o'tkazildi"
CONFIRM       = False              # True qilsangiz haqiqiy yozuv yaratiladi!
# ═══════════════════════════════════════════════════════

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Q

from accounts.models import Center, CustomUser
from education.models import Enrollment, TuitionMonth, PaymentAllocation, Payment
from education.services.tuition import (
    month_first_day,
    create_payment_and_allocate,
    ensure_all_tuition_months_since_start,
    find_earliest_unpaid_month,
    tuition_month_fee_field,
)

# ── Sana parse ──────────────────────────────────────────
try:
    paid_date = date.fromisoformat(TO_LOV_SANA)
except ValueError:
    print(f"❌ TO_LOV_SANA formati noto'g'ri: {TO_LOV_SANA}  (YYYY-MM-DD bo'lishi kerak)")
    sys.exit(1)

paid_at = datetime.combine(paid_date, datetime.min.time())
paid_at = timezone.make_aware(paid_at, timezone.get_current_timezone())

# ── Markaz ──────────────────────────────────────────────
try:
    center = Center.objects.get(slug=CENTER_SLUG)
except Center.DoesNotExist:
    print(f"❌ '{CENTER_SLUG}' slugli markaz topilmadi!")
    print("Mavjud markazlar:")
    for c in Center.objects.all().values("slug", "name"):
        print(f"   • {c['slug']}  ({c['name']})")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"  MARKAZ  : {center.name}  [{center.slug}]")
print(f"  SANA    : {paid_date}")
print(f"  TURI    : {TO_LOV_TURI}")
print(f"  IZOH    : {IZOH}")
print(f"  REJIM   : {'⚠️  HAQIQIY (CONFIRM=True)' if CONFIRM else '🔍 DRY RUN (CONFIRM=False)'}")
print(f"{'='*60}\n")

# ── Superuser (created_by) ───────────────────────────────
creator = CustomUser.objects.filter(is_superuser=True).order_by("id").first()
if creator is None:
    creator = CustomUser.objects.filter(center=center, role__in=["director", "manager"]).order_by("id").first()
if creator is None:
    print("❌ Superuser yoki direktor topilmadi — to'lovni kim yaratishi noma'lum.")
    sys.exit(1)
print(f"  Kirituvchi: {creator.get_full_name()} ({creator.username})\n")

# ── Faol enrollmentlar ──────────────────────────────────
active_enrs = list(
    Enrollment.objects
    .select_related("student", "group", "group__center")
    .filter(
        is_active=True,
        is_deferred=False,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False,
        group__center=center,
    )
    .order_by("student__familya", "student__ism", "id")
)

# Guruhdan chiqarilgan lekin qarzi bor enrollment'lar
fee_field = tuition_month_fee_field()
_inactive_debt_enr_ids = set(
    TuitionMonth.objects
    .filter(
        enrollment__group__center=center,
        enrollment__is_active=False,
        enrollment__student__is_archived=False,
        enrollment__group__is_archived=False,
        enrollment__group__is_deleted=False,
        is_deleted=False,
    )
    .values_list("enrollment_id", flat=True)
)
inactive_enrs = list(
    Enrollment.objects
    .select_related("student", "group", "group__center")
    .filter(id__in=_inactive_debt_enr_ids)
    .order_by("student__familya", "student__ism", "id")
)

all_enrollments = active_enrs + inactive_enrs
print(f"Jami enrollment (faol+chiqarilgan): {len(all_enrollments)}\n")

# ── Har enrollment uchun qarz hisoblash ────────────────
fee_field_name = tuition_month_fee_field()
all_enr_ids = [e.id for e in all_enrollments]

# 1 ta query bilan barcha TuitionMonth
tm_rows = list(
    TuitionMonth.objects
    .filter(enrollment_id__in=all_enr_ids, is_deleted=False)
    .values("id", "enrollment_id", "month", fee_field_name)
)
tm_id_to_enr_month = {r["id"]: (r["enrollment_id"], r["month"]) for r in tm_rows}
tm_ids = [r["id"] for r in tm_rows]

# 1 ta query bilan barcha to'lovlar
paid_map = {}
if tm_ids:
    for row in (
        PaymentAllocation.objects
        .filter(
            tuition_month_id__in=tm_ids,
            tuition_month__is_deleted=False,
            payment__is_deleted=False,
        )
        .values("tuition_month__enrollment_id", "tuition_month__month")
        .annotate(paid=Sum("amount"))
    ):
        paid_map[(row["tuition_month__enrollment_id"], row["tuition_month__month"])] = int(row["paid"] or 0)

# Enrollment bo'yicha qarz yig'amiz
enr_debt = {}   # {enrollment_id: total_debt}
enr_tms  = {}   # {enrollment_id: [tm_row, ...]}
for r in tm_rows:
    eid = r["enrollment_id"]
    fee  = int(r[fee_field_name] or 0)
    paid = paid_map.get((eid, r["month"]), 0)
    debt = max(0, fee - paid)
    enr_debt[eid] = enr_debt.get(eid, 0) + debt
    enr_tms.setdefault(eid, []).append(r)

# ── Faqat qarzdorlarni chiqaramiz ──────────────────────
debtors = [(e, enr_debt.get(e.id, 0)) for e in all_enrollments if enr_debt.get(e.id, 0) > 0]
debtors.sort(key=lambda x: (x[0].student.familya or "", x[0].student.ism or ""))

if not debtors:
    print("✅ Proskill da qarzdor topilmadi — hamma to'lagan!")
    sys.exit(0)

print(f"{'─'*60}")
print(f"{'#':<4} {'O\'quvchi':<30} {'Guruh':<20} {'Qarz':>12}")
print(f"{'─'*60}")
total_debt = 0
for idx, (enr, debt) in enumerate(debtors, 1):
    student_name = f"{enr.student.familya or ''} {enr.student.ism or ''}".strip()
    group_name   = getattr(enr.group, "nom", "?") if enr.group else "?"
    print(f"{idx:<4} {student_name:<30} {group_name:<20} {debt:>12,} so'm")
    total_debt += debt

print(f"{'─'*60}")
print(f"{'JAMI QARZ':>56} {total_debt:>12,} so'm")
print(f"{'─'*60}")
print(f"\nQarzdorlar soni: {len(debtors)}")

if not CONFIRM:
    print("\n" + "═"*60)
    print("  DRY RUN TUGADI — hech narsa o'zgarmadi.")
    print("  Haqiqiy yozuv uchun: CONFIRM = True qiling")
    print("═"*60)
    sys.exit(0)

# ══════════════════════════════════════════════════════
#  HAQIQIY YOZUV (CONFIRM = True)
# ══════════════════════════════════════════════════════
print("\n" + "⚠️ "*20)
print("  HAQIQIY YOZUV BOSHLANMOQDA...")
print("⚠️ "*20 + "\n")

success_count = 0
skip_count    = 0
error_count   = 0
errors        = []

today_month = month_first_day(timezone.localdate())

for enr, debt in debtors:
    student_name = f"{enr.student.familya or ''} {enr.student.ism or ''}".strip()
    try:
        # O'tgan barcha oylar uchun TuitionMonth borligini ta'minlaymiz
        ensure_all_tuition_months_since_start(enr, today_month)

        with transaction.atomic():
            create_payment_and_allocate(
                enrollment=enr,
                cash_amount=debt if TO_LOV_TURI == "cash" else 0,
                card_amount_som=debt if TO_LOV_TURI == "card" else 0,
                created_by=creator,
                start_month=None,   # eng eski to'lanmagan oydan boshlab
                paid_at=paid_at,
                note=IZOH,
                payment_type=TO_LOV_TURI,
            )

        print(f"  ✅ {student_name:<30} {debt:>12,} so'm  → saqlandi")
        success_count += 1

    except Exception as exc:
        err_msg = str(exc)
        print(f"  ❌ {student_name:<30} XATO: {err_msg}")
        errors.append((student_name, err_msg))
        error_count += 1

print(f"\n{'═'*60}")
print(f"  ✅ Muvaffaqiyat : {success_count} ta")
print(f"  ⏭️  O'tkazildi   : {skip_count} ta")
print(f"  ❌ Xato         : {error_count} ta")
print(f"{'═'*60}")
if errors:
    print("\nXatolar:")
    for name, err in errors:
        print(f"  • {name}: {err}")
