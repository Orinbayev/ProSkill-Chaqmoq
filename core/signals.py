from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification, NotificationPreference
from chaqmoq.models import Ledger
from store.models import PurchaseRequest
from accounts.models import Center
from accounts.utils_bot import send_telegram_message
from education.models import Attendance


def _should_notify(user, notification_type: str) -> bool:
    """Foydalanuvchi bu turdagi bildirishnomani xohlaydi?"""
    return NotificationPreference.wants_notification(user, notification_type)


@receiver(post_save, sender=Ledger)
def notify_ledger_change(sender, instance, created, **kwargs):
    if created and instance.student:
        user = instance.student

        if not user.is_active:
            return

        # Preference tekshiruvi
        if not _should_notify(user, "coin"):
            return

        sender_name = instance.beruvchi.full_name() if instance.beruvchi else "Tizim"
        rule_name = instance.rule.nom if instance.rule else instance.rule_nom

        if instance.ball > 0:
            msg = (f"Sizga {sender_name} tomonidan <b>{instance.ball} chaqmoq</b> qo’shildi.<br>"
                   f"Sabab: <b>{rule_name}</b>")
            title = "Chaqmoq qo’shildi ⚡"
        else:
            msg = (f"Sizdan {sender_name} tomonidan <b>{-instance.ball} chaqmoq</b> ayirildi.<br>"
                   f"Sabab: <b>{rule_name}</b>")
            title = "Chaqmoq ayirildi 📉"

        Notification.objects.create(
            recipient=user,
            sender=instance.beruvchi,
            center=instance.group.center if instance.group else user.center,
            title=title,
            message=msg,
            type="coin",
        )

        if user.is_telegram_linked and user.telegram_id:
            total_balance = Ledger.student_balansi(user.id, center=instance.group.center if instance.group else user.center)
            delta = f"+{instance.ball}" if instance.ball > 0 else str(instance.ball)
            tg_text = f"⚡ {delta} Chaqmoq ball o'zgardi! Jami: {total_balance}"
            send_telegram_message(user.telegram_id, tg_text)


@receiver(post_save, sender=Attendance)
def apply_attendance_lightning_rules(sender, instance, created, **kwargs):
    center = instance.center or getattr(instance.group, "center", None)
    if not instance.student or not center:
        return

    try:
        from chaqmoq.services import check_attendance_bonus, check_attendance_penalty

        actor = instance.created_by or instance.teacher
        check_attendance_bonus(
            student=instance.student,
            center=center,
            created_by=actor,
            target_date=instance.date,
        )
        check_attendance_penalty(
            student=instance.student,
            center=center,
            created_by=actor,
            target_date=instance.date,
        )
    except Exception:
        pass

@receiver(post_save, sender=Center)
def invalidate_center_middleware_cache(sender, instance, **kwargs):
    """Center o'zgarganda middleware in-process cache ni tozalaydi."""
    try:
        from core.middleware import invalidate_center_cache
        invalidate_center_cache(instance.pk)
    except Exception:
        pass


@receiver(post_save, sender=PurchaseRequest)
def notify_purchase_status(sender, instance, created, **kwargs):
    if not created:
        user = instance.student

        # Preference tekshiruvi
        if not _should_notify(user, "purchase"):
            return

        product_name = instance.product.nom if instance.product else "Mahsulot"

        if instance.status == PurchaseRequest.APPROVED:
            Notification.objects.create(
                recipient=user,
                title="So’rov tasdiqlandi ✅",
                message=f"Sizning ‘{product_name}’ mahsuloti uchun so’rovingiz tasdiqlandi.",
                type="purchase",
                center=instance.center,
            )
        elif instance.status == PurchaseRequest.REJECTED:
            Notification.objects.create(
                recipient=user,
                title="So’rov rad etildi ❌",
                message=f"Sizning ‘{product_name}’ mahsuloti uchun so’rovingiz rad etildi.",
                type="purchase",
                center=instance.center,
            )
