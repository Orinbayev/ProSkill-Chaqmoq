from django.core.management.base import BaseCommand

from education.models import CertificateRecord
from education.services.certificate_service import PDF_LAYOUT_VERSION, regenerate_certificate_pdf


class Command(BaseCommand):
    help = (
        "Berilgan (issued) sertifikat PDF'larini joriy dizayn (layout) "
        "bo'yicha qayta generatsiya qiladi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--center-id",
            type=int,
            default=None,
            help="Faqat shu markaz sertifikatlari",
        )
        parser.add_argument(
            "--all-statuses",
            action="store_true",
            help="Faqat issued emas — draft/revoked ham (default: faqat issued)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Layout allaqachon yangi bo'lsa ham qayta yozadi",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Yozmasdan faqat ro'yxatni ko'rsatadi",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maksimal qayta yozish soni",
        )

    def handle(self, *args, **options):
        qs = (
            CertificateRecord.objects.select_related("center", "group", "student", "template", "summary")
            .order_by("id")
        )
        if not options.get("all_statuses"):
            qs = qs.filter(status=CertificateRecord.STATUS_ISSUED)
        center_id = options.get("center_id")
        if center_id:
            qs = qs.filter(center_id=center_id)

        total = qs.count()
        self.stdout.write(
            f"Layout target=v{PDF_LAYOUT_VERSION} | candidates={total} "
            f"| force={bool(options.get('force'))} dry_run={bool(options.get('dry_run'))}"
        )

        done = 0
        skipped = 0
        errors = 0
        limit = options.get("limit")

        for record in qs.iterator(chunk_size=50):
            if limit is not None and done >= limit:
                break

            meta = record.metadata if isinstance(record.metadata, dict) else {}
            current_layout = meta.get("pdf_layout_version")
            if not options.get("force") and current_layout == PDF_LAYOUT_VERSION and record.pdf_file:
                skipped += 1
                self.stdout.write(
                    f"  skip  id={record.id} {record.certificate_number} (already v{current_layout})"
                )
                continue

            if options.get("dry_run"):
                self.stdout.write(
                    f"  would id={record.id} {record.certificate_number} "
                    f"layout={current_layout!r} -> v{PDF_LAYOUT_VERSION}"
                )
                done += 1
                continue

            try:
                regenerate_certificate_pdf(record=record, request=None)
                done += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ok    id={record.id} {record.certificate_number} -> v{PDF_LAYOUT_VERSION}"
                    )
                )
            except Exception as exc:
                errors += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"  FAIL  id={record.id} {record.certificate_number}: {exc}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: regenerated={done} skipped={skipped} errors={errors} "
                f"(layout v{PDF_LAYOUT_VERSION})"
            )
        )
