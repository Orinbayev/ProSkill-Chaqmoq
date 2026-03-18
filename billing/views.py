# billing/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q

from .models import SubscriptionPlan, SubscriptionOrder, SubscriptionRequest
from .services import (
    DURATIONS,
    ensure_center_subscription,
    calculate_price,
    create_order,
    mark_order_paid,
    get_subscription_ui_state,
    get_plan_list_payload,
    get_user_subscription_dashboard_data,
    get_billing_history,
    activate_subscription,
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
    role = getattr(request.user, "role", None)
    if role in ("student", "parent"):
        return redirect("core:home")

    if request.method != "POST":
        return redirect("billing:plans")

    center = getattr(request, "center", None)
    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("core:home")

    plan_code = (request.POST.get("plan") or "").strip().upper()
    try:
        months = int(request.POST.get("months") or 1)
    except (TypeError, ValueError):
        months = 1
    if months not in DURATIONS:
        months = 1
    promo = (request.POST.get("promo") or "").strip().upper()

    plan = get_object_or_404(SubscriptionPlan, code=plan_code, active=True)

    pricing = calculate_price(plan, months, promo, center=center)
    SubscriptionRequest.objects.create(
        user=request.user,
        center=center,
        plan_name=plan.title,
        duration_months=months,
        price=pricing.final_price,
        status=SubscriptionRequest.Status.PENDING,
    )

    messages.success(
        request,
        f"So'rov yuborildi ✅ '{plan.title}' tarifi ({months} oy) uchun so'rovingiz admin tasdiqlagach faollashadi."
    )
    return redirect("billing:plans")


@login_required
def order_confirm_demo(request, pk: int):
    """
    DEMO: superadmin tez test qilish uchun.
    """
    if not request.user.is_superuser:
        return redirect("billing:plans")

    order = get_object_or_404(SubscriptionOrder, pk=pk)
    mark_order_paid(order)
    messages.success(request, "To'lov tasdiqlandi ✅")
    return redirect("platform_global:superadmin_dashboard")


@login_required
def order_reject_demo(request, pk: int):
    """
    DEMO: superadmin to'lov so'rovini rad etishi uchun.
    """
    if not request.user.is_superuser:
        return redirect("billing:plans")

    order = get_object_or_404(SubscriptionOrder, pk=pk)
    order.status = SubscriptionOrder.Status.CANCELED
    order.save()
    messages.warning(request, "To'lov so'rovi rad etildi ❌")
    return redirect("platform_global:superadmin_dashboard")


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


def _resolve_plan_from_name(plan_name: str) -> SubscriptionPlan | None:
    return (
        SubscriptionPlan.objects
        .filter(
            Q(code__iexact=plan_name) |
            Q(name__iexact=plan_name) |
            Q(title__iexact=plan_name),
            active=True,
        )
        .order_by("-id")
        .first()
    )


@login_required
@require_POST
def subscription_request_approve(request, pk: int):
    if not request.user.is_superuser:
        return redirect("billing:plans")

    with transaction.atomic():
        sub_request = (
            SubscriptionRequest.objects
            .select_for_update()
            .select_related("user", "center")
            .filter(pk=pk)
            .first()
        )
        if not sub_request:
            messages.error(request, "So'rov topilmadi.")
            return redirect("platform_global:superadmin_dashboard")

        if sub_request.status != SubscriptionRequest.Status.PENDING:
            messages.warning(request, "Bu so'rov allaqachon ko'rib chiqilgan.")
            return redirect("platform_global:superadmin_dashboard")

        plan = _resolve_plan_from_name(sub_request.plan_name)
        if not plan:
            messages.error(request, f"Tarif topilmadi: {sub_request.plan_name}")
            return redirect("platform_global:superadmin_dashboard")

        # 1) User-level access activation (PRO gating etc.)
        activate_subscription(sub_request.user, plan)

        # 2) Keep center-level subscription flow consistent with existing logic.
        normalized_months = sub_request.duration_months if sub_request.duration_months in DURATIONS else 1
        legacy_order = create_order(
            center=sub_request.center,
            plan=plan,
            months=normalized_months,
            promo_code=None,
        )
        mark_order_paid(legacy_order)

        sub_request.status = SubscriptionRequest.Status.APPROVED
        sub_request.save(update_fields=["status", "updated_at"])

    messages.success(request, "Obuna so'rovi tasdiqlandi ✅")
    return redirect("platform_global:superadmin_dashboard")


@login_required
@require_POST
def subscription_request_reject(request, pk: int):
    if not request.user.is_superuser:
        return redirect("billing:plans")

    with transaction.atomic():
        sub_request = (
            SubscriptionRequest.objects
            .select_for_update()
            .select_related("center")
            .filter(pk=pk)
            .first()
        )
        if not sub_request:
            messages.error(request, "So'rov topilmadi.")
            return redirect("platform_global:superadmin_dashboard")

        if sub_request.status != SubscriptionRequest.Status.PENDING:
            messages.warning(request, "Bu so'rov allaqachon ko'rib chiqilgan.")
            return redirect("platform_global:superadmin_dashboard")

        sub_request.status = SubscriptionRequest.Status.REJECTED
        sub_request.save(update_fields=["status", "updated_at"])

    messages.warning(request, "Obuna so'rovi rad etildi ❌")
    return redirect("platform_global:superadmin_dashboard")
