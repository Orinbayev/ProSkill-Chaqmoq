from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
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
