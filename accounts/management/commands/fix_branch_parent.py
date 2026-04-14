"""
Management command: python manage.py fix_branch_parent

DirectorCenterAccess orqali qaysi markazlar filial ekanini aniqlaydi va
parent_center_id ni o'rnatadi.

Ishlatish:
  python manage.py fix_branch_parent           # preview (hech narsa o'zgarmaydi)
  python manage.py fix_branch_parent --apply   # haqiqatdan o'zgartiradi
"""
from django.core.management.base import BaseCommand
from accounts.models import Center, DirectorCenterAccess
from billing.models import CenterSubscription


class Command(BaseCommand):
    help = "Filiallarning parent_center_id ni DirectorCenterAccess asosida to'g'irlaydi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="O'zgarishlarni bazaga yozish (bo'lmasa faqat preview)",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        mode = "APPLY" if apply else "PREVIEW (hech narsa o'zgarmaydi)"
        self.stdout.write(f"\n=== fix_branch_parent [{mode}] ===\n")

        fixed = 0
        skipped = 0

        # DirectorCenterAccess: qaysi direktor qaysi qo'shimcha markazga ega
        for access in DirectorCenterAccess.objects.filter(is_active=True).select_related(
            "director__center", "center"
        ):
            director = access.director
            primary = director.center        # Direktorning asosiy markazi
            branch = access.center           # Qo'shimcha markaz (filial bo'lishi kerak)

            if not primary:
                self.stdout.write(f"  SKIP: {director.email} — asosiy markazi yo'q")
                skipped += 1
                continue

            if primary.id == branch.id:
                skipped += 1
                continue

            if branch.parent_center_id == primary.id:
                self.stdout.write(
                    f"  ALREADY OK: {branch.name} (ID={branch.id}) -> {primary.name}"
                )
                skipped += 1
                continue

            self.stdout.write(
                f"  FIX: {branch.name} (ID={branch.id}) parent_center -> "
                f"{primary.name} (ID={primary.id})"
            )

            if apply:
                # parent_center o'rnatish
                branch.parent_center = primary
                branch.save(update_fields=["parent_center"])

                # Filialning o'z subscriptionini o'chirish
                # (asosiy markaznikidan foydalanadi)
                own_subs = CenterSubscription.objects.filter(center=branch)
                if own_subs.exists():
                    self.stdout.write(
                        f"    -> {own_subs.count()} ta o'z subscription o'chirildi"
                    )
                    own_subs.delete()

            fixed += 1

        self.stdout.write(f"\nNatija: {fixed} ta tuzatildi, {skipped} ta o'tkazib yuborildi")
        if not apply:
            self.stdout.write(
                "\nHaqiqatdan qo'llash uchun:\n"
                "  python manage.py fix_branch_parent --apply\n"
            )
