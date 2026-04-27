import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/groups/groups_screen.dart';
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart';
import 'package:chaqmoq_mobile/screens/students/students_screen.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_loaded) {
      _loaded = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          context.read<NotificationsProvider>().load();
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationsProvider>();
    final items = provider.items;
    return Container(
      color: _NotificationsColors.background,
      child: RefreshIndicator(
        color: _NotificationsColors.accentBlue,
        onRefresh: provider.refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(
            parent: BouncingScrollPhysics(),
          ),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            _NotificationsHeader(
              unreadCount: provider.unreadCount,
              canMarkAllRead: items.isNotEmpty && provider.unreadCount > 0,
              onMarkAllRead: () => _markAllRead(provider),
            ),
            if (provider.state == ViewState.loading && items.isNotEmpty) ...[
              const SizedBox(height: 14),
              const LinearProgressIndicator(
                minHeight: 3,
                color: _NotificationsColors.accentBlue,
                backgroundColor: Color(0xFFEAF4FF),
              ),
            ],
            const SizedBox(height: 16),
            if (provider.state == ViewState.loading && items.isEmpty)
              const _NotificationsStateCard.loading()
            else if (provider.state == ViewState.error && items.isEmpty)
              _NotificationsStateCard(
                title: 'Bildirishnomalar yuklanmadi',
                message: provider.errorMessage ?? 'Qayta urinib ko‘ring',
                icon: Icons.notifications_off_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: provider.refresh,
              )
            else if (items.isEmpty)
              const _NotificationsStateCard(
                title: 'Xabar yo‘q',
                message: 'Hozircha yangi bildirishnomalar mavjud emas.',
                icon: Icons.mark_email_read_rounded,
              )
            else
              ...items.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _NotificationCard(
                    item: item,
                    onTap: () => _openNotification(provider, item),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _markAllRead(NotificationsProvider provider) async {
    await provider.markAllRead();
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Barcha bildirishnomalar o‘qildi')),
    );
  }

  Future<void> _openNotification(
    NotificationsProvider provider,
    NotificationModel item,
  ) async {
    await provider.markRead(item);
    if (!mounted) {
      return;
    }
    final lower = item.type.toLowerCase();
    if (lower.contains('payment')) {
      Navigator.of(
        context,
      ).push(MaterialPageRoute<void>(builder: (_) => const PaymentsScreen()));
      return;
    }
    if (lower.contains('student')) {
      Navigator.of(
        context,
      ).push(MaterialPageRoute<void>(builder: (_) => const StudentsScreen()));
      return;
    }
    if (lower.contains('group')) {
      Navigator.of(
        context,
      ).push(MaterialPageRoute<void>(builder: (_) => const GroupsScreen()));
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(_notificationTitle(item) ?? 'Bildirishnoma ochildi'),
      ),
    );
  }

  String? _notificationTitle(NotificationModel item) {
    final title = cleanHtmlText(item.title);
    if (title.isNotEmpty) {
      return title;
    }
    final body = cleanHtmlText(item.body);
    return body.isEmpty ? null : body;
  }
}

class _NotificationsHeader extends StatelessWidget {
  const _NotificationsHeader({
    required this.unreadCount,
    required this.canMarkAllRead,
    required this.onMarkAllRead,
  });

  final int unreadCount;
  final bool canMarkAllRead;
  final VoidCallback onMarkAllRead;

  @override
  Widget build(BuildContext context) {
    final badgeLabel = unreadCount > 99 ? '99+' : '$unreadCount';
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: _cardDecoration,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: const Icon(
                  Icons.notifications_active_rounded,
                  color: _NotificationsColors.accentBlue,
                  size: 28,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bildirishnomalar',
                      style: _NotificationsTextStyles.title,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Yangi xabarlar va tezkor ogohlantirishlar',
                      style: _NotificationsTextStyles.subtitle,
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(badgeLabel, style: _NotificationsTextStyles.badge),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: canMarkAllRead ? onMarkAllRead : null,
              style: TextButton.styleFrom(
                foregroundColor: _NotificationsColors.accentBlue,
                disabledForegroundColor: const Color(0xFF9AA4B2),
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              icon: const Icon(Icons.done_all_rounded, size: 18),
              label: Text(
                'Barchasini o‘qildi',
                style: _NotificationsTextStyles.action,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.item, required this.onTap});

  final NotificationModel item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final title = cleanHtmlText(item.title).trim();
    final message = cleanHtmlText(item.body).trim();
    final hasMessage = message.isNotEmpty;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: _cardDecoration,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: item.isRead
                      ? const Color(0xFFF3F6FB)
                      : const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: Icon(
                  _iconForType(item.type),
                  color: _NotificationsColors.accentBlue,
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            title.isEmpty ? 'Bildirishnoma' : title,
                            style: _NotificationsTextStyles.cardTitle,
                          ),
                        ),
                        if (!item.isRead) ...[
                          const SizedBox(width: 10),
                          Container(
                            width: 9,
                            height: 9,
                            margin: const EdgeInsets.only(top: 6),
                            decoration: const BoxDecoration(
                              color: _NotificationsColors.accentBlue,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ],
                      ],
                    ),
                    if (hasMessage) ...[
                      const SizedBox(height: 8),
                      Text(message, style: _NotificationsTextStyles.cardBody),
                    ],
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        const Icon(
                          Icons.schedule_rounded,
                          size: 16,
                          color: _NotificationsColors.secondaryText,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            _notificationDate(item.createdAt),
                            style: _NotificationsTextStyles.metadata,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _notificationDate(DateTime value) {
    final difference = DateTime.now().difference(value);
    if (difference.inDays < 7) {
      return Formatters.relative(value);
    }
    return Formatters.dateTime(value);
  }

  IconData _iconForType(String type) {
    final lower = type.toLowerCase();
    if (lower.contains('payment') || lower.contains('tolov')) {
      return Icons.account_balance_wallet_outlined;
    }
    if (lower.contains('student')) {
      return Icons.groups_rounded;
    }
    if (lower.contains('group')) {
      return Icons.view_module_rounded;
    }
    if (lower.contains('grade') ||
        lower.contains('score') ||
        lower.contains('baho')) {
      return Icons.star_border_rounded;
    }
    return Icons.notifications_rounded;
  }
}

class _NotificationsStateCard extends StatelessWidget {
  const _NotificationsStateCard({
    required this.title,
    required this.message,
    required this.icon,
    this.actionLabel,
    this.onAction,
  });

  const _NotificationsStateCard.loading()
    : title = 'Yuklanmoqda',
      message = 'Bildirishnomalar tayyorlanmoqda...',
      icon = Icons.notifications_active_outlined,
      actionLabel = null,
      onAction = null;

  final String title;
  final String message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: _cardDecoration,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: const Color(0xFFEAF4FF),
              borderRadius: BorderRadius.circular(20),
            ),
            alignment: Alignment.center,
            child: actionLabel == null && onAction == null
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.2,
                      color: _NotificationsColors.accentBlue,
                    ),
                  )
                : Icon(icon, color: _NotificationsColors.accentBlue, size: 28),
          ),
          const SizedBox(height: 16),
          Text(
            title,
            textAlign: TextAlign.center,
            style: _NotificationsTextStyles.title,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: _NotificationsTextStyles.subtitle,
          ),
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: 18),
            FilledButton(
              onPressed: onAction,
              style: FilledButton.styleFrom(
                backgroundColor: _NotificationsColors.accentBlue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 14,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: Text(actionLabel!, style: _NotificationsTextStyles.button),
            ),
          ],
        ],
      ),
    );
  }
}

const BoxDecoration _cardDecoration = BoxDecoration(
  color: _NotificationsColors.card,
  borderRadius: BorderRadius.all(Radius.circular(18)),
  border: Border.fromBorderSide(BorderSide(color: _NotificationsColors.border)),
  boxShadow: [
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ],
);

class _NotificationsColors {
  const _NotificationsColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color card = Color(0xFFFFFFFF);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color accentBlue = Color(0xFF1E73F8);
  static const Color border = Color(0xFFE5EAF2);
}

class _NotificationsTextStyles {
  const _NotificationsTextStyles._();

  static TextStyle get title => GoogleFonts.inter(
    fontSize: 20,
    fontWeight: FontWeight.w800,
    height: 1.2,
    color: _NotificationsColors.text,
  );

  static TextStyle get subtitle => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.45,
    color: _NotificationsColors.secondaryText,
  );

  static TextStyle get action => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w700,
    color: _NotificationsColors.accentBlue,
  );

  static TextStyle get badge => GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w800,
    color: _NotificationsColors.accentBlue,
  );

  static TextStyle get cardTitle => GoogleFonts.inter(
    fontSize: 15.5,
    fontWeight: FontWeight.w700,
    height: 1.35,
    color: _NotificationsColors.text,
  );

  static TextStyle get cardBody => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.5,
    color: _NotificationsColors.text,
  );

  static TextStyle get metadata => GoogleFonts.inter(
    fontSize: 13,
    fontWeight: FontWeight.w500,
    height: 1.35,
    color: _NotificationsColors.secondaryText,
  );

  static TextStyle get button => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w700,
    color: Colors.white,
  );
}
