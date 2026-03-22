from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0033_adminauditlog_db_host_adminauditlog_db_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="center",
            name="db_host",
            field=models.CharField(blank=True, help_text="Хост БД центра", max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="center",
            name="db_name",
            field=models.CharField(blank=True, help_text="Имя отдельной базы данных центра (PostgreSQL)", max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="center",
            name="db_password",
            field=models.CharField(blank=True, help_text="Пароль БД центра (TODO: хранить безопасно, использовать env или vault)", max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="center",
            name="db_port",
            field=models.CharField(blank=True, help_text="Порт БД центра", max_length=16, null=True),
        ),
        migrations.AddField(
            model_name="center",
            name="db_user",
            field=models.CharField(blank=True, help_text="Пользователь БД центра", max_length=128, null=True),
        ),
    ]
