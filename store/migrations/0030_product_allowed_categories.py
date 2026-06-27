from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0029_lead_bilim_darajasi_lead_parent_name'),
        ('education', '0058_alter_attendance_status_late'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='allowed_categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='restricted_products',
                to='education.category',
                verbose_name="Ko'rinadigan bo'limlar (bo'sh = hammaga)",
            ),
        ),
    ]
