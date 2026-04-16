import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/groups/groups_screen.dart';
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart';
import 'package:chaqmoq_mobile/screens/students/students_screen.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    context.read<NotificationsProvider>().load();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationsProvider>();
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      children: [
        GlassCard(
          child: Row(
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  const Icon(Icons.notifications_active_rounded, size: 32, color: AppColors.primary),
                  Positioned(
                    right: -8,
                    top: -6,
                    child: CircleAvatar(
                      radius: 10,
                      backgroundColor: AppColors.danger,
                      child: Text(
                        '${provider.unreadCount}',
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.white, fontSize: 10),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Bildirishnomalar', style: AppTextStyles.title),
                    const SizedBox(height: AppSpacing.xs),
                    Text('Yangi xabarlar va tezkor ogohlantirishlar', style: AppTextStyles.bodySmall),
                  ],
                ),
              ),
              if (provider.unreadCount > 0)
                TextButton(
                  onPressed: provider.markAllRead,
                  child: const Text('Barchasini o\'qildi'),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        if (provider.state == ViewState.error)
          EmptyState(
            title: 'Bildirishnomalar yuklanmadi',
            message: provider.errorMessage ?? 'Qayta urinib ko\'ring',
            icon: Icons.notifications_off_rounded,
            actionLabel: 'Qayta yuklash',
            onAction: provider.refresh,
          )
        else if (provider.items.isEmpty && provider.state != ViewState.loading)
          const EmptyState(
            title: 'Xabar yo\'q',
            message: 'Hozircha yangi bildirishnomalar mavjud emas',
            icon: Icons.mark_email_read_rounded,
          )
        else
          ...provider.items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.lg),
              child: GlassCard(
                onTap: () => _openNotification(context, provider, item),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: item.isRead
                            ? AppColors.surfaceAlt
                            : AppColors.primary.withValues(alpha: 0.18),
                        borderRadius: BorderRadius.circular(AppRadius.lg),
                      ),
                      alignment: Alignment.center,
                      child: Icon(_iconForType(item.type), color: AppColors.primary),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(item.title, style: AppTextStyles.body),
                          const SizedBox(height: AppSpacing.xs),
                          Text(item.body, style: AppTextStyles.bodySmall),
                          const SizedBox(height: AppSpacing.sm),
                          Text(Formatters.relative(item.createdAt), style: AppTextStyles.bodySmall),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  void _openNotification(
    BuildContext context,
    NotificationsProvider provider,
    NotificationModel item,
  ) {
    provider.markRead(item);
    final lower = item.type.toLowerCase();
    if (lower.contains('payment')) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => const PaymentsScreen()),
      );
      return;
    }
    if (lower.contains('student')) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => const StudentsScreen()),
      );
      return;
    }
    if (lower.contains('group')) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => const GroupsScreen()),
      );
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(item.title)),
    );
  }

  IconData _iconForType(String type) {
    final lower = type.toLowerCase();
    if (lower.contains('payment')) {
      return Icons.payments_rounded;
    }
    if (lower.contains('student')) {
      return Icons.groups_rounded;
    }
    if (lower.contains('group')) {
      return Icons.view_module_rounded;
    }
    return Icons.notifications_rounded;
  }
}
