from django.db import migrations, models
from django.db.models import F


def backfill_added_to_group_at(apps, schema_editor):
    Lead = apps.get_model("store", "Lead")
    Lead.objects.filter(lead_group_id__isnull=False, added_to_group_at__isnull=True).update(
        added_to_group_at=F("qoshilgan_sana")
    )


def clear_added_to_group_at(apps, schema_editor):
    Lead = apps.get_model("store", "Lead")
    Lead.objects.filter(lead_group_id__isnull=False).update(added_to_group_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0025_lead_confirmed_at_lead_confirmed_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="added_to_group_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_added_to_group_at, clear_added_to_group_at),
    ]
