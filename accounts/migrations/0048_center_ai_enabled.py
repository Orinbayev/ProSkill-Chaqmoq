from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0047_add_instagram_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='center',
            name='ai_enabled',
            field=models.BooleanField(default=False, verbose_name='AI Yordamchi yoqilgan'),
        ),
    ]
