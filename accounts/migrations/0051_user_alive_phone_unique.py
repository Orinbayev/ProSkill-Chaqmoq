# Generated manually for phase 6: unique login phone among alive users.

from django.db import migrations, models
from django.db.models import Count


def _normalize_phone_value(phone: str) -> str:
    import re

    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if len(digits) > 12 and digits.startswith("00") and digits[2:5] == "998":
        return f"+{digits[2:]}"
    if len(digits) == 13 and digits.startswith("0") and digits[1:4] == "998":
        return f"+{digits[1:]}"
    if len(digits) == 12:
        return f"+{digits}"
    return f"+{digits}" if digits else ""


def clean_phone_numbers(apps, schema_editor):
    """
    1) Blank phones → NULL
    2) Normalize remaining values
    3) Among alive users, keep lowest pk per phone; clear duplicates
    """
    User = apps.get_model("accounts", "User")

    # Empty string → NULL (bulk)
    User.objects.filter(phone_number="").update(phone_number=None)

    for user in User.objects.exclude(phone_number__isnull=True).iterator():
        raw = (user.phone_number or "").strip()
        if not raw:
            if user.phone_number is not None:
                user.phone_number = None
                user.save(update_fields=["phone_number"])
            continue
        normalized = _normalize_phone_value(raw) or None
        if normalized != user.phone_number:
            user.phone_number = normalized
            user.save(update_fields=["phone_number"])

    # Resolve duplicates among alive (is_deleted=False) non-null phones
    dup_phones = (
        User.objects.filter(is_deleted=False)
        .exclude(phone_number__isnull=True)
        .values("phone_number")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )
    for row in dup_phones:
        phone = row["phone_number"]
        ids = list(
            User.objects.filter(is_deleted=False, phone_number=phone)
            .order_by("id")
            .values_list("id", flat=True)
        )
        # Keep first, null the rest
        for uid in ids[1:]:
            User.objects.filter(pk=uid).update(phone_number=None)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0050_center_telegram_bot_enabled"),
    ]

    operations = [
        migrations.RunPython(clean_phone_numbers, noop_reverse),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False, phone_number__isnull=False),
                fields=("phone_number",),
                name="user_alive_phone_unique",
            ),
        ),
    ]
