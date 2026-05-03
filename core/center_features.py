from __future__ import annotations


FEATURE_UI_EXAM_SESSIONS = "ui_exam_sessions"
FEATURE_UI_FAILED_STUDENTS = "ui_failed_students"
FEATURE_UI_CERTIFICATES = "ui_certificates"
FEATURE_UI_WEEKLY_SCHEDULE = "ui_weekly_schedule"
FEATURE_SUPPORT_TEACHER = "support_teacher_enabled"


CENTER_UI_FEATURE_DEFAULTS = {
    FEATURE_UI_EXAM_SESSIONS: True,
    FEATURE_UI_FAILED_STUDENTS: True,
    FEATURE_UI_CERTIFICATES: True,
    FEATURE_UI_WEEKLY_SCHEDULE: True,
    # Support teacher — default OFF (faqat shartnoma qilingan markazlarda yoqiladi)
    FEATURE_SUPPORT_TEACHER: False,
}


def center_ui_feature_enabled(center, feature_code: str, *, default: bool | None = None) -> bool:
    """
    Center-level UI modul flaglari.
    Default: eski markazlar buzilmasligi uchun yoqilgan.
    """
    if default is None:
        default = CENTER_UI_FEATURE_DEFAULTS.get(feature_code, True)

    if not center:
        return bool(default)

    features = getattr(center, "features", None) or {}
    if feature_code not in features:
        return bool(default)

    return bool(features.get(feature_code))


def get_center_ui_feature_map(center) -> dict[str, bool]:
    return {
        "feature_exam_sessions_ui": center_ui_feature_enabled(center, FEATURE_UI_EXAM_SESSIONS),
        "feature_failed_students_ui": center_ui_feature_enabled(center, FEATURE_UI_FAILED_STUDENTS),
        "feature_certificates_ui": center_ui_feature_enabled(center, FEATURE_UI_CERTIFICATES),
        "feature_weekly_schedule_ui": center_ui_feature_enabled(center, FEATURE_UI_WEEKLY_SCHEDULE),
        "feature_support_teacher": center_ui_feature_enabled(center, FEATURE_SUPPORT_TEACHER),
    }
