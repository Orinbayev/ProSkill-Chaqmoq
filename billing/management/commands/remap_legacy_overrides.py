from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import PlanFeature, CenterFeatureOverride
from billing.services import LEGACY_CODE_MAP


class Command(BaseCommand):
    help = "Remap CenterFeatureOverride rows from legacy feature codes to v2 codes."

    def handle(self, *args, **opts):
        remapped = 0
        deleted_dupes = 0
        with transaction.atomic():
            for legacy_code, v2_code in LEGACY_CODE_MAP.items():
                if legacy_code == v2_code:
                    continue
                v2_feature = PlanFeature.objects.filter(code=v2_code).first()
                legacy_feature = PlanFeature.objects.filter(code=legacy_code).first()
                if not v2_feature or not legacy_feature:
                    continue
                # For each override pointing at legacy_feature, repoint to v2_feature.
                # If a v2 override already exists for the same center, keep the legacy
                # value (it's more specific) and delete the v2 row first to avoid
                # unique_together collision.
                for ov in CenterFeatureOverride.objects.filter(feature=legacy_feature):
                    existing = CenterFeatureOverride.objects.filter(
                        center=ov.center, feature=v2_feature
                    ).first()
                    if existing and existing.id != ov.id:
                        existing.delete()
                        deleted_dupes += 1
                    ov.feature = v2_feature
                    ov.note = (ov.note or "") + f" [remapped from {legacy_code}]"
                    ov.save()
                    remapped += 1
        self.stdout.write(self.style.SUCCESS(
            f"Remapped {remapped} overrides; deleted {deleted_dupes} duplicate v2 rows."
        ))
