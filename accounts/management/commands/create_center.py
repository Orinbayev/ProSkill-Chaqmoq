from django.core.management.base import BaseCommand
from accounts.models import Center

class Command(BaseCommand):
    help = "Create a new Center"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--address", default="")
        parser.add_argument("--slug", default="")

    def handle(self, *args, **opts):
        c = Center(name=opts["name"], address=opts["address"])
        if opts["slug"]:
            c.slug = opts["slug"]
        c.save()
        self.stdout.write(self.style.SUCCESS(f"Center created: {c.id} {c.name} ({c.slug})"))
