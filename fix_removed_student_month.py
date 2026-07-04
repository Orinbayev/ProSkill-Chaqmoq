"""Chiqarilgan o'quvchining noto'g'ri oyga yozilgan qarzini to'g'ri oyga ko'chiradi.

DRY-RUN (default): faqat ko'rsatadi — HECH NARSA yozmaydi.
--apply: transaction ichida tuzatadi (faqat paid=0 va himoyalanmagan yozuvlar).

Foydalanish:
    # Bitta o'quvchi (telefon bo'yicha) — avval ko'rish:
    python fix_removed_student_month.py --phone 993804721
    # Tuzatish:
    python fix_removed_student_month.py --phone 993804721 --apply

    # Ism bo'yicha:
    python fix_removed_student_month.py --name AMANDURDIYEV

    # BUTUN markaz bo'yicha barcha chiqarilgan o'quvchilar (ehtiyot bo'ling):
    python fix_removed_student_month.py --center-slug proskill
    python fix_removed_student_month.py --center-slug proskill --apply
"""
import os
import sys
import argparse
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db.models import Q  # noqa: E402
from accounts.models import User  # noqa: E402
from education.models import Enrollment  # noqa: E402
from education.services.removed_debt_repair import (  # noqa: E402
    build_proposals, apply_proposal,
)


def _enrollments(args):
    qs = Enrollment.all_objects.select_related("student", "group", "group__center")
    qs = qs.filter(Q(is_active=False) | Q(is_deleted=True))  # chiqarilganlar
    if args.phone:
        qs = qs.filter(Q(student__telefon1__icontains=args.phone)
                       | Q(student__telefon2__icontains=args.phone))
    if args.name:
        qs = qs.filter(Q(student__familya__icontains=args.name)
                       | Q(student__ism__icontains=args.name))
    if args.center_slug:
        qs = qs.filter(Q(center__slug=args.center_slug)
                       | Q(group__center__slug=args.center_slug))
    return qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone")
    ap.add_argument("--name")
    ap.add_argument("--center-slug")
    ap.add_argument("--apply", action="store_true", help="Haqiqatan tuzatadi (aks holda dry-run)")
    args = ap.parse_args()

    if not (args.phone or args.name or args.center_slug):
        print("Kamida --phone / --name / --center-slug bering.")
        sys.exit(1)

    enrs = _enrollments(args)
    print(f"Chiqarilgan enrollment topildi: {enrs.count()}")
    print("REJIM:", "APPLY (yoziladi!)" if args.apply else "DRY-RUN (hech narsa yozilmaydi)")
    print("=" * 72)

    total_props = 0
    for enr in enrs:
        props = build_proposals(enr)
        if not props:
            continue
        for p in props:
            total_props += 1
            tag = {"move": "KO'CHIRISH", "zero_phantom": "FANTOM→0",
                   "skip_paid": "TASHLAB KETISH (to'langan)",
                   "skip_unknown": "TASHLAB KETISH (oy noaniq)"}.get(p.action, p.action)
            print(f"\n[{tag}] {p.student_name} | {p.group_name} (enr={p.enrollment_id})")
            print(f"    {p.source_month:%Y-%m} fee={p.source_fee}  ->  "
                  f"{p.target_month:%Y-%m} (hozirgi fee={p.target_existing_fee})")
            print(f"    izoh: {p.note}")
            if args.apply and p.action in ("move", "zero_phantom"):
                result = apply_proposal(p)
                print(f"    ==> {result}")

    print("\n" + "=" * 72)
    print(f"Jami takliflar: {total_props}")
    if not args.apply and total_props:
        print("Tuzatish uchun xuddi shu buyruqni --apply bilan qayta ishga tushiring.")


if __name__ == "__main__":
    main()
