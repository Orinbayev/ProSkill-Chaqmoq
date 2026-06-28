"""
fix_teacher_income_limit.py

Har bir (o'quvchi, guruh, oy) uchun oy_dars_soni dan ortiq dars bo'lsa,
qo'shimcha darslarning TeacherIncome yozuvlarini 0 ga tushiradi.

Ishlatish:
    python manage.py fix_teacher_income_limit             # barcha markazlar
    python manage.py fix_teacher_income_limit --dry-run  # faqat hisobot, o'zgartirmasdan
    python manage.py fix_teacher_income_limit --center proskill  # bitta markaz
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count


class Command(BaseCommand):
    help = "Oy limitidan (oy_dars_soni) ortiq darslardagi teacher income ni 0 ga tushiradi"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="O'zgartirmasdan hisobot ko'rsat")
        parser.add_argument("--center", type=str, help="Center slug (ixtiyoriy)")

    def handle(self, *args, **options):
        from education.models import Attendance, TeacherIncome, Group
        from accounts.models import Center

        dry_run = options["dry_run"]
        center_slug = options.get("center")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN rejimi — hech narsa o'zgartirilmaydi\n"))

        # Barcha (group, student, year, month) kombinatsiyalarini topamiz
        qs = (
            Attendance.objects
            .filter(status__in=("present", "absent_unexcused", "late"))
            .values("group_id", "student_id", "date__year", "date__month")
            .annotate(total=Count("id"))
        )

        if center_slug:
            try:
                center = Center.objects.get(slug=center_slug)
                qs = qs.filter(group__center=center)
            except Center.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Center topilmadi: {center_slug}"))
                return

        groups_cache = {}
        total_fixed = 0
        total_checked = 0

        for row in qs:
            group_id = row["group_id"]
            student_id = row["student_id"]
            year = row["date__year"]
            month = row["date__month"]
            total_lessons = row["total"]

            # Guruh oy_dars_soni ni kesh qilamiz
            if group_id not in groups_cache:
                try:
                    g = Group.objects.only("oy_dars_soni").get(pk=group_id)
                    groups_cache[group_id] = g.oy_dars_soni or 12
                except Group.DoesNotExist:
                    groups_cache[group_id] = 12

            limit = groups_cache[group_id]

            if total_lessons <= limit:
                continue  # bu oy normada, o'tkazib yuboramiz

            # Ortiqcha darslar bor — birinchi `limit` tani aniqlash
            all_billable_ids = list(
                Attendance.objects.filter(
                    group_id=group_id,
                    student_id=student_id,
                    date__year=year,
                    date__month=month,
                    status__in=("present", "absent_unexcused", "late"),
                ).order_by("date", "id").values_list("id", flat=True)
            )

            paid_ids = set(all_billable_ids[:limit])
            extra_ids = set(all_billable_ids[limit:])

            total_checked += 1

            # Ortiqcha darslarning TeacherIncome yozuvlarini 0 ga tushir
            extra_incomes = TeacherIncome.objects.filter(
                attendance_id__in=extra_ids
            ).exclude(amount=0)

            count = extra_incomes.count()
            if count == 0:
                continue

            total_fixed += count
            self.stdout.write(
                f"  Guruh {group_id} | Student {student_id} | {year}-{month:02d} | "
                f"dars={total_lessons} limit={limit} | ortiqcha={len(extra_ids)} | "
                f"income yozuv={count}"
            )

            if not dry_run:
                with transaction.atomic():
                    extra_incomes.update(amount=0, center_amount=0, total_amount=0)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDRY-RUN natija: {total_fixed} ta TeacherIncome 0 ga tushirilardi "
                f"({total_checked} ta (guruh,o'quvchi,oy) kombinatsiyada ortiqcha dars topildi)"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Tugadi: {total_fixed} ta TeacherIncome 0 ga tushirildi"
            ))
