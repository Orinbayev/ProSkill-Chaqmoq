from django.core.management.base import BaseCommand
from django.db.models import Q

from accounts.models import Roles, User


class Command(BaseCommand):
    help = "Generate missing mobile child link codes for existing students."

    def handle(self, *args, **options):
        students = User.all_objects.filter(role=Roles.OQUVCHI).filter(
            Q(child_code__isnull=True) | Q(child_code="")
        )
        updated = 0

        for student in students.iterator():
            student.child_code = User.generate_unique_child_code()
            student.save(update_fields=["child_code"])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Student link codes ready. Updated {updated} student(s)."
            )
        )
