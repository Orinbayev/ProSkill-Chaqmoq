import secrets

from django.db import migrations, models


CHILD_CODE_PREFIX = "CHQ"
CHILD_CODE_LENGTH = 6


def _generate_code() -> str:
    return (
        f"{CHILD_CODE_PREFIX}-"
        f"{secrets.randbelow(10 ** CHILD_CODE_LENGTH):0{CHILD_CODE_LENGTH}d}"
    )


def populate_student_child_codes(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    students = User.objects.filter(role="student").filter(
        models.Q(child_code__isnull=True) | models.Q(child_code="")
    )

    for student in students.iterator():
        while True:
            code = _generate_code()
            if not User.objects.filter(child_code=code).exists():
                student.child_code = code
                student.save(update_fields=["child_code"])
                break


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0043_center_director_telegram_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="child_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Ota-onalar mobil ilovada shu kod orqali farzandni bog‘laydi.",
                max_length=16,
                null=True,
                unique=True,
                verbose_name="Farzand bog‘lash kodi",
            ),
        ),
        migrations.RunPython(
            populate_student_child_codes,
            migrations.RunPython.noop,
        ),
    ]
