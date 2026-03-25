from django.contrib import admin

from .models import (
    Attendance,
    CertificateRecord,
    CertificateTemplate,
    CertificateVerificationLog,
    Category,
    CenterExamSetting,
    DailyLightningSetting,
    EducationAuditLog,
    Enrollment,
    ExamReminderLog,
    ExamResult,
    ExamResultFile,
    ExamSession,
    GroupClosureWorkflow,
    GroupInternalRankingSnapshot,
    Group,
    Payment,
    StudentAcademicSummary,
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("nom", "center", "oqituvchi", "is_archived", "course_start_date", "estimated_end_date")
    list_filter = ("center", "is_archived")
    search_fields = ("nom", "center__name", "oqituvchi__ism", "oqituvchi__familya")


admin.site.register(Enrollment)
admin.site.register(Payment)
admin.site.register(Attendance)



@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "description")
    search_fields = ("name",)


@admin.register(DailyLightningSetting)
class DailyLightningSettingAdmin(admin.ModelAdmin):
    list_display = ("date", "max_lightning", "active")
    list_filter = ("active",)


@admin.register(CenterExamSetting)
class CenterExamSettingAdmin(admin.ModelAdmin):
    list_display = ("center", "exam_system_enabled", "exam_every_n_lessons", "passing_score_percent", "updated_at")
    search_fields = ("center__name",)


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "center", "lesson_number_reference", "exam_date", "status")
    list_filter = ("center", "status")
    search_fields = ("group__nom", "teacher__ism", "teacher__familya")


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "group", "exam_date", "percent", "passed", "follow_up_status")
    list_filter = ("center", "passed", "follow_up_status")
    search_fields = ("student__ism", "student__familya", "group__nom")


@admin.register(ExamResultFile)
class ExamResultFileAdmin(admin.ModelAdmin):
    list_display = ("id", "result", "file_kind", "uploaded_by", "created_at")
    list_filter = ("file_kind",)


@admin.register(ExamReminderLog)
class ExamReminderLogAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "teacher", "attendance_date", "lesson_number_reference", "action")
    list_filter = ("action", "center")
    search_fields = ("group__nom", "teacher__ism", "teacher__familya")


@admin.register(EducationAuditLog)
class EducationAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "center", "action_type", "entity_type", "entity_id", "actor")
    list_filter = ("center", "action_type")
    search_fields = ("action_type", "entity_type", "entity_id", "message")


@admin.register(GroupInternalRankingSnapshot)
class GroupInternalRankingSnapshotAdmin(admin.ModelAdmin):
    list_display = ("snapshot_date", "group", "student", "rank_position", "total_internal_score")
    list_filter = ("center", "snapshot_date")
    search_fields = ("group__nom", "student__ism", "student__familya")


@admin.register(StudentAcademicSummary)
class StudentAcademicSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "group",
        "student",
        "completion_recommendation",
        "average_percent",
        "attendance_percent",
        "internal_rank_position",
    )
    list_filter = ("center", "completion_recommendation")
    search_fields = ("group__nom", "student__ism", "student__familya")


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("center", "template_type", "name", "is_active", "updated_at")
    list_filter = ("center", "template_type", "is_active")
    search_fields = ("name", "center__name")


@admin.register(CertificateRecord)
class CertificateRecordAdmin(admin.ModelAdmin):
    list_display = ("certificate_number", "student", "group", "certificate_type", "status", "issue_date")
    list_filter = ("center", "certificate_type", "status", "recommendation_status")
    search_fields = ("certificate_number", "student__ism", "student__familya", "group__nom")


@admin.register(CertificateVerificationLog)
class CertificateVerificationLogAdmin(admin.ModelAdmin):
    list_display = ("certificate", "verified_by", "ip_address", "created_at")
    list_filter = ("created_at",)
    search_fields = ("certificate__certificate_number", "ip_address")


@admin.register(GroupClosureWorkflow)
class GroupClosureWorkflowAdmin(admin.ModelAdmin):
    list_display = ("group", "center", "status", "decision_date", "reminder_date", "closed_at")
    list_filter = ("center", "status")
    search_fields = ("group__nom",)
