from django.db import migrations, models


def _infer_subject(name: str) -> str:
    normalized = (name or "").strip().lower()
    if "ielts" in normalized:
        return "ielts"
    if "matem" in normalized or "math" in normalized:
        return "math"
    if "rus" in normalized or "russian" in normalized:
        return "russian"
    if "english" in normalized or "ingliz" in normalized:
        return "general_english"
    return "other"


def backfill_lead_subject(apps, schema_editor):
    Lead = apps.get_model("store", "Lead")
    for lead in Lead.objects.select_related("yonalish").all().iterator():
        direction_name = getattr(getattr(lead, "yonalish", None), "nom", "") or ""
        lead.subject = _infer_subject(direction_name)
        lead.save(update_fields=["subject"])


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0022_normalize_lead_catalog_isolation"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="subject",
            field=models.CharField(
                choices=[
                    ("ielts", "IELTS"),
                    ("general_english", "General English"),
                    ("math", "Matematika"),
                    ("russian", "Rus tili"),
                    ("other", "Boshqa"),
                ],
                db_index=True,
                default="other",
                max_length=24,
            ),
        ),
        migrations.RunPython(backfill_lead_subject, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(fields=["center", "subject"], name="store_lead_center_subject_idx"),
        ),
    ]
