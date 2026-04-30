from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0036_perf_indexes"),
        ("education", "0049_enrollment_course_and_lesson_planning"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentGroupTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transfer_date", models.DateField()),
                ("reason", models.TextField(blank=True, default="")),
                ("old_payment_state", models.JSONField(blank=True, default=dict)),
                ("old_attendance_summary", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("center", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_group_transfers", to="accounts.center")),
                ("new_group", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transfers", to="education.group")),
                ("old_group", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transfers", to="education.group")),
                ("performed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performed_group_transfers", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_transfers", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "O'quvchi guruh ko'chirish tarixi",
                "verbose_name_plural": "O'quvchi guruh ko'chirish tarixlari",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="studentgrouptransfer",
            index=models.Index(fields=["center", "student", "transfer_date"], name="sgt_center_student_date_idx"),
        ),
        migrations.AddIndex(
            model_name="studentgrouptransfer",
            index=models.Index(fields=["old_group", "new_group"], name="sgt_groups_idx"),
        ),
    ]
