import logging

from education.models import EducationAuditLog

logger = logging.getLogger(__name__)


def log_education_event(
    *,
    center,
    actor=None,
    action_type: str,
    entity=None,
    message: str = "",
    payload: dict | None = None,
):
    """
    Best-effort audit logger.
    Asosiy flowni hech qachon to'xtatmaydi.
    """
    if not center or not action_type:
        return None

    entity_type = ""
    entity_id = ""
    if entity is not None:
        entity_type = entity.__class__.__name__
        entity_id = str(getattr(entity, "pk", "") or "")

    try:
        return EducationAuditLog.objects.create(
            center=center,
            actor=actor,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message or "",
            payload=payload or {},
        )
    except Exception:
        logger.exception("Failed to write EducationAuditLog")
        return None
