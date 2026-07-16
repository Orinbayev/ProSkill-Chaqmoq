"""
READ-ONLY diagnostic: Dashboard "Qarzdorlar" KPI vs Qarzdorlar sahifasi farqini
qayerdan kelishini ko'rsatadi (arxiv/o'chirilgan guruhlar, deferred, va h.k.).

Serverda (Render shell) ishga tushiring:
    python manage.py shell < diagnose_dashboard_vs_qarzdorlar.py

Hech narsani o'zgartirmaydi — faqat hisoblab chiqaradi.
"""
from datetime import date
from django.db.models import Q, Sum
from django.utils import timezone
from education.models import Enrollment, TuitionMonth, PaymentAllocation, Center
from education.services.tuition import tuition_month_fee_field

ff = tuition_month_fee_field()
today = timezone.localdate()
month = today.replace(day=1)   # joriy oy (dashboard KPI shu oyni sanaydi)
print(f"Oy: {month}   fee_field: {ff}\n")


def _paid(tm_ids):
    m = {}
    for r in (PaymentAllocation.objects
              .filter(tuition_month_id__in=tm_ids, tuition_month__is_deleted=False,
                      payment__is_deleted=False)
              .values("tuition_month_id").annotate(p=Sum("amount"))):
        m[r["tuition_month_id"]] = int(r["p"] or 0)
    return m


for center in Center.objects.all():
    # center_month_debt_summary bilan bir xil enrollment sharti:
    tm_q = (TuitionMonth.objects.filter(
                enrollment__group__center=center, month=month, is_deleted=False)
            .filter(Q(enrollment__is_active=True, enrollment__is_deferred=False,
                      enrollment__student__is_archived=False)
                    | Q(enrollment__is_active=False,
                        enrollment__student__is_archived=False)))
    rows = list(tm_q.values_list(
        "id", "enrollment__student_id",
        "enrollment__group__is_archived", "enrollment__group__is_deleted", ff))
    if not rows:
        continue
    pm = _paid([r[0] for r in rows])

    old_total = 0          # ESKI dashboard (arxiv guruhlar bilan)
    new_total = 0          # YANGI dashboard (arxiv/o'chirilgan chiqarilgan) = qarzdorlar sahifasi
    archived_bucket = 0    # farqning sababi
    for tmid, sid, g_arch, g_del, fee in rows:
        d = max(0, int(fee or 0) - pm.get(tmid, 0))
        if d <= 0:
            continue
        old_total += d
        if g_arch or g_del:
            archived_bucket += d
        else:
            new_total += d

    if old_total == 0:
        continue
    print("=" * 60)
    print(f"CENTER {center.id}: {getattr(center,'nom',getattr(center,'name',''))}")
    print(f"  ESKI dashboard KPI  (arxiv guruhlar bilan)   = {old_total:,} so'm")
    print(f"  YANGI dashboard KPI (tuzatilgan)             = {new_total:,} so'm")
    print(f"  --> ARXIV/O'CHIRILGAN guruhlardagi qarz      = {archived_bucket:,} so'm")
    if archived_bucket == old_total - new_total and archived_bucket > 0:
        print("  ✅ Farq TO'LIQ arxiv/o'chirilgan guruhlardan — tuzatish yopadi.")
    elif archived_bucket == 0:
        print("  ⚠️  Arxiv guruhlarda qarz yo'q — farq boshqa sababdan (deferred/scope).")
