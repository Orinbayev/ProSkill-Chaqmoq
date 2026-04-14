from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@login_required
def churn_api_summary(request):
    """Boshqaruv sahifasi uchun churn statistikasi (JSON)."""
    center = getattr(request, 'center', None) or getattr(request.user, 'center', None)
    if not center:
        return JsonResponse({'total': 0, 'high': 0, 'medium': 0, 'low': 0})
    from .models import ChurnRisk
    qs = ChurnRisk.objects.filter(center=center)
    return JsonResponse({
        'total':  qs.count(),
        'high':   qs.filter(risk_level='high').count(),
        'medium': qs.filter(risk_level='medium').count(),
        'low':    qs.filter(risk_level='low').count(),
    })

@require_POST
@login_required
def notifications_mark_read_api(request):
    try:
        # Assuming we can just mark all unread as read for the user
        from .models import Notification
        updated_count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True, 'count': updated_count})
    except Exception:
        logger.exception("notifications_mark_read_api failed")
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


@login_required
def exam_api_summary(request):
    try:
        from core.tenant import get_request_center
        from education.models import CertificateRecord, ExamResult, ExamSession

        center = get_request_center(request)
        if not center:
            return JsonResponse({
                "total_sessions": 0,
                "this_month_completed": 0,
                "avg_percent": 0,
                "pending_certificates": 0,
            })

        if not request.user.is_superuser and getattr(request.user, "role", None) not in ("manager", "director"):
            return JsonResponse({"detail": "forbidden"}, status=403)

        today = timezone.localdate()
        month_start = today.replace(day=1)

        total = ExamSession.objects.filter(center=center).count()
        this_month = ExamSession.objects.filter(
            center=center,
            exam_date__gte=month_start,
            status="completed",
        ).count()
        avg_pct = (
            ExamResult.objects.filter(
                center=center,
                exam_date__gte=month_start,
            )
            .exclude(percent__isnull=True)
            .aggregate(a=Avg("percent"))["a"] or 0
        )
        pending_certs = CertificateRecord.objects.filter(
            center=center,
            status="draft",
        ).count()

        return JsonResponse({
            "total_sessions": total,
            "this_month_completed": this_month,
            "avg_percent": round(float(avg_pct), 1),
            "pending_certificates": pending_certs,
        })
    except Exception:
        logger.exception("exam_api_summary failed")
        return JsonResponse({"detail": "error"}, status=500)
