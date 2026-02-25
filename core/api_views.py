from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json

@require_POST
@login_required
def notifications_mark_read_api(request):
    try:
        # Assuming we can just mark all unread as read for the user
        from .models import Notification
        updated_count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True, 'count': updated_count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def director_stats_api(request):
    """
    Returns director dashboard analytics as JSON.
    """
    if not (request.user.is_superuser or getattr(request.user, 'role', None) in ('director', 'manager')):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    from .director_stats import _build_director_stats
    center = getattr(request, 'center', None) or request.user.center
    
    if not center:
        return JsonResponse({'error': 'Center not found'}, status=404)
        
    stats = _build_director_stats(center)
    return JsonResponse(stats)
