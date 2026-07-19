"""
O'quvchilar uchun bildirishnoma doim yoniq bo'lsin — bot menyusidagi
"Sozlamalar" (bildirishnoma o'chirish) tugmasi olib tashlandi, shu sabab
avval o'chirib qo'yganlarni qayta yoqamiz.
"""
from django.db import migrations


def enable_for_students(apps, schema_editor):
    NotificationPreference = apps.get_model("core", "NotificationPreference")
    NotificationPreference.objects.filter(user__role="student").update(
        receive_coin=True,
        receive_broadcast=True,
        receive_purchase=True,
        receive_system=True,
    )


def noop(apps, schema_editor):
    # Ortga qaytarishda hech narsa qilmaymiz (o'chirilgan holatni tiklamaymiz).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_chatpresence_typing_until"),
    ]

    operations = [
        migrations.RunPython(enable_for_students, noop),
    ]
