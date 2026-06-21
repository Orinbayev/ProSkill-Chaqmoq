from accounts.models import Center
from education.models import Enrollment, Group

# Barcha markazlar uchun yoki faqat bittasi uchun
# CENTER_SLUG = "proskill"  # faqat proskill
CENTER_SLUG = None           # hammasi

groups_qs = Group.objects.filter(is_archived=False, is_deleted=False, kurs_narxi=0)
if CENTER_SLUG:
    c = Center.objects.get(slug=CENTER_SLUG)
    groups_qs = groups_qs.filter(center=c)

zero_price_groups = list(groups_qs.select_related("center", "oqituvchi"))
print(f"\nNarxi 0 bo'lgan guruhlar: {len(zero_price_groups)} ta")

enr_qs = Enrollment.objects.filter(
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__in=zero_price_groups,
).select_related("student", "group", "group__center")

also_zero_enr = Enrollment.objects.filter(
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    kurs_narhi=0,
    group__is_archived=False,
    group__is_deleted=False,
)
if CENTER_SLUG:
    also_zero_enr = also_zero_enr.filter(group__center=c)

all_ids = set(enr_qs.values_list("id", flat=True)) | set(also_zero_enr.values_list("id", flat=True))

all_enrs = Enrollment.objects.filter(
    id__in=all_ids
).select_related("student", "group", "group__center").order_by(
    "group__center__name", "group__nom", "student__familya"
)

print(f"Narxi 0 bo'lgan faol o'quvchilar: {all_enrs.count()} ta\n")
print(f"{'#':<4} {'Markaz':<15} {'Guruh':<25} {'O\'quvchi':<30} {'Guruh narxi':>12} {'Enr narxi':>10}")
print("-" * 100)

for i, e in enumerate(all_enrs, 1):
    markaz = getattr(e.group.center, "name", "?") if e.group and e.group.center else "?"
    guruh  = getattr(e.group, "nom", "?") if e.group else "?"
    guruh_narxi = getattr(e.group, "kurs_narxi", "?") if e.group else "?"
    enr_narxi = e.kurs_narhi
    ism = f"{e.student.familya or ''} {e.student.ism or ''}".strip()
    print(f"{i:<4} {markaz:<15} {guruh:<25} {ism:<30} {guruh_narxi:>12,} {enr_narxi:>10,}")

print("-" * 100)
print(f"JAMI: {all_enrs.count()} ta o'quvchi\n")
