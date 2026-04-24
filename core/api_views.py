from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _director_or_manager(user) -> bool:
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager")


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


@login_required
def dashboard_quick_stats(request):
    """
    Director va Manager dashboard uchun tezkor statistikalar (JSON).

    Eski fieldlar (director boshqaruv): today_income, debtors, active_groups,
      attendance_pct, attendance_label.
    Yangi fieldlar (manager KPI grid uchun, home view deferred bo'lganidan
      keyin AJAX orqali yuklanadi): students, teachers, products,
      pending_requests.
    """
    if not _director_or_manager(request.user):
        return JsonResponse({"detail": "forbidden"}, status=403)

    from django.db.models import Count, Q
    from accounts.models import User
    from core.tenant import get_request_center
    from core.dashboard_metrics import (
        get_center_active_groups_count,
        get_center_attendance_snapshot,
        get_center_debtors_count,
        get_center_today_income,
        month_start,
    )
    from store.models import Product, PurchaseRequest

    center = get_request_center(request)
    if not center:
        return JsonResponse({"detail": "center_not_found"}, status=403)

    today = timezone.localdate()
    current_month = month_start(today)
    attendance = get_center_attendance_snapshot(center, today)

    # ✅ Manager KPI — 3 alohida count() emas, 1 aggregate query.
    user_agg = User.objects.filter(center=center).aggregate(
        teachers=Count("id", filter=Q(role="teacher")),
        students=Count("id", filter=Q(role="student", is_archived=False)),
    )
    pending_status = getattr(PurchaseRequest, "PENDING", "pending")

    return JsonResponse(
        {
            # director
            "today_income": get_center_today_income(center, today),
            "debtors": get_center_debtors_count(center, current_month),
            "active_groups": get_center_active_groups_count(center),
            "attendance_pct": attendance["pct"],
            "attendance_label": attendance["label"],
            # manager KPI grid
            "students": user_agg["students"] or 0,
            "teachers": user_agg["teachers"] or 0,
            "products": Product.objects.filter(center=center).count(),
            "pending_requests": PurchaseRequest.objects.filter(
                center=center, status=pending_status,
            ).count(),
        }
    )


@login_required
def dashboard_low_activity_api(request):
    """Manager dashboard 'Faolligi Past Talabalar' bloki — deferred load."""
    if not _director_or_manager(request.user):
        return JsonResponse({"detail": "forbidden"}, status=403)

    from core.tenant import get_request_center
    from core.views import _get_low_activity_data

    center = get_request_center(request)
    if not center:
        return JsonResponse({"items": []})

    items = _get_low_activity_data(center, limit=5)
    return JsonResponse({"items": items})


@login_required
def dashboard_student_init_api(request):
    """Student dashboard boshlangan'ich ma'lumotlar — balance + last actions."""
    from core.tenant import get_request_center
    from core.views import _student_last_actions
    from chaqmoq.views import _get_balances_with_legacy_fallback

    user = request.user
    if getattr(user, "role", None) != "student" and not user.is_superuser:
        return JsonResponse({"detail": "forbidden"}, status=403)

    center = get_request_center(request) or getattr(user, "center", None)
    balance = _get_balances_with_legacy_fallback([user.id], center=center).get(user.id, 0)
    last_actions = _student_last_actions(user.id, center=center)

    # created_at datetime → ISO string (JSON serialize uchun)
    for a in last_actions:
        ca = a.get("created_at")
        if ca is not None and not isinstance(ca, str):
            try:
                a["created_at"] = ca.isoformat()
            except Exception:
                a["created_at"] = str(ca)

    return JsonResponse({
        "balance": int(balance or 0),
        "last_actions": last_actions,
    })
