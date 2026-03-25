from django.core.management.base import BaseCommand, CommandError

from accounts.services.demo_center_service import (
    DEMO_CENTER_SLUG,
    DEMO_PASSWORD_DEFAULT,
    seed_demo_center,
)


class Command(BaseCommand):
    help = "Create or refresh a safe demo center with realistic sample data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            default=DEMO_CENTER_SLUG,
            help=f"Demo center slug (default: {DEMO_CENTER_SLUG})",
        )
        parser.add_argument(
            "--password",
            default=DEMO_PASSWORD_DEFAULT,
            help="Password for all seeded demo users.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset demo center data before seeding.",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        password = options["password"]
        reset = bool(options["reset"])

        try:
            result = seed_demo_center(
                slug=slug,
                password=password,
                reset_before_seed=reset,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo center ready: id={result['center_id']} slug={result['center_slug']}"
            )
        )
        self.stdout.write(
            f"Users={result['users_total']} | Groups={result['groups_total']} | "
            f"Students={result['students_total']} | Parents={result['parents_total']}"
        )
        self.stdout.write("Demo credentials:")
        for item in result.get("credentials", []):
            self.stdout.write(
                f" - {item['role']}: {item['email']} / {item['password']}"
            )
