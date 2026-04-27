from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


def populate_enrollment_course(apps, schema_editor):
    Enrollment = apps.get_model("education", "Enrollment")

    for enrollment in Enrollment.objects.select_related("group__category_obj").all():
        group = getattr(enrollment, "group", None)
        enrollment.course_id = getattr(group, "category_obj_id", None)
        enrollment.save(update_fields=["course"])


class Migration(migrations.Migration):

    dependencies = [
        ("education", "0048_enrollment_lesson_pattern"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollment",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="enrollments",
                to="education.category",
                verbose_name="Fan",
            ),
        ),
        migrations.AddField(
            model_name="enrollment",
            name="last_lesson_date",
            field=models.DateField(blank=True, null=True, verbose_name="Oxirgi dars sanasi"),
        ),
        migrations.AddField(
            model_name="enrollment",
            name="remaining_lessons_override",
            field=models.PositiveIntegerField(
                blank=True,
                default=None,
                help_text="Bo'sh bo'lsa tizim avtomatik qolgan dars sonini ishlatadi.",
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(999),
                ],
                verbose_name="Qo'lda kiritilgan qolgan dars",
            ),
        ),
        migrations.RunPython(populate_enrollment_course, migrations.RunPython.noop),
    ]
