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

    def __str__(self):
        return f"{self.recipient} -> {self.title}"
