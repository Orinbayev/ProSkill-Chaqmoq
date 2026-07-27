"""«Tasdiqlangan, lekin markazi yo'q» filial so'rovlarini tuzatadi.

Nima uchun kerak?

Ilgari Django admin'da `BranchRequest.status` oddiy tahrirlanadigan maydon
edi. Uni qo'lda "approved" qilib qo'yish faqat ustunni yozardi — markaz
yaratilmasdi, direktorga ruxsat berilmasdi. Natijada ariza tasdiqlangandek
ko'rinardi, filial esa hech qayerda yo'q edi.

Buyruq shunday qatorlarni topib, ular uchun markazni haqiqatan yaratadi.

    python manage.py filiallarni_tuzat            # nima bo'lishini ko'rsatadi
    python manage.py filiallarni_tuzat --bajar    # haqiqatan tuzatadi
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import BranchRequest
from accounts.services import branch_requests as branch_service


class Command(BaseCommand):
    help = "Tasdiqlangan, lekin markazi yaratilmagan filial so'rovlarini tuzatadi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--bajar",
            action="store_true",
            help="Haqiqatan tuzatadi. Busiz faqat ro'yxatni ko'rsatadi.",
        )

    def handle(self, *args, **options):
        bajar = options["bajar"]

        nosozlar = (
            BranchRequest.objects
            .filter(status=BranchRequest.Status.APPROVED, created_center__isnull=True)
            .select_related("requester", "parent_center")
            .order_by("created_at")
        )

        if not nosozlar:
            self.stdout.write(self.style.SUCCESS("Nosoz so'rov yo'q — hammasi joyida."))
            return

        self.stdout.write(
            self.style.WARNING(f"{nosozlar.count()} ta nosoz so'rov topildi:\n")
        )

        tuzatildi, xatolar = 0, 0
        for so_rov in nosozlar:
            tavsif = (
                f"  #{so_rov.pk} «{so_rov.name}» "
                f"(asosiy: {so_rov.parent_center}, so'rovchi: {so_rov.requester})"
            )

            if not bajar:
                self.stdout.write(tavsif)
                continue

            try:
                markaz = branch_service.tasdiqla(so_rov)
            except branch_service.FilialXatosi as xato:
                xatolar += 1
                self.stdout.write(self.style.ERROR(f"{tavsif} → {xato}"))
            except Exception as xato:  # noqa: BLE001 — bittasi yiqilsa qolgani davom etsin
                xatolar += 1
                self.stdout.write(self.style.ERROR(f"{tavsif} → kutilmagan xato: {xato}"))
            else:
                tuzatildi += 1
                self.stdout.write(
                    self.style.SUCCESS(f"{tavsif} → markaz #{markaz.pk} yaratildi")
                )

        self.stdout.write("")
        if not bajar:
            self.stdout.write(
                "Bu faqat ro'yxat edi. Tuzatish uchun:\n"
                "  python manage.py filiallarni_tuzat --bajar"
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Tuzatildi: {tuzatildi}"))
        if xatolar:
            self.stdout.write(self.style.ERROR(f"Xatolik: {xatolar}"))
