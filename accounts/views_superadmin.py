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


@login_required

@user_passes_test(lambda u: u.is_superuser)
def superadmin_dashboard(request):
    """Super Admin: Global Dashboard with SaaS KPIs"""
    from django.db.models import Count, Sum, Q, F, ExpressionWrapper, fields, Prefetch
    from django.utils import timezone
    from datetime import timedelta
    from billing.models import SubscriptionOrder, CenterSubscription
    from accounts.models import User
    
    # 1. Base Queryset
    centers = Center.objects.filter(is_deleted=False).select_related('subscription__plan').prefetch_related(
        Prefetch('user_set', queryset=User.objects.filter(role='director'), to_attr='directors')
    ).annotate(
        student_count=Count('user', filter=Q(user__role='student', user__is_archived=False), distinct=True),
    ).order_by('-created_at')

    # 2. Filters from URL
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    plan_filter = request.GET.get('plan', '')
    expiry_filter = request.GET.get('expiry', '')

    if search_q:
        centers = centers.filter(
            Q(name__icontains=search_q) | 
            Q(address__icontains=search_q) |
            Q(user__email__icontains=search_q) |  # Search by user email (director)
            Q(phone__icontains=search_q)
        ).distinct()

    if status_filter:
        centers = centers.filter(status=status_filter)
    
    if plan_filter:
        centers = centers.filter(plan=plan_filter)

    now = timezone.now()
    seven_days_later = now + timedelta(days=7)

    if expiry_filter == 'expired':
        centers = centers.filter(expires_at__lt=now)
    elif expiry_filter == 'expiring_soon':
        centers = centers.filter(expires_at__gte=now, expires_at__lte=seven_days_later)

    # 3. Global KPI Aggregates (using separate fresh queryset for accuracy)
    all_centers = Center.objects.filter(is_deleted=False)
    
    total_centers = all_centers.count()
    active_centers_count = all_centers.filter(status='ACTIVE').count()
    blocked_centers_count = all_centers.filter(status='BLOCKED').count()
    archived_centers_count = all_centers.filter(status='ARCHIVED').count()
    
    # MRR: Sum of monthly_price for ACTIVE centers
    mrr = all_centers.filter(status='ACTIVE').aggregate(s=Sum('monthly_price'))['s'] or 0

    # Subscription Stats
    active_subs_count = all_centers.filter(status='ACTIVE', expires_at__gt=now).count()
    expired_count = all_centers.filter(expires_at__lt=now).count()
    expiring_soon_count = all_centers.filter(expires_at__gte=now, expires_at__lte=seven_days_later).count()

    total_students_global = User.objects.filter(role='student', is_archived=False).count()

    # 4. Pending Orders (For Approval)
    pending_orders = SubscriptionOrder.objects.filter(status='PENDING').select_related('center', 'plan').order_by('-created_at')

    # 4. Context Preparation
    context = {
        'centers': centers,
        'search_q': search_q,
        'status_filter': status_filter,
        'plan_filter': plan_filter,
        'expiry_filter': expiry_filter,
        
        'pending_orders': pending_orders, # <--- Added this

        # KPIs
        'total_centers': total_centers,
        'active_centers_count': active_centers_count,
        'blocked_centers_count': blocked_centers_count,
        'archived_centers_count': archived_centers_count,
        'mrr': mrr,
        'active_subs_count': active_subs_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'total_students_global': total_students_global,
        
        # Dropdown choices (Dynamic Plans)
        'plans': SubscriptionPlan.objects.values_list('code', 'title'),
        'statuses': Center.STATUS_CHOICES,
    }
    
    return render(request, 'accounts/superadmin_dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def center_create(request):
    """Super Admin: Markaz va Director yaratish (transactional)"""
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
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
                        
                        # Set center status to match
                        center.status = 'ACTIVE'
                        center.expires_at = expires_at
                        center.monthly_price = plan.monthly_price  # Store current MRR
                        center.save()
                    
                    messages.success(
                        request, 
                        f"✅ Markaz '{center.name}' va Director '{director.email}' muvaffaqiyatli yaratildi!"
                    )
                    return redirect('accounts:superadmin_dashboard')
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")
        else:
            messages.error(request, "Formada xatolar bor. Iltimos tekshiring.")
    
    # Prepare Plans JSON for frontend calculation
    plans_data = list(SubscriptionPlan.objects.filter(active=True).values(
        'code', 'title', 'monthly_price', 'discount_percent', 'max_students', 'max_users'
    ))
    
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
        return redirect('accounts:superadmin_dashboard')
    
    return render(request, 'accounts/center_edit.html', {
        'form': form,
        'center': center,
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
