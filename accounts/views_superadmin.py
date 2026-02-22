# Super Admin Dashboard & Center Creation Views

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from accounts.models import Center
from billing.models import SubscriptionPlan, CenterSubscription
from billing.services import ensure_center_subscription
from .forms import CenterAdminForm, DirectorCreationForm
from django.http import JsonResponse
import json
from django.core.serializers.json import DjangoJSONEncoder


@login_required

@user_passes_test(lambda u: u.is_superuser)
def superadmin_dashboard(request):
    """Super Admin: Global Dashboard with SaaS KPIs — optimized"""
    from django.db.models import Count, Sum, Q, Prefetch, Case, When, IntegerField
    from django.utils import timezone
    from datetime import timedelta
    from billing.models import SubscriptionOrder, CenterSubscription
    from accounts.models import User

    now = timezone.now()
    seven_days_later = now + timedelta(days=7)

    # ── 1. Filters from URL ─────────────────────────────────────
    search_q     = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    plan_filter   = request.GET.get('plan', '')
    expiry_filter = request.GET.get('expiry', '')

    # ── 2. Centers queryset (only needed fields) ────────────────
    centers = (
        Center.objects
        .filter(is_deleted=False)
        .only(
            'id', 'name', 'address', 'phone', 'plan', 'status',
            'monthly_price', 'expires_at', 'capacity_limit', 'created_at',
            'slug',
        )
        .prefetch_related(
            Prefetch(
                'user_set',
                queryset=User.objects.filter(role='director').only('id', 'ism', 'familya', 'email', 'telefon1'),
                to_attr='directors',
            ),
            'subscriptions__plan',
        )
        .annotate(
            student_count=Count(
                'user',
                filter=Q(user__role='student', user__is_archived=False),
                distinct=True,
            ),
        )
        .order_by('-created_at')
    )

    # ── 3. Apply filters ────────────────────────────────────────
    if search_q:
        centers = centers.filter(
            Q(name__icontains=search_q)    |
            Q(address__icontains=search_q) |
            Q(phone__icontains=search_q)   |
            # Better search: Director name/email
            Q(user__ism__icontains=search_q) |
            Q(user__familya__icontains=search_q) |
            Q(user__email__icontains=search_q)
        ).distinct()

    if status_filter:
        centers = centers.filter(status=status_filter)

    if plan_filter:
        centers = centers.filter(plan=plan_filter)

    if expiry_filter:
        if expiry_filter == 'expired':
            centers = centers.filter(expires_at__lt=now)
        elif expiry_filter == 'expiring_soon':
            # 7 days
            centers = centers.filter(expires_at__gte=now, expires_at__lte=seven_days_later)
        elif expiry_filter == 'expiring_3':
            # 3 days
            centers = centers.filter(expires_at__gte=now, expires_at__lte=now + timedelta(days=3))
        elif expiry_filter == 'today':
            # Today
            centers = centers.filter(expires_at__date=now.date())
        elif expiry_filter == 'grace':
            # Expired but within 3 days grace
            centers = centers.filter(expires_at__lt=now, expires_at__gte=now - timedelta(days=3))
        elif expiry_filter == 'active':
            centers = centers.filter(expires_at__gt=now)

    # ── 4. KPI aggregates — ONE query instead of 6 ─────────────
    kpis = Center.objects.filter(is_deleted=False).aggregate(
        total_centers=Count('id'),
        active_centers_count=Count('id', filter=Q(status='ACTIVE')),
        blocked_centers_count=Count('id', filter=Q(status='BLOCKED')),
        archived_centers_count=Count('id', filter=Q(status='ARCHIVED')),
        mrr=Sum('monthly_price', filter=Q(status='ACTIVE')),
        active_subs_count=Count('id', filter=Q(status='ACTIVE', expires_at__gt=now)),
        expired_count=Count('id', filter=Q(expires_at__lt=now)),
        expiring_soon_count=Count('id', filter=Q(
            expires_at__gte=now, expires_at__lte=seven_days_later
        )),
    )

    # ── 5. Global student count ─────────────────────────────────
    # Filter over-capacity centers if requested
    limit_filter = request.GET.get('limit', '')
    if limit_filter == 'over':
        from django.db.models import F
        centers = centers.filter(student_count__gt=F('capacity_limit'))

    total_students_global = User.objects.filter(
        role='student', is_archived=False
    ).count()

    # ── 6. Pending orders ───────────────────────────────────────
    pending_orders = (
        SubscriptionOrder.objects
        .filter(status='PENDING')
        .select_related('center', 'plan')
        .only(
            'id', 'center__name', 'plan__code', 'plan__title',
            'duration_months', 'final_price', 'created_at',
        )
        .order_by('-created_at')
    )

    # ── 7. Context ──────────────────────────────────────────────
    context = {
        'centers': centers,
        'search_q': search_q,
        'status_filter': status_filter,
        'plan_filter': plan_filter,
        'expiry_filter': expiry_filter,
        'limit_filter': limit_filter,
        'pending_orders': pending_orders,

        # KPIs (from single aggregate)
        'total_centers':       kpis['total_centers']       or 0,
        'active_centers_count': kpis['active_centers_count'] or 0,
        'blocked_centers_count': kpis['blocked_centers_count'] or 0,
        'archived_centers_count': kpis['archived_centers_count'] or 0,
        'mrr':                 kpis['mrr']                 or 0,
        'active_subs_count':   kpis['active_subs_count']   or 0,
        'expired_count':       kpis['expired_count']       or 0,
        'expiring_soon_count': kpis['expiring_soon_count'] or 0,
        'total_students_global': total_students_global,

        # Dropdown choices
        'plans':    SubscriptionPlan.objects.filter(active=True).values_list('code', 'title'),
        'statuses': Center.STATUS_CHOICES,
    }

    return render(request, 'accounts/superadmin_dashboard.html', context)



@login_required
@user_passes_test(lambda u: u.is_superuser)
def center_create(request):
    """Super Admin: Markaz va Director yaratish (transactional)"""
    
    center_form = CenterAdminForm(request.POST or None)
    director_form = DirectorCreationForm(request.POST or None)
    
    if request.method == 'POST':
        if center_form.is_valid() and director_form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Markaz yaratish
                    center = center_form.save()
                    
                    # 2. Director yaratish
                    director = director_form.save(center=center)
                    
                    # 3. Subscription yaratish
                    from django.utils import timezone
                    from datetime import timedelta
                    
                    plan_code = center.plan
                    plan = SubscriptionPlan.objects.filter(code=plan_code, active=True).first()
                    if not plan:
                        plan = SubscriptionPlan.objects.filter(active=True).first()
                    
                    # Get duration/months from POST (default 1)
                    try:
                        duration = int(request.POST.get('duration', 1))
                    except (ValueError, TypeError):
                        duration = 1
                    
                    if plan:
                        # Auto-calculate expiry
                        now = timezone.now()
                        expires_at = now + timedelta(days=30 * duration)
                        
                        CenterSubscription.objects.create(
                            center=center,
                            plan=plan,
                            expires_at=expires_at,
                            status='ACTIVE'
                        )
                        
                        # Set center status and limits to match the plan
                        center.status = 'ACTIVE'
                        center.expires_at = expires_at
                        center.monthly_price = plan.monthly_price  # Store current MRR
                        
                        # SaaS Sync: Core Limits & Features
                        center.capacity_limit = plan.max_students
                        center.max_students = plan.max_students
                        center.max_groups = 9999
                        center.max_users = 9999
                        
                        # Sync features from plan
                        feature_codes = list(plan.plan_features.values_list('code', flat=True))
                        center.features = {code: True for code in feature_codes}
                        
                        center.save()
                    
                    messages.success(
                        request, 
                        f"✅ Markaz '{center.name}' va Director '{director.email}' muvaffaqiyatli yaratildi!"
                    )
                    return redirect('platform_global:superadmin_dashboard')
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")
        else:
            messages.error(request, "Formada xatolar bor. Iltimos tekshiring.")
    
    # Prepare Plans JSON for frontend calculation
    plans_qs = SubscriptionPlan.objects.filter(active=True)
    plans_data = []
    for p in plans_qs:
        plans_data.append({
            'code': p.code,
            'title': p.title,
            'monthly_price': p.monthly_price,
            'discount_percent': p.discount_percent,
            'max_students': p.max_students,
            'max_users': p.max_users,
            'price_3m': p.price_3m,
            'price_6m': p.price_6m,
            'price_9m': p.price_9m,
            'price_12m': p.price_12m,
            'feature_codes': list(p.plan_features.values_list('code', flat=True))
        })
    
    return render(request, 'accounts/center_create.html', {
        'center_form': center_form,
        'director_form': director_form,
        'plans_json': json.dumps(plans_data, cls=DjangoJSONEncoder)
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def center_edit(request, pk):
    """Super Admin: Markazni tahrirlash"""
    center = get_object_or_404(Center, pk=pk)
    form = CenterAdminForm(request.POST or None, instance=center)
    
    if request.method == 'POST' and form.is_valid():
        center = form.save()
        
        try:
            # Sync subscription expiry if exists
            if hasattr(center, 'subscription') and center.subscription:
                sub = center.subscription
                sub.expires_at = center.expires_at
                sub.save()
        except Exception:
            pass
            
        messages.success(request, f"✅ Markaz '{center.name}' yangilandi!")
        return redirect('platform_global:superadmin_dashboard')
    
    # Prepare Plans JSON for frontend calculation
    plans_qs = SubscriptionPlan.objects.filter(active=True)
    plans_data = []
    for p in plans_qs:
        plans_data.append({
            'code': p.code,
            'title': p.title,
            'monthly_price': p.monthly_price,
            'discount_percent': p.discount_percent,
            'max_students': p.max_students,
            'max_users': p.max_users,
            'price_3m': p.price_3m,
            'price_6m': p.price_6m,
            'price_9m': p.price_9m,
            'price_12m': p.price_12m,
            'feature_codes': list(p.plan_features.values_list('code', flat=True))
        })
    
    return render(request, 'accounts/center_edit.html', {
        'form': form,
        'center': center,
        'plans_json': json.dumps(plans_data, cls=DjangoJSONEncoder)
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def update_center_capacity(request, pk):
    """
    Update Center Capacity Limit via AJAX.
    """
    if request.method != 'POST':
         return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        new_limit = data.get('capacity_limit')
        
        # Validation
        try:
            new_limit = int(new_limit)
        except (ValueError, TypeError):
             return JsonResponse({'error': 'Limit butun son bo‘lishi shart'}, status=400)
             
        if new_limit < 1:
             return JsonResponse({'error': 'Limit kamida 1 bo‘lishi kerak'}, status=400)
             
        center = get_object_or_404(Center, pk=pk)
        
        # Update
        center.capacity_limit = new_limit
        center.save()
        
        # Recalculate Logic
        counts = center.get_counts
        current_students = counts['students']
        over_limit = current_students > new_limit
        
        return JsonResponse({
            'success': True,
            'message': 'Limit muvaffaqiyatli yangilandi',
            'capacity_limit': new_limit,
            'current_students': current_students,
            'over_limit': over_limit
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
