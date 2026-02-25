# accounts/student_limit.py
"""
Student Limit Enforcement Helper
CRITICAL: Prevents centers from exceeding their subscription plan student limits
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

def check_student_limit(center, raise_error=True):
    """
    Check if center has reached student limit.
    Uses proper Subscription Service logic.
    """
    from accounts.models import User
    
    # 1. Get Limit Source (Using the new Center.effective_student_limit)
    limit = center.effective_student_limit
    
    # 2. Count active students
    current_count = User.objects.filter(
        center=center, 
        role='student', 
        is_archived=False
    ).count()
    
    is_at_limit = current_count >= limit
    remaining = max(0, limit - current_count)

    if raise_error and is_at_limit:
        plan_info = f" ({center.active_subscription.plan.title} tarifi)" if center.active_subscription else ""
        raise ValidationError(
            f"❌ '{center.name}' markazida o‘quvchi limiti to‘lgan! "
            f"Amaldagi holat: {current_count}/{limit}{plan_info}. "
            "Yangi o‘quvchi qo‘shish uchun tarifni yangilang yoki 'capacity_limit'ni oshiring (Super Admin orqali)."
        )

    active_sub = center.active_subscription
    return {
        'is_at_limit': is_at_limit,
        'current_count': current_count,
        'limit': limit,
        'remaining': remaining,
        'plan_name': active_sub.plan.title if active_sub and hasattr(active_sub, 'plan') else "Noma'lum"
    }


@transaction.atomic
def create_student_safe(user_data, center):
    """
    Safely create student with atomic transaction and limit check.
    Prevents race conditions using select_for_update.
    """
    from accounts.models import User, Center
    
    # Lock Center to prevent concurrent additions bypassing limit
    center_locked = Center.objects.select_for_update().get(id=center.id)
    
    # Re-check limit inside lock
    check_student_limit(center_locked, raise_error=True)
    
    # Create
    user = User.objects.create(**user_data)
    return user
