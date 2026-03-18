# accounts/student_limit.py
"""
Student Limit Enforcement Helper
CRITICAL: Prevents centers from exceeding their subscription plan student limits
"""
from django.core.exceptions import ValidationError
from django.db import transaction

def check_student_limit(center, raise_error=True, actor=None):
    """
    Check if center has reached student limit.
    Free -> 50
    PRO/paid -> active plan max_students
    """
    from accounts.models import User
    from billing.services import (
        check_subscription,
        get_center_student_limit,
        get_subscription_owner_for_center,
    )
    
    limit = get_center_student_limit(center=center, actor=actor, free_limit=50)
    
    # 2. Count active students
    current_count = User.objects.filter(
        center=center, 
        role='student', 
        is_archived=False
    ).count()
    
    is_at_limit = current_count >= limit
    remaining = max(0, limit - current_count)

    owner = get_subscription_owner_for_center(center=center, actor=actor)
    owner_sub = check_subscription(owner) if owner else None
    plan_name = (
        owner_sub.plan.name or owner_sub.plan.title or owner_sub.plan.code
        if owner_sub and owner_sub.plan
        else "FREE"
    )

    if raise_error and is_at_limit:
        plan_info = f" ({plan_name} tarifi)"
        raise ValidationError(
            f"❌ '{center.name}' markazida o‘quvchi limiti to‘lgan! "
            f"Amaldagi holat: {current_count}/{limit}{plan_info}. "
            "Yangi o‘quvchi qo‘shish uchun obunani yangilang."
        )

    return {
        'is_at_limit': is_at_limit,
        'current_count': current_count,
        'limit': limit,
        'remaining': remaining,
        'plan_name': plan_name,
    }


@transaction.atomic
def create_student_safe(user_data, center, actor=None):
    """
    Safely create student with atomic transaction and limit check.
    Prevents race conditions using select_for_update.
    """
    from accounts.models import User, Center
    
    # Lock Center to prevent concurrent additions bypassing limit
    center_locked = Center.objects.select_for_update().get(id=center.id)
    
    # Re-check limit inside lock
    check_student_limit(center_locked, raise_error=True, actor=actor)
    
    # Create
    user = User.objects.create(**user_data)
    return user
