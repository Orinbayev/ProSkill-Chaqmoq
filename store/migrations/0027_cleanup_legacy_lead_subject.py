from django.db import migrations


def cleanup_legacy_lead_subject(apps, schema_editor):
    connection = schema_editor.connection
    introspection = connection.introspection
    quote_name = schema_editor.quote_name
    table_name = "store_lead"
    legacy_column = "subject"
    legacy_index = "store_lead_center_subject_idx"
    dependent_indexes = set()

    with connection.cursor() as cursor:
        table_names = set(introspection.table_names(cursor))
        if table_name not in table_names:
            return

        try:
            column_names = {
                column.name
                for column in introspection.get_table_description(cursor, table_name)
            }
        except Exception:
            column_names = set()

        try:
            constraints = introspection.get_constraints(cursor, table_name)
        except Exception:
            constraints = {}

    for name, details in constraints.items():
        if legacy_column in set(details.get("columns") or []):
            dependent_indexes.add(name)

    dependent_indexes.add(legacy_index)

    for index_name in sorted(dependent_indexes):
        schema_editor.execute(f"DROP INDEX IF EXISTS {quote_name(index_name)}")

    if legacy_column not in column_names:
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            f"ALTER TABLE {quote_name(table_name)} "
            f"DROP COLUMN IF EXISTS {quote_name(legacy_column)} CASCADE"
        )
        return

    schema_editor.execute(
        f"ALTER TABLE {quote_name(table_name)} DROP COLUMN {quote_name(legacy_column)}"
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("store", "0026_lead_added_to_group_at"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(cleanup_legacy_lead_subject, noop_reverse),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="lead",
                    name="store_lead_center_subject_idx",
                ),
                migrations.RemoveField(
                    model_name="lead",
                    name="subject",
                ),
            ],
        ),
    ]
