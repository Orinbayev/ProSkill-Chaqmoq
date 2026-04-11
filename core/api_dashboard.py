"""
Director Dashboard API views — restored from session history.
Provides JSON endpoints consumed by director_panel.html Chart.js charts.
"""
from django.core.cache import cache
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views import View
from datetime import timedelta, date
import logging

from accounts.models import User, Center
from education.models import Group, Enrollment, Payment, Attendance, Category
from store.models import Expense, Lead
try:
    from .services.director_dashboard import build_director_dashboard_payload
except ImportError:
    build_director_dashboard_payload = None

logger = logging.getLogger(__name__)


def _perm(request):
    return request.user.is_superuser or getattr(request.user, "role", None) in ("director", "manager")


def _center(request):
    return getattr(request, "center", None) or getattr(request.user, "center", None)


class DirectorDashboardAPIView(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _perm(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            center = _center(request)
            if not center:
                return JsonResponse({"error": "Center not found"}, status=404)
            if build_director_dashboard_payload is None:
                return JsonResponse({"error": "Dashboard service not available"}, status=503)
            data = build_director_dashboard_payload(center=center, params=request.GET)
            return JsonResponse(data)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)


class DebtorDiagramAPIView(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _perm(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            center = _center(request)
            if not center:
                return JsonResponse({"error": "Center not found"}, status=404)

            ck = f"debtor_diagram:v1:center:{center.id}"
            cached = cache.get(ck)
            if cached:
                return JsonResponse(cached)

            from core.services.center_ai_context import get_debt_aging_context
            aging = get_debt_aging_context(center)
            buckets_list = aging.get("buckets", [])
            buckets_by_label = {b["label"]: b for b in buckets_list}
            all_labels = ["0-30 kun", "31-60 kun", "61-90 kun", "90+ kun"]

            payload = {
                "chart_labels": all_labels,
                "chart_amounts": [buckets_by_label.get(l, {}).get("amount", 0) for l in all_labels],
                "chart_counts": [buckets_by_label.get(l, {}).get("debtor_count", 0) for l in all_labels],
                "buckets": buckets_list,
                "top_debtors": aging.get("top_debtors", [])[:10],
                "total_debt": aging.get("total_debt", 0),
                "total_debtors": aging.get("total_debtors", 0),
                "as_of": aging.get("as_of"),
            }
            cache.set(ck, payload, 300)
            return JsonResponse(payload)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)


class CategoryRevenueAPIView(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _perm(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            center = _center(request)
            if not center:
                return JsonResponse({"error": "Center not found"}, status=404)

            date_from = request.GET.get("date_from")
            date_to = request.GET.get("date_to")
            ck = f"category_revenue:v1:center:{center.id}:{date_from}:{date_to}"
            cached = cache.get(ck)
            if cached:
                return JsonResponse(cached)

            from core.services.center_ai_context import get_category_revenue_context
            cat_data = get_category_revenue_context(center, date_from=date_from, date_to=date_to)
            categories = cat_data.get("by_category", [])

            payload = {
                "labels": [c["category"] for c in categories],
                "amounts": [c["revenue"] for c in categories],
                "payment_counts": [c.get("payments_count", 0) for c in categories],
                "categories": categories,
                "lowest_groups": cat_data.get("lowest_groups", []),
                "highest_groups": cat_data.get("highest_groups", []),
                "total_revenue": cat_data.get("total_revenue", 0),
                "period": cat_data.get("period", {}),
            }
            cache.set(ck, payload, 300)
            return JsonResponse(payload)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)


class StudentChartAPIView(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _perm(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            center = _center(request)
            if not center:
                return JsonResponse({"error": "Center not found"}, status=404)

            year = int(request.GET.get("year", timezone.localtime(timezone.now()).year))
            ck = f"student_chart:v2:center:{center.id}:year:{year}"
            cached = cache.get(ck)
            if cached:
                return JsonResponse(cached)

            uz_months = {1:"Yanvar",2:"Fevral",3:"Mart",4:"Aprel",5:"May",6:"Iyun",
                         7:"Iyul",8:"Avgust",9:"Sentabr",10:"Oktabr",11:"Noyabr",12:"Dekabr"}
            monthly = (
                User.objects.filter(center=center, role="student", is_archived=False, date_joined__year=year)
                .annotate(month=ExtractMonth("date_joined"))
                .values("month").annotate(total=Count("id"))
            )
            month_map = {row["month"]: row["total"] for row in monthly}
            payload = {
                "labels": [uz_months[m] for m in range(1, 13)],
                "new_students": [int(month_map.get(m, 0)) for m in range(1, 13)],
            }
            cache.set(ck, payload, 300)
            return JsonResponse(payload)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)
