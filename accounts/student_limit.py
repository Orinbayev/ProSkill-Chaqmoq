# accounts/student_limit.py
"""
Student Limit Enforcement Helper
CRITICAL: Prevents centers from exceeding their subscription plan student limits
"""
from django.core.exceptions import ValidationError
from django.db import transaction


def check_student_limit(center, raise_error=True):
    """
    Check if center has reached student limit.
    
    Args:
        center: Center instance
        raise_error: If True, raises ValidationError when limit exceeded
        
    Returns:
        dict with keys: is_at_limit, current_count, max_students, remaining
        
    Raises:
        ValidationError if limit exceeded and raise_error=True
    """
    from billing.models import CenterSubscription
    from accounts.models import User
    
    # Get max students limit
    max_students = getattr(center, 'capacity_limit', 100)
    
    # Fallback to subscription plan via properties if capacity_limit isn't set or old logic
    if max_students is None or max_students <= 0:
        try:
            subscription = CenterSubscription.objects.get(center=center)
            max_students = subscription.plan.max_students
        except CenterSubscription.DoesNotExist:
            max_students = 100 # Changed default to 100 based on recent updates
    
    # Count active students (exclude archived)
    current_count = User.objects.filter(
        center=center,
        role='student',
        is_archived=False
    ).count()
    
    # Calculate remaining
    remaining = max_students - current_count
    is_at_limit = current_count >= max_students
    
    # Raise error if requested
    if raise_error and is_at_limit:
        raise ValidationError(
            f"❌ Limit tugagan! Ushbu markaz maksimal {max_students} ta o'quvchiga ruxsat beradi. "
            f"Hozir {current_count} ta o'quvchi ro'yxatdan o'tgan. "
            f"Davom etish uchun tarifni yangilang."
        )
    
    return {
        'is_at_limit': is_at_limit,
        'current_count': current_count,
        'max_students': max_students,
        'remaining': remaining
    }


@transaction.atomic
def create_student_safe(user_data, center):
    """
    Safely create student with atomic transaction and limit check.
    Prevents race conditions.
    
    Args:
        user_data: dict with user fields
        center: Center instance
        
    Returns:
        User instance
        
    Raises:
        ValidationError if limit exceeded
    """
    from accounts.models import User, Center
    from billing.models import CenterSubscription
    
    # Lock center row to prevent concurrent student creation
    center_locked = Center.objects.select_for_update().get(id=center.id)
    
    # Check limit with locked data
    # Lock subscription just in case, but rely on capacity_limit first
    try:
        subscription = CenterSubscription.objects.select_for_update().filter(center=center_locked).first()
    except:
        pass

    max_students = getattr(center_locked, 'capacity_limit', 100)
    if max_students is None or max_students <= 0:
         if subscription:
             max_students = subscription.plan.max_students
         else:
             max_students = 100
    
    # Count with lock
    current_count = User.objects.filter(
        center=center_locked,
        role='student',
        is_archived=False
    ).select_for_update().count()
    
    # Check limit
    if current_count >= max_students:
        raise ValidationError(
            f"❌ Limit tugagan! Maksimal {max_students} ta o'quvchi. "
            f"Hozir {current_count} ta. Tarifni yangilang."
        )
    
    # Create student
    user = User.objects.create(**user_data)
    return user
