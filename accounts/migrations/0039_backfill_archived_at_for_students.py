from django.db import migrations
from django.utils import timezone


def backfill_archived_at(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        role="student",
        is_archived=True,
        archived_at__isnull=True,
    ).update(archived_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0038_user_archived_at"),
    ]

    operations = [
        migrations.RunPython(backfill_archived_at, migrations.RunPython.noop),
    ]
