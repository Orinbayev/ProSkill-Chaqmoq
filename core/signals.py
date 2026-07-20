from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification, NotificationPreference
from chaqmoq.models import Ledger
from store.models import PurchaseRequest
from accounts.models import Center
from accounts.utils_bot import send_telegram_message
from education.models import Attendance, Payment, StudentGroupTransfer


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
        from core.middleware import invalidate_center_tree_cache
        invalidate_center_tree_cache(instance)
    except Exception:
        pass


def invalidate_on_subscription_change(sender, instance, **kwargs):
    """
    Subscription activate/block/expire → block cache darhol yangilanadi
    (phase 8: 1 soatlik lag o'rniga).
    """
    try:
        from core.middleware import invalidate_center_tree_cache
        center = getattr(instance, "center", None)
        if center is None and getattr(instance, "center_id", None):
            center = Center.objects.filter(pk=instance.center_id).first()
        invalidate_center_tree_cache(center)
    except Exception:
        pass


def connect_billing_cache_signals():
    """Called from CoreConfig.ready() to avoid import cycles with billing."""
    try:
        from billing.models import CenterSubscription
        from django.db.models.signals import post_save as _post_save

        _post_save.connect(
            invalidate_on_subscription_change,
            sender=CenterSubscription,
            dispatch_uid="core.invalidate_on_subscription_change",
        )
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


# ─── Ota-onalarga avtomatik xabar ─────────────────────────────────────────────

def _get_parent_telegram_ids(student):
    """O’quvchining Telegram ga ulangan ota-onalarini qaytaradi."""
    ids = []
    # 1. student.parent_telegram_id — tezkor to’g’ridan-to’g’ri maydon
    if getattr(student, "parent_telegram_id", None):
        ids.append(student.parent_telegram_id)
    # 2. M2M parents — family bot orqali ulangan ota-onalar
    try:
        for parent in student.parents.filter(is_telegram_linked=True, is_active=True):
            if parent.telegram_id and parent.telegram_id not in ids:
                ids.append(parent.telegram_id)
    except Exception:
        pass
    return ids


@receiver(post_save, sender=Attendance)
def notify_parent_on_absence(sender, instance, created, **kwargs):
    """O’quvchi darsga kelmasa yoki kech qolsa ota-onaga xabar."""
    try:
        student = instance.student
        if not student:
            return

        absent_statuses = ("absent_unexcused", "absent_excused", "late")
        if instance.status not in absent_statuses:
            return

        parent_tg_ids = _get_parent_telegram_ids(student)
        if not parent_tg_ids:
            return

        group_name = getattr(instance.group, "nom", "Guruh")
        date_str = instance.date.strftime("%d.%m.%Y") if instance.date else "—"
        student_name = student.get_full_name()

        if instance.status == "late":
            text = (
                f"⏰ <b>Darsga kech qoldi</b>\n\n"
                f"O’quvchi: <b>{student_name}</b>\n"
                f"Guruh: <b>{group_name}</b>\n"
                f"Sana: <b>{date_str}</b>\n\n"
                f"Farzandingiz darsga kech qoldi."
            )
        elif instance.status == "absent_excused":
            text = (
                f"🟡 <b>Darsga kelmadi (sababli)</b>\n\n"
                f"O’quvchi: <b>{student_name}</b>\n"
                f"Guruh: <b>{group_name}</b>\n"
                f"Sana: <b>{date_str}</b>"
            )
        else:
            text = (
                f"🔴 <b>Darsga kelmadi</b>\n\n"
                f"O’quvchi: <b>{student_name}</b>\n"
                f"Guruh: <b>{group_name}</b>\n"
                f"Sana: <b>{date_str}</b>\n\n"
                f"Farzandingiz bugun darsga kelmadi."
            )

        for tg_id in parent_tg_ids:
            send_telegram_message(tg_id, text)
    except Exception:
        pass


@receiver(post_save, sender=Payment)
def notify_parent_on_payment(sender, instance, created, **kwargs):
    """To’lov qilinganda ota-onaga tasdiqlash xabari."""
    if not created:
        return
    try:
        student = instance.student
        if not student:
            return

        parent_tg_ids = _get_parent_telegram_ids(student)
        if not parent_tg_ids:
            return

        group_name = getattr(instance.group, "nom", "Guruh")
        date_str = instance.paid_date.strftime("%d.%m.%Y") if instance.paid_date else "—"
        summa = instance.summa or 0

        text = (
            f"✅ <b>To’lov qabul qilindi</b>\n\n"
            f"O’quvchi: <b>{student.get_full_name()}</b>\n"
            f"Guruh: <b>{group_name}</b>\n"
            f"Summa: <b>{summa:,} so’m</b>\n"
            f"Sana: <b>{date_str}</b>\n\n"
            f"To’lovingiz tizimda qayd etildi."
        )

        for tg_id in parent_tg_ids:
            send_telegram_message(tg_id, text)
    except Exception:
        pass


@receiver(post_save, sender=StudentGroupTransfer)
def notify_parent_on_group_transfer(sender, instance, created, **kwargs):
    """O’quvchi guruhdan ko’chirilganda ota-onaga xabar."""
    if not created:
        return
    try:
        student = instance.student
        if not student:
            return

        parent_tg_ids = _get_parent_telegram_ids(student)
        if not parent_tg_ids:
            return

        old_group = getattr(instance.old_group, "nom", "—")
        new_group = getattr(instance.new_group, "nom", "—")
        date_str = instance.transfer_date.strftime("%d.%m.%Y") if instance.transfer_date else "—"

        text = (
            f"🔄 <b>Guruh o’zgartirildi</b>\n\n"
            f"O’quvchi: <b>{student.get_full_name()}</b>\n"
            f"Oldingi guruh: <b>{old_group}</b>\n"
            f"Yangi guruh: <b>{new_group}</b>\n"
            f"Sana: <b>{date_str}</b>"
        )

        for tg_id in parent_tg_ids:
            send_telegram_message(tg_id, text)
    except Exception:
        pass
