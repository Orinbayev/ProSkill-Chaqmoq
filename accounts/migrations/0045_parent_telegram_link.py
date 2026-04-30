from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0044_user_child_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="parent_telegram_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=50,
                null=True,
                verbose_name="Parent Telegram ID",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="parent_telegram_linked_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Parent Telegram ulangan sana",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="parent_telegram_username",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name="Parent Telegram Username",
            ),
        ),
        migrations.CreateModel(
            name="ParentTelegramLinkToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=96, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("used_by_telegram_id", models.CharField(blank=True, max_length=50, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_parent_telegram_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        limit_choices_to={"role": "student"},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parent_telegram_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "used_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="used_parent_telegram_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Parent Telegram link token",
                "verbose_name_plural": "Parent Telegram link tokenlari",
                "ordering": ["-created_at"],
            },
        ),
    ]
