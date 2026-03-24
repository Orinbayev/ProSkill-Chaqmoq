import io
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from .models import PricingFeature, PricingPlan
from .pricing_plan_io import (
    IMPORT_MODE_SKIP_DUPLICATES,
    IMPORT_MODE_UPDATE_EXISTING,
    PricingPlanExportService,
    PricingPlanImportService,
)


class PricingPlanIOServiceTests(TestCase):
    def _build_xlsx_upload(self, headers, rows, filename="pricing-import.xlsx"):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)

        stream = io.BytesIO()
        workbook.save(stream)
        return SimpleUploadedFile(
            filename,
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_import_excel_creates_plan_and_features(self):
        headers = [
            "name",
            "student_range",
            "duration_months",
            "current_price",
            "old_price",
            "badge_text",
            "discount_label",
            "is_recommended",
            "is_active",
            "order",
            "highlight_features",
            "detail_features",
        ]
        rows = [
            [
                "Standart",
                "0-200 ta",
                3,
                "390000",
                "450000",
                "Yangi",
                "-13%",
                "true",
                "true",
                1,
                "Guruhlar|Dashboard",
                "Hisobotlar|Support",
            ]
        ]
        uploaded_file = self._build_xlsx_upload(headers, rows)

        result = PricingPlanImportService().import_file(
            uploaded_file=uploaded_file,
            mode=IMPORT_MODE_UPDATE_EXISTING,
            file_format="xlsx",
        )

        self.assertFalse(result.has_errors)
        self.assertEqual(result.created_count, 1)
        self.assertEqual(PricingPlan.objects.count(), 1)

        plan = PricingPlan.objects.first()
        self.assertEqual(plan.name, "Standart")
        self.assertEqual(plan.duration_months, 3)
        self.assertEqual(plan.features.count(), 4)

    def test_import_update_mode_updates_existing_row(self):
        plan = PricingPlan.objects.create(
            name="Premium",
            student_range="0-300 ta",
            duration_months=6,
            current_price=500000,
            old_price=600000,
            is_active=True,
            order=1,
        )
        PricingFeature.objects.create(pricing_plan=plan, text="Eski feature", order=1)

        headers = [
            "name",
            "student_range",
            "duration_months",
            "current_price",
            "old_price",
            "is_active",
            "highlight_features",
        ]
        rows = [["Premium", "0-500 ta", 6, "690000", "790000", "true", "Yangi feature"]]
        uploaded_file = self._build_xlsx_upload(headers, rows)

        result = PricingPlanImportService().import_file(
            uploaded_file=uploaded_file,
            mode=IMPORT_MODE_UPDATE_EXISTING,
            file_format="xlsx",
        )

        self.assertFalse(result.has_errors)
        self.assertEqual(result.updated_count, 1)
        plan.refresh_from_db()
        self.assertEqual(plan.student_range, "0-500 ta")
        self.assertEqual(str(plan.current_price), "690000.00")
        self.assertEqual(plan.features.count(), 1)
        self.assertEqual(plan.features.first().text, "Yangi feature")

    def test_import_skip_duplicates_does_not_override_existing(self):
        PricingPlan.objects.create(
            name="Pro",
            student_range="500+",
            duration_months=12,
            current_price=1000000,
            is_active=True,
            order=1,
        )

        headers = ["name", "student_range", "duration_months", "current_price"]
        rows = [["Pro", "500+", 12, "1200000"]]
        uploaded_file = self._build_xlsx_upload(headers, rows)

        result = PricingPlanImportService().import_file(
            uploaded_file=uploaded_file,
            mode=IMPORT_MODE_SKIP_DUPLICATES,
            file_format="xlsx",
        )

        self.assertFalse(result.has_errors)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(PricingPlan.objects.count(), 1)
        self.assertEqual(str(PricingPlan.objects.first().current_price), "1000000.00")

    def test_export_json_returns_nested_features(self):
        plan = PricingPlan.objects.create(
            name="Standart",
            student_range="0-200",
            duration_months=3,
            current_price=390000,
            is_active=True,
            order=1,
        )
        for index in range(1, 8):
            PricingFeature.objects.create(pricing_plan=plan, text=f"Feature {index}", order=index)

        payload = PricingPlanExportService().export_json(PricingPlan.objects.prefetch_related("features"))
        data = json.loads(payload.decode("utf-8"))

        self.assertEqual(data["meta"]["total_plans"], 1)
        plan_payload = data["plans"][0]
        self.assertEqual(len(plan_payload["features"]["highlight"]), 6)
        self.assertEqual(len(plan_payload["features"]["detail"]), 1)
