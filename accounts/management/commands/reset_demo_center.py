from django.core.management.base import BaseCommand, CommandError

from accounts.services.demo_center_service import (
    DEMO_CENTER_SLUG,
    DEMO_PASSWORD_DEFAULT,
    reset_demo_center,
    seed_demo_center,
)


class Command(BaseCommand):
    help = "Safely reset demo-center data only. Optionally reseeds baseline data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            default=DEMO_CENTER_SLUG,
            help=f"Demo center slug (default: {DEMO_CENTER_SLUG})",
        )
        parser.add_argument(
            "--password",
            default=DEMO_PASSWORD_DEFAULT,
            help="Password to use when reseeding demo users.",
        )
        parser.add_argument(
            "--no-seed",
            action="store_true",
            help="Only reset; do not reseed demo data afterwards.",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        password = options["password"]
        do_seed = not bool(options["no_seed"])

        try:
            reset_result = reset_demo_center(slug=slug)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        if not reset_result.get("center_found"):
            self.stdout.write(
                self.style.WARNING(
                    f"Demo center not found for slug '{slug}'."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo center reset completed for slug '{slug}'."
            )
        )

        if not do_seed:
            self.stdout.write("Reseed skipped (--no-seed).")
            return

        try:
            seed_result = seed_demo_center(
                slug=slug,
                password=password,
                reset_before_seed=False,
            )
        except Exception as exc:
            raise CommandError(f"Reset done, but reseed failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo center reseeded: id={seed_result['center_id']} slug={seed_result['center_slug']}"
            )
        )
