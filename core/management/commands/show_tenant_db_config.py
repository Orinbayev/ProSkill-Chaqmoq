from django.core.management.base import BaseCommand, CommandError

from accounts.models import Center
from core.db_config import (
    build_tenant_db_config,
    center_has_dedicated_db,
    mask_db_config,
    resolve_routing_center,
    resolve_tenant_db_password,
    tenant_db_routing_enabled,
)
from core.db_router import resolve_tenant_db_alias, uses_default_database


class Command(BaseCommand):
    help = "Show resolved tenant DB config for a center (password masked)"

    def add_arguments(self, parser):
        parser.add_argument("center_slug", type=str, help="Center slug")
        parser.add_argument(
            "--show-password-set",
            action="store_true",
            help="Print whether a password is configured (not the value)",
        )

    def handle(self, *args, **options):
        slug = options["center_slug"]
        try:
            center = Center.objects.get(slug=slug)
        except Center.DoesNotExist as exc:
            raise CommandError(f'Center with slug "{slug}" does not exist') from exc

        root = resolve_routing_center(center)
        self.stdout.write(
            self.style.SUCCESS(
                f'Center "{center.name}" ({center.slug}) root={getattr(root, "slug", None)}'
            )
        )
        self.stdout.write(f"  TENANT_DB_ROUTING_ENABLED: {tenant_db_routing_enabled()}")
        self.stdout.write(f"  has_dedicated_db_name: {center_has_dedicated_db(center)}")

        if not center_has_dedicated_db(center):
            self.stdout.write(self.style.WARNING("  No db_name on root — would use default DB"))
            return

        try:
            config = build_tenant_db_config(center)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error: {exc}"))
            return

        alias = resolve_tenant_db_alias(center)
        self.stdout.write(f"  resolved_alias: {alias}")
        self.stdout.write(f"  uses_default_database: {uses_default_database(config)}")
        if options.get("show_password_set"):
            self.stdout.write(
                f"  password_configured: {bool(resolve_tenant_db_password(root))}"
            )

        self.stdout.write("  config:")
        for key, value in mask_db_config(config).items():
            self.stdout.write(f"    {key}: {value}")
