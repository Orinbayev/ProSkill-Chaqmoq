# billing/views.py
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from . import click_views
from .models import SubscriptionPlan, SubscriptionRequest
from .services import (
    DURATIONS,
    ensure_center_subscription,
    calculate_price,
    calculate_upgrade_preview,
    get_active_subscription,
    get_subscription_ui_state,
    get_plan_list_payload,
    get_user_subscription_dashboard_data,
    get_billing_history,
    resolve_center_student_limit,
)


@login_required
def blocked(request):
    center = getattr(request, "center", None)
    ui = {}
    is_over_limit = False
    current_students = 0
    max_students = 0
    exceeded_count = 0
    
    if center:
        ui = get_subscription_ui_state(center)
        # Check student limit
        try:
            sub = get_active_subscription(center)
            is_over_limit = sub.is_over_student_limit()
            limit_state = resolve_center_student_limit(center, actor=request.user, include_usage=True)
            current_students = limit_state["current_count"]
            max_students = limit_state["limit"]
            exceeded_count = max(0, current_students - max_students)
        except Exception:
            pass
    
    return render(request, "billing/blocked.html", {
        "sub": ui,
        "is_over_limit": is_over_limit,
        "current_students": current_students,
        "max_students": max_students,
        "exceeded_count": exceeded_count,
    })



@login_required
def plans(request):
    center = getattr(request, "center", None)
    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("core:home")

    # Agar bloklangan bo'lsa, to'lov qilishga ruxsat beramiz (barchaga)
    role = getattr(request.user, "role", None)
    if not request.user.is_superuser and center.status != 'BLOCKED' and role in ("student", "parent", "teacher"):
        # Redirect qilmasdan, to'g'ridan-to'g'ri error ko'rsatamiz (loop oldini olish)
        return render(request, "billing/permission_denied.html", {
            "message": "Sizda bu sahifaga kirish huquqi yo'q. Bu sahifa faqat administrator va menejerlar uchun."
        })

    # ✅ Agar teacher/student/parent bo'lsa va center BLOCKED bo'lsa -> ularga plan tanlash chiqmasligi kerak
    if role in ("student", "parent", "teacher"):
         return render(request, "billing/blocked.html", {
             "sub": get_subscription_ui_state(center),
             "readonly": True
         })

    ensure_center_subscription(center)
    ui = get_subscription_ui_state(center)

    duration = int(request.GET.get("m") or 1)
    if duration not in DURATIONS:
        duration = 1

    promo = (request.GET.get("promo") or "").strip().upper()

    # Faqat ochiq (public) tariflar — test/ortiqcha tariflar landing_visible=False
    plans = list(
        SubscriptionPlan.objects.filter(active=True, landing_visible=True).order_by("monthly_price")
    )
    if not plans:  # xavfsizlik fallback — hech bo'lmasa hammasi
        plans = list(SubscriptionPlan.objects.filter(active=True).order_by("monthly_price"))

    # pricing table
    pricing_map = {}
    for p in plans:
        pr = calculate_price(p, duration, promo, center=center)
        pricing_map[p.code] = pr

    from datetime import timedelta
    from django.utils import timezone as tz_now

    # Auto-expire truly stale pending orders (older than 30 min with no webhook received)
    stale_cutoff = tz_now.now() - timedelta(minutes=30)
    if center:
        SubscriptionRequest.objects.filter(
            center=center,
            status=SubscriptionRequest.Status.PENDING,
            created_at__lt=stale_cutoff,
        ).update(status=SubscriptionRequest.Status.CANCELLED, updated_at=tz_now.now())

    # Pending orders for this center (only truly recent/active ones)
    recent_cutoff = tz_now.now() - timedelta(minutes=30)
    my_pending_orders = SubscriptionRequest.objects.filter(
        status=SubscriptionRequest.Status.PENDING,
        created_at__gte=recent_cutoff,
    ).order_by("-created_at")

    # Payment history: use actual paid SubscriptionOrders with exact date info
    from billing.models import SubscriptionOrder as SO
    my_history_qs = SO.objects.filter(
        status=SO.Status.PAID,
    ).select_related("plan").order_by("-paid_at")

    if center:
        my_pending_orders = my_pending_orders.filter(center=center)
        my_history_qs = my_history_qs.filter(center=center)
    else:
        my_pending_orders = my_pending_orders.filter(user=request.user)

    # Build history list with real start/end dates from the payment timestamp
    my_history = []
    for o in my_history_qs[:20]:
        paid_on = o.paid_at or o.created_at
        my_history.append({
            "plan_name": o.plan.title if o.plan else "—",
            "duration_months": o.duration_months,
            "amount": o.final_price,
            "updated_at": paid_on,
            "start_date": paid_on.date(),
            "end_date": (paid_on + timedelta(days=30 * o.duration_months)).date(),
            "status": "paid",
            "status_display": "Muvaffaqiyatli",
        })

    # ── Data-driven feature taqqoslash (PlanFeature'dan, qattiq kod emas) ──
    from billing.models import PlanFeature as _PF
    _m2m = {p.id: set(p.plan_features.values_list("code", flat=True)) for p in plans}
    _cat_labels = dict(_PF.Category.choices)
    _groups = {}
    for f in _PF.objects.filter(is_active=True).order_by("category", "order", "name"):
        per_plan = [bool(f.is_core or f.code in _m2m.get(p.id, set())) for p in plans]
        if not any(per_plan):
            continue  # hech qaysi ochiq tarifda yo'q — ko'rsatmaymiz
        _groups.setdefault(f.category, []).append({
            "name": f.name_uz or f.name, "is_core": f.is_core, "per_plan": per_plan,
        })
    feature_comparison = [
        {"label": _cat_labels.get(c, c), "features": rows} for c, rows in _groups.items()
    ]

    context = {
        "sub": ui,
        "plans": plans,
        "my_pending_orders": my_pending_orders,
        "my_history": my_history,
        "durations": DURATIONS,
        "duration": duration,
        "promo": promo,
        "pricing": pricing_map,
        "feature_comparison": feature_comparison,
    }
    return render(request, "billing/plans.html", context)



@login_required
def order_create(request):
    """
    Backward-compatible endpoint.
    Old flow used manual admin approval; now it is fully automatic via Click webhook.
    """
    role = getattr(request.user, "role", None)
    if role in ("student", "parent"):
        return redirect("core:home")

    if request.method != "POST":
        return redirect("billing:plans")

    center = getattr(request, "center", None)
    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("core:home")

    click_response = click_views.create_order_and_redirect(request)
    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )
    if wants_json:
        return click_response

    if click_response.status_code != 200:
        try:
            payload = json.loads(click_response.content.decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            payload = {}
        messages.error(request, payload.get("error_note") or "Click order yaratishda xatolik.")
        return redirect("billing:plans")

    try:
        payload = json.loads(click_response.content.decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        messages.error(request, "To'lov URL ni olishda xatolik.")
        return redirect("billing:plans")

    payment_url = (payload.get("payment_url") or "").strip()
    if not payment_url:
        messages.error(request, "To'lov URL bo'sh qaytdi.")
        return redirect("billing:plans")

    return redirect(payment_url)


@login_required
def order_confirm_demo(request, pk: int):
    if request.user.is_superuser:
        return redirect("platform_global:superadmin_dashboard")
    return redirect("billing:plans")


@login_required
def order_reject_demo(request, pk: int):
    if request.user.is_superuser:
        return redirect("platform_global:superadmin_dashboard")
    return redirect("billing:plans")


@login_required
def plans_api(request):
    """
    Frontend support endpoint:
    - returns available plans
    """
    return JsonResponse({"plans": get_plan_list_payload()})


@login_required
def upgrade_preview_api(request):
    """
    GET /billing/api/upgrade-preview/?plan_id=<id>&months=<n>
    Upgrade qilganda qolgan kreditni ko'rsatadi.
    """
    center = getattr(request, "center", None)
    if not center:
        return JsonResponse({"ok": False, "error": "Center topilmadi."}, status=400)

    plan_id = request.GET.get("plan_id")
    months = int(request.GET.get("months") or 1)
    if months not in DURATIONS:
        months = 1

    try:
        new_plan = SubscriptionPlan.objects.get(pk=plan_id, active=True)
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Tarif topilmadi."}, status=404)

    active_sub = get_active_subscription(center)
    duration_days = int(getattr(new_plan, "duration_days", 0) or 30) * months

    preview = calculate_upgrade_preview(
        active_sub=active_sub,
        new_plan=new_plan,
        paid_days=duration_days,
    )

    # Serialize Decimal / datetime for JSON
    result = {
        "ok": True,
        "is_upgrade": preview["is_upgrade"],
        "remaining_days": preview.get("remaining_days", 0),
        "remaining_credit": str(preview.get("remaining_credit", 0)),
        "credit_days": preview.get("credit_days", 0),
        "paid_days": preview.get("paid_days", duration_days),
        "total_new_days": preview.get("total_new_days", duration_days),
        "old_plan_title": preview.get("old_plan_title", ""),
        "old_monthly_price": preview.get("old_monthly_price", 0),
        "new_plan_title": preview.get("new_plan_title", new_plan.title),
        "new_monthly_price": preview.get("new_monthly_price", new_plan.monthly_price),
        "new_expires_at": preview["new_expires_at"].strftime("%d.%m.%Y") if preview.get("new_expires_at") else "",
    }
    return JsonResponse(result)


@login_required
def current_subscription_api(request):
    """
    Frontend support endpoint:
    - current subscription data
    - recent billing transactions
    """
    user_data = get_user_subscription_dashboard_data(request.user)
    history_qs = get_billing_history(request.user)[:20]
    history = [
        {
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "status": tx.status,
            "created_at": tx.created_at,
        }
        for tx in history_qs
    ]
    return JsonResponse({
        "current_subscription": user_data,
        "billing_history": history,
    })


@login_required
@require_POST
def subscription_request_approve(request, pk: int):
    if request.user.is_superuser:
        return redirect("platform_global:superadmin_dashboard")
    return redirect("billing:plans")


@login_required
@require_POST
def subscription_request_reject(request, pk: int):
    if request.user.is_superuser:
        return redirect("platform_global:superadmin_dashboard")
    return redirect("billing:plans")
