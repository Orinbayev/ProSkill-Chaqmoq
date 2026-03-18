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
    get_subscription_ui_state,
    get_plan_list_payload,
    get_user_subscription_dashboard_data,
    get_billing_history,
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
        from .models import CenterSubscription
        from accounts.models import User
        
        try:
            sub = CenterSubscription.objects.get(center=center)
            is_over_limit = sub.is_over_student_limit()
            current_students = User.objects.filter(
                center=center,
                role='student',
                is_archived=False
            ).count()
            max_students = center.effective_student_limit
            exceeded_count = max(0, current_students - max_students)
        except CenterSubscription.DoesNotExist:
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

    plans = list(SubscriptionPlan.objects.filter(active=True).order_by("monthly_price"))

    # pricing table
    pricing_map = {}
    for p in plans:
        pr = calculate_price(p, duration, promo, center=center)
        pricing_map[p.code] = pr

    # Pending orders for this center
    my_pending_orders = SubscriptionRequest.objects.filter(
        status=SubscriptionRequest.Status.PENDING,
    ).order_by("-created_at")
    
    # History for this center
    my_history = SubscriptionRequest.objects.exclude(
        status=SubscriptionRequest.Status.PENDING,
    ).order_by("-created_at")
    
    if center:
        my_pending_orders = my_pending_orders.filter(center=center)
        my_history = my_history.filter(center=center)
    else:
        my_pending_orders = my_pending_orders.filter(user=request.user)
        my_history = my_history.filter(user=request.user)

    from datetime import timedelta
    for order in my_history:
        order.start_date = order.updated_at.date()
        order.end_date = (order.updated_at + timedelta(days=30 * order.duration_months)).date()

    context = {
        "sub": ui,
        "plans": plans,
        "my_pending_orders": my_pending_orders, # <--- Added
        "my_history": my_history, # <--- Added history
        "durations": DURATIONS,
        "duration": duration,
        "promo": promo,
        "pricing": pricing_map,
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
