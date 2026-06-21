"""
Render Shell:
    python manage.py shell < scripts/diagnose_proskill_debt.py
"""
from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth, PaymentAllocation
from education.services.tuition import tuition_month_fee_field
from django.db.models import Sum

CENTER_SLUG = "proskill"

center = Center.objects.get(slug=CENTER_SLUG)
fee_field = tuition_month_fee_field()

# ── Faol enrollmentlar ──────────────────────────────────
active_enrs = list(
    Enrollment.objects
    .filter(
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False,
        group__center=center,
    )
    .select_related("student", "group")
)

# ── Chiqarilgan lekin TuitionMonth bor enrollmentlar ───
inactive_with_tm_ids = set(
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
    .filter(id__in=inactive_with_tm_ids)
    .select_related("student", "group")
)

all_enrs = active_enrs + inactive_enrs
all_ids  = [e.id for e in all_enrs]

# ── TuitionMonth va Payment ma'lumotlari ───────────────
tm_rows = list(
    TuitionMonth.objects
    .filter(enrollment_id__in=all_ids, is_deleted=False)
    .values("id", "enrollment_id", "month", fee_field)
    .order_by("enrollment_id", "month")
)
tm_ids = [r["id"] for r in tm_rows]

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

# ── Har enrollment uchun hisob ─────────────────────────
enr_info = {}
for r in tm_rows:
    eid  = r["enrollment_id"]
    fee  = int(r[fee_field] or 0)
    paid = paid_map.get((eid, r["month"]), 0)
    debt = max(0, fee - paid)
    if eid not in enr_info:
        enr_info[eid] = {"fee": 0, "paid": 0, "debt": 0, "months": 0, "unpaid_months": 0}
    enr_info[eid]["fee"]   += fee
    enr_info[eid]["paid"]  += paid
    enr_info[eid]["debt"]  += debt
    enr_info[eid]["months"] += 1
    if debt > 0:
        enr_info[eid]["unpaid_months"] += 1

active_set   = {e.id for e in active_enrs}
inactive_set = {e.id for e in inactive_enrs}

# ── Natijalar ──────────────────────────────────────────
active_debt_enrs   = [(e, enr_info[e.id]) for e in active_enrs   if enr_info.get(e.id, {}).get("debt", 0) > 0]
inactive_debt_enrs = [(e, enr_info[e.id]) for e in inactive_enrs if enr_info.get(e.id, {}).get("debt", 0) > 0]

total_active_debt   = sum(i["debt"] for _, i in active_debt_enrs)
total_inactive_debt = sum(i["debt"] for _, i in inactive_debt_enrs)

print("\n" + "="*65)
print(f"  MARKAZ: {center.name}  [{center.slug}]")
print("="*65)

print(f"\n{'─'*65}")
print(f"  FAOL O'QUVCHILAR QARZI")
print(f"{'─'*65}")
print(f"  Faol enrollment soni       : {len(active_enrs):>6}")
print(f"  Shundan qarzdorlar         : {len(active_debt_enrs):>6}")
print(f"  Jami faol qarz             : {total_active_debt:>15,} so'm")

# Nechta oylik qarzlari bor?
month_dist = {}
for _, info in active_debt_enrs:
    m = info["unpaid_months"]
    month_dist[m] = month_dist.get(m, 0) + 1
print(f"\n  To'lanmagan oy bo'yicha taqsimot (faol):")
for m in sorted(month_dist):
    label = f"{m} oy"
    print(f"    {label:>8} : {month_dist[m]:>4} ta enrollment")

print(f"\n{'─'*65}")
print(f"  GURUHDAN CHIQARILGAN (is_active=False) LEKIN QARZI BOR")
print(f"{'─'*65}")
print(f"  Chiqarilgan enrollment soni: {len(inactive_enrs):>6}")
print(f"  Shundan qarzdorlar         : {len(inactive_debt_enrs):>6}")
print(f"  Jami chiqarilgan qarz      : {total_inactive_debt:>15,} so'm")

if inactive_debt_enrs:
    print(f"\n  {'O\'quvchi':<30} {'Guruh':<22} {'Oy':>4} {'Qarz':>12}")
    print(f"  {'─'*70}")
    for e, info in sorted(inactive_debt_enrs, key=lambda x: -x[1]["debt"])[:30]:
        name  = f"{e.student.familya or ''} {e.student.ism or ''}".strip()
        group = getattr(e.group, "nom", "?") if e.group else "?"
        print(f"  {name:<30} {group:<22} {info['unpaid_months']:>4} {info['debt']:>12,}")
    if len(inactive_debt_enrs) > 30:
        print(f"  ... va yana {len(inactive_debt_enrs)-30} ta")

print(f"\n{'='*65}")
print(f"  JAMI QARZ BREAKDOWN")
print(f"{'='*65}")
print(f"  Faol o'quvchilar qarzi     : {total_active_debt:>15,} so'm")
print(f"  Chiqarilgan o'quvchilar    : {total_inactive_debt:>15,} so'm")
print(f"  {'─'*40}")
print(f"  UMUMIY                     : {total_active_debt+total_inactive_debt:>15,} so'm")
print(f"{'='*65}\n")
