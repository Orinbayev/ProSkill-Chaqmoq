from django.db import models
from django.conf import settings
from accounts.models import Center

class Notification(models.Model):
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_notifications")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    TYPE_CHOICES = (
        ('coin', 'Chaqmoq o\'zgarishi'),
        ('broadcast', 'Xabar (Broadcast)'),
        ('purchase', 'Xarid holati'),
        ('system', 'Tizim xabari'),
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} -> {self.title}"


class MobileAccessToken(models.Model):
    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name="mobile_access_tokens",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mobile_access_tokens",
    )
    key_prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    device_name = models.CharField(max_length=120, blank=True, default="")
    device_platform = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_revoked", "expires_at"],
                name="core_mobile_user_3d310a_idx",
            ),
            models.Index(
                fields=["center", "is_revoked"],
                name="core_mobile_center_22cc7d_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} / {self.device_name or 'mobil token'}"


class DirectorAIChatSession(models.Model):
    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name="director_ai_chat_sessions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="director_ai_chat_sessions",
    )
    title = models.CharField(max_length=255, blank=True, default="Direktor AI chat")
    launcher_position = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["center", "user"],
                name="core_director_ai_chat_unique_center_user",
            ),
        ]
        indexes = [
            models.Index(fields=["center", "updated_at"]),
            models.Index(fields=["user", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.center} / {self.user} / {self.title or 'AI chat'}"


class DirectorAIChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Foydalanuvchi"
        ASSISTANT = "assistant", "AI"

    session = models.ForeignKey(
        DirectorAIChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    source = models.CharField(max_length=24, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["role", "created_at"]),
        ]

    def __str__(self):
        return f"{self.session_id} / {self.role}"


class CenterDailyMetric(models.Model):
    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name="daily_metrics",
    )
    date = models.DateField(db_index=True)
    students_count = models.PositiveIntegerField(default=0)
    teachers_count = models.PositiveIntegerField(default=0)
    revenue = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["center", "date"],
                name="core_center_daily_metric_unique_center_date",
            ),
        ]
        indexes = [
            models.Index(fields=["center", "date"]),
            models.Index(fields=["date", "center"]),
        ]

    def __str__(self):
        return f"{self.center_id} / {self.date}"


class TeacherDailyMetric(models.Model):
    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name="teacher_daily_metrics",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_teacher_metrics",
        limit_choices_to={"role": "teacher"},
    )
    date = models.DateField(db_index=True)
    students_count = models.PositiveIntegerField(default=0)
    revenue = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["center", "teacher", "date"],
                name="core_teacher_daily_metric_unique_center_teacher_date",
            ),
        ]
        indexes = [
            models.Index(fields=["center", "teacher", "date"]),
            models.Index(fields=["teacher", "date"]),
            models.Index(fields=["date", "center"]),
        ]

    def __str__(self):
        return f"{self.teacher_id} / {self.date}"


class StudentDailyMetric(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ("paid", "To'langan"),
        ("partial", "Qisman"),
        ("debt", "Qarzdor"),
        ("unknown", "Noma'lum"),
    )

    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name="student_daily_metrics",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_student_metrics",
        limit_choices_to={"role": "student"},
    )
    date = models.DateField(db_index=True)
    attendance = models.BooleanField(default=False)
    payment_status = models.CharField(
        max_length=16,
        choices=PAYMENT_STATUS_CHOICES,
        default="unknown",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["center", "student", "date"],
                name="core_student_daily_metric_unique_center_student_date",
            ),
        ]
        indexes = [
            models.Index(fields=["center", "student", "date"]),
            models.Index(fields=["student", "date"]),
            models.Index(fields=["date", "center"]),
        ]

    def __str__(self):
        return f"{self.student_id} / {self.date}"
