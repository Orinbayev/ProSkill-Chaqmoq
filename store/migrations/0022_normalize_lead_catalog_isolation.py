from django.db import migrations


def normalize_lead_catalog_relations(apps, schema_editor):
    Lead = apps.get_model("store", "Lead")
    Manba = apps.get_model("store", "Manba")
    Yonalish = apps.get_model("store", "Yonalish")
    LeadStatus = apps.get_model("store", "LeadStatus")

    def remap_related(field_name, model):
        for lead in (
            Lead.objects.exclude(**{f"{field_name}__isnull": True})
            .select_related(field_name)
            .iterator()
        ):
            if not lead.center_id:
                continue

            related_obj = getattr(lead, field_name, None)
            if not related_obj:
                continue

            if getattr(related_obj, "center_id", None) == lead.center_id:
                continue

            candidate = None
            scoped_qs = model.objects.filter(center_id=lead.center_id)

            if field_name == "status":
                related_code = getattr(related_obj, "code", "")
                if related_code:
                    candidate = scoped_qs.filter(code=related_code).order_by("order", "id").first()
                if not candidate:
                    candidate = scoped_qs.filter(nom=getattr(related_obj, "nom", "")).order_by("order", "id").first()
            else:
                candidate = scoped_qs.filter(nom=getattr(related_obj, "nom", "")).order_by("id").first()

            setattr(lead, f"{field_name}_id", candidate.id if candidate else None)
            lead.save(update_fields=[field_name, "updated_at"])

    remap_related("manba", Manba)
    remap_related("yonalish", Yonalish)
    remap_related("status", LeadStatus)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0021_alter_leadactivity_action_alter_leadstatus_code_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_lead_catalog_relations, noop_reverse),
    ]
