"""
Center.telegram_bot_enabled — Telegram (Oila) botni har markaz uchun superadmin
yoqadi. Yangi markazlar default o'chiq, lekin MAVJUD (o'chirilmagan) markazlar
grandfather qilinadi (True) — hozir botdan foydalanayotganlar buzilmasin.
"""
from django.db import migrations, models


def grandfather_existing(apps, schema_editor):
    Center = apps.get_model("accounts", "Center")
    Center.objects.filter(is_deleted=False).update(telegram_bot_enabled=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0049_center_role_ai_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="center",
            name="telegram_bot_enabled",
            field=models.BooleanField(default=False, db_index=True, verbose_name="Telegram bot yoqilgan"),
        ),
        migrations.RunPython(grandfather_existing, noop),
    ]
