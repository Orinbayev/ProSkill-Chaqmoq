# Super Admin Dashboard & Center Creation Views

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from accounts.models import Center
from billing.models import SubscriptionPlan, CenterSubscription
from billing.services import ensure_center_subscription
from .forms import CenterAdminForm, DirectorCreationForm


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_dashboard(request):
    """Super Admin: Barcha markazlar ro'yxati va statistikasi"""
    from django.db.models import Count, Sum, Q
    from education.models import Group, Enrollment
    from billing.models import SubscriptionOrder
    
    centers = Center.objects.filter(is_deleted=False).annotate(
        user_count=Count('user', distinct=True),
        group_count=Count('group', distinct=True),
        # ✅ O'quvchilar sonini User modelidan olamiz (faqat role='student')
        student_count=Count('user', filter=Q(user__role='student', user__is_archived=False), distinct=True),
    ).order_by('-created_at')
    
    # Revenue statistics
    total_revenue = SubscriptionOrder.objects.filter(
        status=SubscriptionOrder.Status.PAID
    ).aggregate(total=Sum('final_price'))['total'] or 0

    # Pending Orders
    pending_orders = SubscriptionOrder.objects.filter(
        status=SubscriptionOrder.Status.PENDING
    ).select_related('center', 'plan').order_by('-created_at')
    
    return render(request, 'accounts/superadmin_dashboard.html', {
        'centers': centers,
        'total_revenue': total_revenue,
        'pending_orders': pending_orders,
    })


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
                    
                    # 3. Subscription yaratish (default plan)
                    plan = SubscriptionPlan.objects.filter(
                        code=center.plan, active=True
                    ).first()
                    if not plan:
                        plan = SubscriptionPlan.objects.filter(active=True).first()
                    
                    if plan:
                        CenterSubscription.objects.create(
                            center=center,
                            plan=plan
                        )
                    
                    messages.success(
                        request, 
                        f"✅ Markaz '{center.name}' va Director '{director.email}' muvaffaqiyatli yaratildi!"
                    )
                    return redirect('accounts:superadmin_dashboard')
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")
        else:
            messages.error(request, "Formada xatolar bor. Iltimos tekshiring.")
    
    return render(request, 'accounts/center_create.html', {
        'center_form': center_form,
        'director_form': director_form,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def center_edit(request, pk):
    """Super Admin: Markazni tahrirlash"""
    center = get_object_or_404(Center, pk=pk)
    form = CenterAdminForm(request.POST or None, instance=center)
    
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"✅ Markaz '{center.name}' yangilandi!")
        return redirect('accounts:superadmin_dashboard')
    
    return render(request, 'accounts/center_edit.html', {
        'form': form,
        'center': center,
    })
