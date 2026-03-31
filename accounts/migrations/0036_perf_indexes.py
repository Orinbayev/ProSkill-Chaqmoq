"""
Performance indexes migration — 2026-03-31
==========================================
Qo'shilgan indexlar:

User model:
  - phone_number: Login da User.objects.get(phone_number=...) — index yo'q edi
  - role: filter(role='student'), filter(role='teacher') — har yerda ishlatiladi
  - center + role (composite): users = User.objects.filter(center=c, role='student')
  - is_archived: filter(is_archived=False) — student query da
  - center + is_archived (composite): eng ko'p ishlatiladigan filter

Center model:
  - slug: URL routing da har requestda filter(slug=...) — CRITICAL
  - status: filter(status='ACTIVE') — middleware va views da
  - is_deleted: filter(is_deleted=False) — deyarli barcha querylarda

Bu migration SAFE — mavjud ma'lumotlarga ta'siri yo'q, faqat index qo'shadi.
Revert: RemoveIndex bilan osonlikcha olib tashlash mumkin.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0035_center_is_demo_user_is_demo_user'),
    ]

    operations = [
        # ── User.phone_number ──────────────────────────────────────
        # Login: User.objects.get(phone_number=normalized_phone)
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['phone_number'], name='user_phone_perf_idx'),
        ),

        # ── User.role ──────────────────────────────────────────────
        # _build_stats: filter(role='manager'), filter(role='teacher'), filter(role='student')
        # teacher_list, student_list, va boshqa ko'p joylarda
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['role'], name='user_role_perf_idx'),
        ),

        # ── User.is_archived ──────────────────────────────────────
        # filter(is_archived=False) — student querylarda
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['is_archived'], name='user_is_archived_perf_idx'),
        ),

        # ── User(center, role) composite ──────────────────────────
        # _build_stats aggregate: filter(center=center) + role condition
        # Eng tez-tez ishlatiladigan filtr kombinatsiyasi
        migrations.AddIndex(
            model_name='user',
            index=models.Index(
                fields=['center', 'role'],
                name='user_center_role_perf_idx',
            ),
        ),

        # ── User(center, role, is_archived) composite ─────────────
        # filter(center=center, role='student', is_archived=False)
        migrations.AddIndex(
            model_name='user',
            index=models.Index(
                fields=['center', 'role', 'is_archived'],
                name='user_center_role_arch_idx',
            ),
        ),

        # ── Center.slug ────────────────────────────────────────────
        # CRITICAL: TenantMiddleware da har URL requestda
        # Center._default_manager.filter(slug=slug, is_deleted=False)
        # slug unique=True bo'lsa ham, composite index qo'shamiz
        migrations.AddIndex(
            model_name='center',
            index=models.Index(
                fields=['slug', 'is_deleted'],
                name='center_slug_deleted_perf_idx',
            ),
        ),

        # ── Center.status ─────────────────────────────────────────
        # filter(status='ACTIVE') — middleware, billing, superadmin
        migrations.AddIndex(
            model_name='center',
            index=models.Index(fields=['status'], name='center_status_perf_idx'),
        ),

        # ── Center.is_deleted ─────────────────────────────────────
        # filter(is_deleted=False) — deyarli barcha Center querylarda
        migrations.AddIndex(
            model_name='center',
            index=models.Index(fields=['is_deleted'], name='center_is_deleted_perf_idx'),
        ),
    ]
