from django.core.management.base import BaseCommand, CommandError
from accounts.models import Center
from core.db_config import build_tenant_db_config

class Command(BaseCommand):
    help = 'Show resolved tenant DB config for a center (diagnostic only)'

    def add_arguments(self, parser):
        parser.add_argument('center_slug', type=str, help='Center slug')

    def handle(self, *args, **options):
        slug = options['center_slug']
        try:
            center = Center.objects.get(slug=slug)
        except Center.DoesNotExist:
            raise CommandError(f'Center with slug "{slug}" does not exist')
        try:
            config = build_tenant_db_config(center)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
            return
        self.stdout.write(self.style.SUCCESS(f'DB config for center "{center.name}" ({center.slug}):'))
        for k, v in config.items():
            self.stdout.write(f'  {k}: {v}')

