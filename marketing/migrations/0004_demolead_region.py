from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0003_alter_demolead_options_alter_faq_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='demolead',
            name='region',
            field=models.CharField(
                blank=True,
                choices=[
                    ('andijon', 'Andijon'),
                    ('buxoro', 'Buxoro'),
                    ('fargona', "Farg'ona"),
                    ('jizzax', 'Jizzax'),
                    ('xorazm', 'Xorazm'),
                    ('namangan', 'Namangan'),
                    ('navoiy', 'Navoiy'),
                    ('qashqadaryo', 'Qashqadaryo'),
                    ('qoraqalpogiston', "Qoraqalpog'iston Respublikasi"),
                    ('samarqand', 'Samarqand'),
                    ('sirdaryo', 'Sirdaryo'),
                    ('surxondaryo', 'Surxondaryo'),
                    ('toshkent_viloyat', 'Toshkent viloyati'),
                    ('toshkent_shahar', 'Toshkent shahri'),
                ],
                max_length=60,
                verbose_name='Viloyat',
            ),
        ),
    ]
