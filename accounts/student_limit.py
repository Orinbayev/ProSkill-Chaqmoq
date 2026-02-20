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
    
    # 1. Get Limit Source (Priority: Active Sub Plan > Center.capacity_limit > Default)
    limit = 50 # Absolute fallback
    
    active_sub = center.active_subscription
    if active_sub:
        limit = active_sub.plan.max_students
    elif center.capacity_limit and center.capacity_limit > 0:
        limit = center.capacity_limit
    
    # 2. Count active students
    current_count = User.objects.filter(
        center=center, 
        role='student', 
        is_archived=False
    ).count()
    
    is_at_limit = current_count >= limit
    remaining = max(0, limit - current_count)

    if raise_error and is_at_limit:
        raise ValidationError(
            f"❌ O‘quvchi limiti to‘lgan ({current_count}/{limit}). "
            "Yangi o‘quvchi qo‘shish uchun tarifni yangilang (Upgrade)."
        )

    return {
        'is_at_limit': is_at_limit,
        'current_count': current_count,
        'limit': limit,
        'remaining': remaining,
        'plan_name': active_sub.plan.title if active_sub else "Noma'lum"
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
