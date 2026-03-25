from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0034_center_db_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="center",
            name="is_demo",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Demo markazmi (savdo/demo uchun test ma'lumotlar).",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_demo_user",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Demo markaz uchun yaratilgan test foydalanuvchi.",
                verbose_name="Demo foydalanuvchi",
            ),
        ),
    ]
