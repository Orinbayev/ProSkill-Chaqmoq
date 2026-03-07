from django.core.management.base import BaseCommand
from accounts.models import User, BotAdmin

class Command(BaseCommand):
    help = 'Create a new Telegram Bot Admin'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email')
        parser.add_argument('tg_id', type=str, help='Telegram ID')

    def handle(self, *args, **options):
        email = options['email']
        tg_id = options['tg_id']

        user = User.objects.filter(email=email).first()
        if not user:
            self.stdout.write(self.style.ERROR(f'User with email {email} not found'))
            return

        # Ensure user is linked
        user.telegram_id = tg_id
        user.is_telegram_linked = True
        user.save()

        admin, created = BotAdmin.objects.get_or_create(
            user=user,
            defaults={'telegram_id': tg_id}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Successfully created Bot Admin for {user.full_name()}'))
        else:
            admin.telegram_id = tg_id
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Bot Admin for {user.full_name()} already exists, updated ID'))
