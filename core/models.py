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


class NotificationPreference(models.Model):
    """
    Foydalanuvchining bildirishnoma afzalliklari.
    Har bir tur uchun alohida opt-out imkoniyati.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    # Har bir tur uchun: True = qabul qilish, False = rad etish
    receive_coin = models.BooleanField(default=True, verbose_name="Chaqmoq o'zgarishi")
    receive_broadcast = models.BooleanField(default=True, verbose_name="Umumiy xabarlar")
    receive_purchase = models.BooleanField(default=True, verbose_name="Xarid holati")
    receive_system = models.BooleanField(default=True, verbose_name="Tizim xabarlari")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bildirishnoma sozlamasi"
        verbose_name_plural = "Bildirishnoma sozlamalari"

    def __str__(self):
        return f"{self.user} bildirishnoma sozlamalari"

    @classmethod
    def wants_notification(cls, user, notification_type: str) -> bool:
        """
        Foydalanuvchi ushbu turdagi bildirishnomani olishni xohlaydi?
        Sozlama yo'q bo'lsa — standart True qaytaradi.
        """
        field_map = {
            "coin": "receive_coin",
            "broadcast": "receive_broadcast",
            "purchase": "receive_purchase",
            "system": "receive_system",
        }
        field = field_map.get(notification_type, "receive_system")
        try:
            pref = cls.objects.get(user=user)
            return getattr(pref, field, True)
        except cls.DoesNotExist:
            return True  # Standart: barcha bildirishnomalar yoqilgan


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
    launcher_position = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["center", "user", "updated_at"]),
            models.Index(fields=["center", "updated_at"]),
            models.Index(fields=["user", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.center_id} / {self.user_id} / {self.title}"


class DirectorAIChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = (
        (ROLE_USER, "Foydalanuvchi"),
        (ROLE_ASSISTANT, "AI"),
    )

    session = models.ForeignKey(
        DirectorAIChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    source = models.CharField(max_length=24, blank=True, default="")
    metadata = models.JSONField(blank=True, default=dict)
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


class ChurnRisk(models.Model):
    """
    O'quvchi ketish xavfi baholash.
    Har kuni yoki qo'lda yangilanadi.
    """
    HIGH   = 'high'
    MEDIUM = 'medium'
    LOW    = 'low'
    RISK_CHOICES = [
        (HIGH,   'Yuqori xavf'),
        (MEDIUM, "O'rta xavf"),
        (LOW,    'Past xavf'),
    ]

    center      = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='churn_risks')
    student     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='churn_risks',
        limit_choices_to={'role': 'student'},
    )
    risk_level  = models.CharField(max_length=10, choices=RISK_CHOICES, default=LOW)
    risk_score  = models.PositiveSmallIntegerField(default=0, help_text="0–100: yuqori = xavfli")
    reasons     = models.JSONField(default=list, help_text="Xavf sabablari ro'yxati")
    att_pct     = models.SmallIntegerField(default=100, help_text="So'nggi 30 kunlik davomat %")
    debt_amount = models.BigIntegerField(default=0, help_text="Joriy qarz summasi (so'm)")
    notified    = models.BooleanField(default=False, help_text="Menejerga xabar yuborilganmi?")
    notified_at = models.DateTimeField(null=True, blank=True)
    assessed_at = models.DateTimeField(auto_now=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-risk_score']
        verbose_name        = "Churn Xavfi"
        verbose_name_plural = "Churn Xavflari"
        indexes = [
            models.Index(fields=['center', 'risk_level']),
            models.Index(fields=['student', 'assessed_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['center', 'student'],
                name='core_churn_risk_unique_center_student',
            )
        ]

    def __str__(self):
        return f"{self.student} | {self.get_risk_level_display()} | {self.risk_score}"


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


class GameSession(models.Model):
    """O'quvchi o'ynagan mini-o'yin sessiyasi."""
    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name="game_sessions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_sessions",
        limit_choices_to={"role": "student"},
    )
    game_slug = models.CharField(max_length=32, db_index=True)
    score = models.PositiveIntegerField(default=0)
    level = models.PositiveSmallIntegerField(default=1)
    duration_sec = models.PositiveIntegerField(default=0)
    coins_earned = models.PositiveIntegerField(default=0)
    balls_earned = models.PositiveSmallIntegerField(default=0)
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-played_at"]
        indexes = [
            models.Index(fields=["center", "student", "game_slug", "played_at"]),
            models.Index(fields=["center", "game_slug", "score"]),
            models.Index(fields=["student", "played_at"]),
        ]

    def __str__(self):
        return f"{self.student_id} / {self.game_slug} / {self.score}"


class GlobalGameConfig(models.Model):
    """Super admin: qaysi o'yinlar barcha markazlarda ko'rinadi."""
    game_slug = models.CharField(max_length=32, unique=True, db_index=True)
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Global O'yin Sozlamasi"
        verbose_name_plural = "Global O'yin Sozlamalari"

    def __str__(self):
        return f"{self.game_slug}: {'✓' if self.is_enabled else '✗'}"


class CenterGameConfig(models.Model):
    """Director/Manager: markazga xos o'yin sozlamalari."""
    center = models.ForeignKey(
        Center, on_delete=models.CASCADE, related_name="game_configs"
    )
    game_slug = models.CharField(max_length=32)
    is_enabled = models.BooleanField(default=True)
    max_coins = models.PositiveSmallIntegerField(
        default=0, help_text="0 = standart qiymat ishlatiladi"
    )
    min_score = models.PositiveSmallIntegerField(
        default=0, help_text="0 = standart qiymat ishlatiladi"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="game_config_edits"
    )

    class Meta:
        unique_together = [["center", "game_slug"]]
        verbose_name = "Markaz O'yin Sozlamasi"
        verbose_name_plural = "Markaz O'yin Sozlamalari"
        indexes = [models.Index(fields=["center", "game_slug"])]

    def __str__(self):
        return f"{self.center_id}/{self.game_slug}"


class StudentGameProgress(models.Model):
    """O'quvchining har bir o'yindagi level progressi."""
    center = models.ForeignKey(
        Center, on_delete=models.CASCADE, related_name="student_game_progress"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="game_progress",
        limit_choices_to={"role": "student"},
    )
    game_slug = models.CharField(max_length=32)
    current_level = models.PositiveSmallIntegerField(default=1)
    best_score = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["center", "student", "game_slug"]]
        verbose_name = "O'quvchi O'yin Progressi"
        verbose_name_plural = "O'quvchi O'yin Progresslari"
        indexes = [
            models.Index(fields=["center", "student"]),
            models.Index(fields=["student", "game_slug"]),
        ]

    def __str__(self):
        return f"{self.student_id}/{self.game_slug}/L{self.current_level}"


class GameSuggestion(models.Model):
    """O'quvchi tomonidan taklif qilingan yangi o'yin."""
    center = models.ForeignKey(
        Center, on_delete=models.CASCADE, related_name="game_suggestions"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="game_suggestions",
    )
    game_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "O'yin Taklifi"
        verbose_name_plural = "O'yin Takliflari"

    def __str__(self):
        return f"{self.student_id}: {self.game_name}"


class GameQuestion(models.Model):
    """O'yin savollari — markazga tegishli yoki global (center=None)."""
    center = models.ForeignKey(
        Center, on_delete=models.CASCADE, null=True, blank=True,
        related_name="game_questions",
    )
    game_slug = models.CharField(max_length=32, db_index=True)
    level = models.PositiveSmallIntegerField(default=1)
    question_data = models.JSONField()
    is_active = models.BooleanField(default=True)
    is_ai_generated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_game_qs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["game_slug", "level", "created_at"]
        indexes = [models.Index(fields=["center", "game_slug", "is_active"])]
        verbose_name = "O'yin Savoli"
        verbose_name_plural = "O'yin Savollari"

    def __str__(self):
        return f"{self.game_slug}/L{self.level}: {str(self.question_data)[:60]}"


class GameBallsConfig(models.Model):
    """Markaz uchun o'yin balli almashtirish sozlamalari."""
    center = models.OneToOneField(
        Center, on_delete=models.CASCADE, related_name="game_balls_config"
    )
    min_balls_to_convert = models.PositiveSmallIntegerField(
        default=100,
        help_text="Minimal ball miqdori (chaqmoqqa almashtrish uchun)"
    )
    chaqmoq_per_conversion = models.PositiveSmallIntegerField(
        default=5,
        help_text="Bir konvertatsiyada beriladi"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "O'yin Balli Sozlamasi"
        verbose_name_plural = "O'yin Balli Sozlamalari"

    def __str__(self):
        return f"{self.center}: {self.min_balls_to_convert} ball → {self.chaqmoq_per_conversion} ⚡"


class StudentBallsWallet(models.Model):
    """O'quvchining o'yin balli hisobchasi."""
    center = models.ForeignKey(
        Center, on_delete=models.CASCADE, related_name="student_balls_wallets"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="balls_wallet",
        limit_choices_to={"role": "student"},
    )
    total_balls = models.PositiveIntegerField(
        default=0, help_text="Konvertatsiya qilinmagan ballar"
    )
    lifetime_balls = models.PositiveIntegerField(
        default=0, help_text="Jami qo'shilgan ballar (hech qachon kamaymas)"
    )
    last_ball_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["center", "student"]]
        verbose_name = "O'quvchi Ball Hisobchasi"
        verbose_name_plural = "O'quvchi Ball Hisobchalari"
        indexes = [models.Index(fields=["center", "student"])]

    def __str__(self):
        return f"{self.student_id}: {self.total_balls} ball"


class GameBallsConversionLog(models.Model):
    """Ball → chaqmoq konvertatsiya tarixi."""
    center = models.ForeignKey(
        Center, on_delete=models.CASCADE, related_name="balls_conversions"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="balls_conversions",
    )
    balls_spent = models.PositiveSmallIntegerField()
    chaqmoq_earned = models.PositiveSmallIntegerField()
    converted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-converted_at"]
        verbose_name = "Ball Konvertatsiyasi"
        verbose_name_plural = "Ball Konvertatsiyalari"

    def __str__(self):
        return f"{self.student_id}: {self.balls_spent} ball → {self.chaqmoq_earned} ⚡"
