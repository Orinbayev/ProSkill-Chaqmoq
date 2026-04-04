# accounts/student_limit.py
"""
Student Limit Enforcement Helper
CRITICAL: Prevents centers from exceeding their subscription plan student limits
"""
import logging

from django.core.exceptions import ValidationError
from django.db import transaction

logger = logging.getLogger(__name__)


def check_student_limit(center, raise_error=True, actor=None):
    """
    Check if center has reached student limit.
    Uses the unified center limit resolver so add form, backend validation,
    templates and superadmin all rely on the same number.
    """
    from billing.services import (
        resolve_center_student_limit,
    )

    limit_state = resolve_center_student_limit(
        center=center,
        actor=actor,
        include_usage=True,
    )
    current_count = limit_state["current_count"]
    limit = limit_state["limit"]
    is_at_limit = limit_state["is_at_limit"]
    remaining = limit_state["remaining"]
    plan_name = limit_state.get("plan_name") or "CUSTOM"

    logger.info(
        "Student limit check: center_id=%s center=%s current_students=%s resolved_limit=%s source=%s",
        getattr(center, "id", None),
        getattr(center, "slug", None) or getattr(center, "name", None),
        current_count,
        limit,
        limit_state.get("source"),
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
        'limit_source': limit_state.get("source"),
        'limit_source_label': limit_state.get("source_label"),
        'candidates': limit_state.get("candidates", []),
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
