from django.db import migrations


def add_feature(apps, schema_editor):
    PlanFeature = apps.get_model("billing", "PlanFeature")
    PlanFeature.objects.update_or_create(
        code="manual_oy_dars_soni",
        defaults={
            "name": "Qo'lda oylik dars soni",
            "name_uz": "Qo'lda oylik dars soni",
            "description": (
                "Guruhga bir oyda o'tiladigan darslar sonini qo'lda belgilash imkoni. "
                "Yoqilmagan holda tizim har doim standart 12 dars bilan hisoblaydi."
            ),
            "description_uz": (
                "Guruhga bir oyda o'tiladigan darslar sonini qo'lda belgilash imkoni. "
                "Yoqilmagan holda tizim har doim standart 12 dars bilan hisoblaydi."
            ),
            "category": "billing",
            "icon": "🔢",
            "is_core": False,
            "is_active": True,
            "order": 10,
            "implementation_status": "READY",
            "show_on_landing": False,
            "is_highlight": False,
        },
    )


def remove_feature(apps, schema_editor):
    PlanFeature = apps.get_model("billing", "PlanFeature")
    PlanFeature.objects.filter(code="manual_oy_dars_soni").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0024_seed_plan_features"),
    ]

    operations = [
        migrations.RunPython(add_feature, remove_feature),
    ]
