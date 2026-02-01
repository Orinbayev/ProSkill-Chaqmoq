# billing/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse

from .models import SubscriptionPlan, SubscriptionOrder
from .services import (
    DURATIONS, ensure_center_subscription, calculate_price, create_order, mark_order_paid, get_subscription_ui_state
)


@login_required
def blocked(request):
    center = getattr(request, "center", None)
    ui = {}
    if center:
        ui = get_subscription_ui_state(center)
    return render(request, "billing/blocked.html", {"sub": ui})


@login_required
def plans(request):
    # Only staff/admins should see billing
    role = getattr(request.user, "role", None)
    if role in ("student", "parent"):
        return redirect("core:home")

    center = getattr(request, "center", None)
    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("core:home")

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
        pr = calculate_price(p, duration, promo)
        pricing_map[p.code] = {
            "base": pr.base_price,
            "discount_percent": pr.discount_percent,
            "final": pr.final_price,
            "has_promo": bool(pr.promo),
        }

    context = {
        "sub": ui,
        "plans": plans,
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
    months = int(request.POST.get("months") or 1)
    promo = (request.POST.get("promo") or "").strip().upper()

    plan = get_object_or_404(SubscriptionPlan, code=plan_code, active=True)

    order = create_order(center, plan, months, promo)

    messages.success(
        request,
        f"So‘rov yuborildi ✅ (Order #{order.id}). Admin tasdiqlagach obunangiz yangilanadi."
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
    messages.success(request, f"Order #{order.id} PAID qilindi ✅")
    return redirect("billing:plans")
