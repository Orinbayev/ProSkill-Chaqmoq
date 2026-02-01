from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Center

User = get_user_model()

class Command(BaseCommand):
    help = "Create director for a Center"

    def add_arguments(self, parser):
        parser.add_argument("--center", required=True, help="center slug or id")
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--first_name", default="")
        parser.add_argument("--last_name", default="")

    def handle(self, *args, **opts):
        center_q = opts["center"]
        center = Center.objects.filter(slug=center_q).first() or Center.objects.filter(id=center_q).first()
        if not center:
            self.stderr.write("Center not found")
            return

        u = User(
            email=opts["email"],
            first_name=opts["first_name"],
            last_name=opts["last_name"],
            role="director",
            center=center,
        )
        u.set_password(opts["password"])
        u.save()
        self.stdout.write(self.style.SUCCESS(f"Director created: {u.email} / center={center.slug}"))
