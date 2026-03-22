from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction


def _resolve_model(label: str):
    try:
        app_label, model_name = label.split(".", 1)
    except ValueError as exc:
        raise CommandError(f"Invalid model label in snapshot: {label}") from exc
    model = apps.get_model(app_label, model_name)
    if model is None:
        raise CommandError(f"Model not found for label: {label}")
    return model


def _topological_model_order(model_map: dict[str, type[models.Model]]) -> list[str]:
    adjacency: dict[str, set[str]] = {label: set() for label in model_map}
    indegree: dict[str, int] = {label: 0 for label in model_map}

    for label, model in model_map.items():
        for field in model._meta.fields:
            if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            related_model = field.related_model
            if related_model is None:
                continue
            related_label = related_model._meta.label_lower
            if related_label in model_map and related_label != label:
                if label not in adjacency[related_label]:
                    adjacency[related_label].add(label)
                    indegree[label] += 1

    queue = deque(sorted([label for label, deg in indegree.items() if deg == 0]))
    ordered: list[str] = []
    while queue:
        node = queue.popleft()
        ordered.append(node)
        for nxt in sorted(adjacency[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(ordered) != len(model_map):
        remaining = sorted([label for label in model_map if label not in ordered])
        ordered.extend(remaining)

    return ordered


class Command(BaseCommand):
    help = (
        "Restore one center-scoped JSON backup. "
        "By default this is dry-run only. Use --apply to write create/update changes."
    )

    def add_arguments(self, parser):
        parser.add_argument("snapshot", type=str, help="Path to center snapshot JSON file")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply restore (without this flag, command only validates and prints summary).",
        )
        parser.add_argument(
            "--center-slug",
            type=str,
            default="",
            help="Safety check: expected center slug from snapshot meta.",
        )
        parser.add_argument(
            "--database",
            type=str,
            default="default",
            help="Database alias to restore into (default: default).",
        )

    def handle(self, *args, **options):
        snapshot_path = Path(options["snapshot"]).expanduser().resolve()
        apply_restore = bool(options["apply"])
        expected_center_slug = str(options.get("center_slug") or "").strip()
        database_alias = str(options.get("database") or "default").strip() or "default"

        if not snapshot_path.exists() or not snapshot_path.is_file():
            raise CommandError(f"Snapshot file not found: {snapshot_path}")

        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CommandError(f"Invalid JSON snapshot: {snapshot_path}") from exc

        if not isinstance(payload, dict):
            raise CommandError("Snapshot root must be an object with meta and objects")

        meta = payload.get("meta") or {}
        objects = payload.get("objects")

        if not isinstance(meta, dict):
            raise CommandError("Snapshot meta must be an object")
        if meta.get("type") != "center_scoped_snapshot":
            raise CommandError("Unsupported snapshot type; expected center_scoped_snapshot")
        if not isinstance(objects, list):
            raise CommandError("Snapshot objects must be a list")

        center_slug = str(meta.get("center_slug") or "").strip()
        center_id = meta.get("center_id")

        if expected_center_slug and expected_center_slug != center_slug:
            raise CommandError(
                f"Center slug mismatch: snapshot={center_slug!r}, expected={expected_center_slug!r}"
            )

        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in objects:
            if not isinstance(item, dict):
                raise CommandError("Each snapshot object must be a JSON object")
            model_label = str(item.get("model") or "").strip()
            if not model_label:
                raise CommandError("Snapshot object missing 'model'")
            if "pk" not in item:
                raise CommandError(f"Snapshot object missing 'pk' for model {model_label}")
            fields = item.get("fields")
            if not isinstance(fields, dict):
                raise CommandError(f"Snapshot object has invalid 'fields' for model {model_label}")
            grouped[model_label].append(item)

        model_map = {label: _resolve_model(label) for label in grouped}
        model_order = _topological_model_order(model_map)

        total_objects = sum(len(rows) for rows in grouped.values())
        self.stdout.write(
            self.style.WARNING(
                "Restore preview: "
                f"file={snapshot_path} center_slug={center_slug or '-'} center_id={center_id} "
                f"models={len(grouped)} objects={total_objects} apply={apply_restore} db={database_alias}"
            )
        )

        for label in model_order:
            self.stdout.write(f" - {label}: {len(grouped[label])}")

        if not apply_restore:
            self.stdout.write(
                self.style.SUCCESS(
                    "Dry-run complete. No data changed. Re-run with --apply to execute restore."
                )
            )
            return

        created_count = 0
        updated_count = 0
        m2m_updated_count = 0

        with transaction.atomic(using=database_alias):
            for label in model_order:
                model = model_map[label]
                m2m_fields = {field.name for field in model._meta.many_to_many}
                fk_attnames = {
                    field.name: field.attname
                    for field in model._meta.fields
                    if isinstance(field, (models.ForeignKey, models.OneToOneField))
                }
                manager = model._default_manager.db_manager(database_alias)

                for item in sorted(grouped[label], key=lambda row: str(row.get("pk"))):
                    pk = item["pk"]
                    fields = dict(item.get("fields") or {})
                    defaults = {}
                    for key, value in fields.items():
                        if key in m2m_fields:
                            continue
                        defaults[fk_attnames.get(key, key)] = value

                    instance, created = manager.update_or_create(pk=pk, defaults=defaults)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                    for m2m_name in m2m_fields:
                        if m2m_name in fields:
                            values = fields[m2m_name] or []
                            getattr(instance, m2m_name).set(values)
                            m2m_updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Restore applied successfully: "
                f"created={created_count} updated={updated_count} m2m_updated={m2m_updated_count} "
                f"total={total_objects} center_slug={center_slug or '-'}"
            )
        )
