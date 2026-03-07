from django.db import models
from django.utils import timezone
from django.conf import settings

class SoftDeleteQuerySet(models.QuerySet):
    def delete(self, deleted_by=None):
        """Soft delete for queryset"""
        return super().update(
            is_deleted=True, 
            deleted_at=timezone.now(),
            deleted_by=deleted_by
        )

    def hard_delete(self):
        """Permanent delete for queryset"""
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)

class SoftDeleteManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop('alive_only', True)
        super(SoftDeleteManager, self).__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)
        return SoftDeleteQuerySet(self.model, using=self._db)

    def delete(self, deleted_by=None):
        return self.get_queryset().delete(deleted_by=deleted_by)

    def hard_delete(self):
        return self.get_queryset().hard_delete()

class SoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False, verbose_name="O'chirilgan")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="O'chirilgan sana/vaqt")
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="deleted_%(class)s_items",
        verbose_name="O'chirgan foydalanuvchi"
    )
    deleted_reason = models.TextField(null=True, blank=True, verbose_name="O'chirish sababi")

    # Audit for restore
    restored_at = models.DateTimeField(null=True, blank=True, verbose_name="Tiklangan sana/vaqt")
    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="restored_%(class)s_items",
        verbose_name="Tiklagan foydalanuvchi"
    )

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager(alive_only=False)

    class Meta:
        abstract = True

    def delete(self, deleted_by=None, reason=None, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if deleted_by:
            self.deleted_by = deleted_by
        if reason:
            self.deleted_reason = reason
        self.save()

    def restore(self, restored_by=None):
        self.is_deleted = False
        self.restored_at = timezone.now()
        if restored_by:
            self.restored_by = restored_by
        self.save()

    def hard_delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
