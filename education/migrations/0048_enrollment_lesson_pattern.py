# Generated manually for enrollment lesson pattern support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("education", "0047_enrollment_active_lessons_count_enrollment_joined_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollment",
            name="lesson_pattern",
            field=models.CharField(
                choices=[
                    ("group", "Guruh jadvali"),
                    ("even", "Juft kunlar"),
                    ("odd", "Toq kunlar"),
                    ("daily", "Har kuni"),
                ],
                default="group",
                max_length=12,
                verbose_name="Dars patterni",
            ),
        ),
    ]
