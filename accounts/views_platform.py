from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

@login_required
@user_passes_test(lambda u: u.is_superuser)
@ensure_csrf_cookie
def plans_list_view(request):
    """Render the Plans Management Page (HTML)"""
    # Fetch initial data if needed, or let JS fetch it.
    # We'll pass csrf_token to template automatically
    from billing.models import SubscriptionPlan
    # Pre-fetch for SSR if desired, but user asked for JS fetch.
    # However, passing initial list is better for UX.
    db_plans = SubscriptionPlan.objects.filter(active=True).order_by("monthly_price")
    return render(request, 'accounts/platform_plans.html', {
        'db_plans': db_plans
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def promos_list_view(request):
    """Render the Promos Management Page (HTML)"""
    return render(request, 'accounts/platform_promos.html')
