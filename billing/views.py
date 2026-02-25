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
    my_pending_orders = SubscriptionOrder.objects.filter(center=center, status=SubscriptionOrder.Status.PENDING).order_by('-created_at')

    context = {
        "sub": ui,
        "plans": plans,
        "my_pending_orders": my_pending_orders, # <--- Added
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
