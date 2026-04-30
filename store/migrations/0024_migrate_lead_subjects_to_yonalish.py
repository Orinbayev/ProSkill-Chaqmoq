from django.db import migrations, models


DEFAULT_SUBJECTS = [
    ("IELTS", "#3b82f6"),
    ("General English", "#64748b"),
    ("Matematika", "#22c55e"),
    ("Rus tili", "#f59e0b"),
    ("Boshqa", "#94a3b8"),
]


def _resolve_subject_name(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "Boshqa"
    if normalized == "ielts" or "ielts" in normalized:
        return "IELTS"
    if normalized in {"general_english", "general english"} or "english" in normalized or "ingliz" in normalized:
        return "General English"
    if normalized == "math" or "matem" in normalized or "math" in normalized:
        return "Matematika"
    if normalized == "russian" or "rus" in normalized or "russian" in normalized:
        return "Rus tili"
    if normalized == "other":
        return "Boshqa"
    return (value or "").strip() or "Boshqa"


def _resolve_subject_color(name: str) -> str:
    normalized = (name or "").strip().lower()
    if "ielts" in normalized:
        return "#3b82f6"
    if "matem" in normalized or "math" in normalized:
        return "#22c55e"
    if "rus" in normalized or "russian" in normalized:
        return "#f59e0b"
    if "english" in normalized or "ingliz" in normalized:
        return "#64748b"
    return "#94a3b8"


def migrate_lead_subjects(apps, schema_editor):
    Lead = apps.get_model("store", "Lead")
    Yonalish = apps.get_model("store", "Yonalish")

    subject_cache = {}

    def get_or_create_subject(center_id, name: str):
        resolved_name = _resolve_subject_name(name)
        cache_key = (center_id, resolved_name.lower())
        if cache_key in subject_cache:
            return subject_cache[cache_key]

        subject = (
            Yonalish.objects.filter(center_id=center_id, nom__iexact=resolved_name)
            .order_by("id")
            .first()
        )
        color = _resolve_subject_color(resolved_name)
        if subject:
            changed = False
            if not subject.color:
                subject.color = color
                changed = True
            if not subject.is_active:
                subject.is_active = True
                changed = True
            if changed:
                subject.save(update_fields=["color", "is_active"])
        else:
            subject = Yonalish.objects.create(
                center_id=center_id,
                nom=resolved_name,
                color=color,
                is_active=True,
            )
        subject_cache[cache_key] = subject
        return subject

    center_ids = set(
        Lead.objects.exclude(center_id__isnull=True).values_list("center_id", flat=True).distinct()
    )
    center_ids.update(
        Yonalish.objects.exclude(center_id__isnull=True).values_list("center_id", flat=True).distinct()
    )

    for center_id in center_ids:
        for subject_name, _ in DEFAULT_SUBJECTS:
            get_or_create_subject(center_id, subject_name)

    for subject in Yonalish.objects.all().iterator():
        changed = False
        if not subject.color:
            subject.color = _resolve_subject_color(subject.nom)
            changed = True
        if not subject.is_active:
            subject.is_active = True
            changed = True
        if changed:
            subject.save(update_fields=["color", "is_active"])

    for lead in Lead.objects.all().iterator():
        if lead.yonalish_id:
            subject = Yonalish.objects.filter(id=lead.yonalish_id).first()
            if subject:
                changed = False
                if not subject.color:
                    subject.color = _resolve_subject_color(subject.nom)
                    changed = True
                if not subject.is_active:
                    subject.is_active = True
                    changed = True
                if changed:
                    subject.save(update_fields=["color", "is_active"])
            continue

        legacy_subject = getattr(lead, "subject", "") or ""
        subject_name = _resolve_subject_name(legacy_subject)
        subject = get_or_create_subject(lead.center_id, subject_name)
        if subject:
            lead.yonalish_id = subject.id
            lead.save(update_fields=["yonalish"])


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0023_lead_subject_and_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="yonalish",
            name="color",
            field=models.CharField(blank=True, default="#64748b", max_length=20),
        ),
        migrations.AddField(
            model_name="yonalish",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="yonalish",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterModelOptions(
            name="yonalish",
            options={"ordering": ("nom",)},
        ),
        migrations.RunPython(migrate_lead_subjects, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="lead",
            name="store_lead_center_subject_idx",
        ),
        migrations.RemoveField(
            model_name="lead",
            name="subject",
        ),
    ]
