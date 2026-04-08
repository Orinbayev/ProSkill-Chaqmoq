import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_list_item_card.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _queuedLoad = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_queuedLoad) {
      return;
    }
    _queuedLoad = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      context.read<NotificationsProvider>().load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationsProvider>();

    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingState(title: 'Bildirishnomalar yuklanmoqda...');
    }

    if (provider.errorMessage != null && provider.items.isEmpty) {
      return EmptyState(
        icon: Icons.notifications_off_rounded,
        title: 'Bildirishnomalar bo\'limi ochilmadi',
        message: provider.errorMessage!,
        actionLabel: 'Qayta urinish',
        onAction: () => context.read<NotificationsProvider>().load(),
      );
    }

    return RefreshIndicator(
      onRefresh: () => context.read<NotificationsProvider>().load(),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          AppPageHeader(
            title: '${provider.unreadCount} ta o\'qilmagan bildirishnoma',
            subtitle:
                'Faollik, to\'lov va sinf bo\'yicha xabarlarni kuzatib boring.',
            action: AppButton(
              label: 'Barchasini o\'qish',
              icon: Icons.done_all_rounded,
              expanded: false,
              variant: AppButtonVariant.tonal,
              loading: provider.isSaving,
              onPressed: provider.items.isEmpty
                  ? null
                  : () async {
                      final ok = await context
                          .read<NotificationsProvider>()
                          .markAllRead();
                      if (!context.mounted || !ok) {
                        return;
                      }
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Barcha bildirishnomalar o\'qilgan deb belgilandi',
                          ),
                        ),
                      );
                    },
            ),
          ),
          const SizedBox(height: 14),
          if (provider.items.isEmpty)
            const EmptyState(
              icon: Icons.notifications_none_rounded,
              title: 'Hali bildirishnomalar yo\'q',
              message: 'Yangi tizim xabarlari va eslatmalar shu yerda ko\'rinadi.',
            )
          else
            for (final item in provider.items) ...[
              AppListItemCard(
                title: item.title,
                subtitle: item.message,
                leading: Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: item.isRead
                        ? const Color(0xFFE2E8F0)
                        : Theme.of(
                            context,
                          ).colorScheme.primary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    item.isRead
                        ? Icons.notifications_none_rounded
                        : Icons.notifications_active_rounded,
                    color: item.isRead
                        ? const Color(0xFF64748B)
                        : Theme.of(context).colorScheme.primary,
                  ),
                ),
                tags: [
                  Chip(
                    label: Text(
                      AppFormatters.notificationTypeLabel(item.type),
                    ),
                  ),
                ],
                footer: Text(
                  AppFormatters.formatDateTime(item.createdAt),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              if (item != provider.items.last) const SizedBox(height: 14),
            ],
        ],
      ),
    );
  }
}
