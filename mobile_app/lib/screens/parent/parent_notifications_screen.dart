import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Parent notifications — light theme list.
/// Mirrors NotificationsScreen JSX: app bar with counter + done_all,
/// list with unread tint, click → mark read.
class ParentNotificationsScreen extends StatefulWidget {
  const ParentNotificationsScreen({super.key});

  @override
  State<ParentNotificationsScreen> createState() =>
      _ParentNotificationsScreenState();
}

class _ParentNotificationsScreenState extends State<ParentNotificationsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<NotificationsProvider>().load();
    });
  }

  Future<void> _refresh() async {
    await context.read<NotificationsProvider>().refresh();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationsProvider>();
    return Scaffold(
      backgroundColor: ParentColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            AppParentAppBar(
              title: 'Bildirishnomalar',
              onBack: () => Navigator.of(context).maybePop(),
              right: provider.unreadCount > 0
                  ? Material(
                      color: Colors.transparent,
                      borderRadius: BorderRadius.circular(12),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(12),
                        onTap: provider.markAllRead,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 10),
                          decoration: BoxDecoration(
                            color: ParentColors.card,
                            border: Border.all(color: ParentColors.line),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.done_all_rounded,
                                  color: ParentColors.text, size: 18),
                              const SizedBox(width: 6),
                              Text('Hammasi',
                                  style: GoogleFonts.inter(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: ParentColors.text,
                                  )),
                            ],
                          ),
                        ),
                      ),
                    )
                  : null,
            ),
            Expanded(
              child: RefreshIndicator(
                color: ParentColors.primary,
                onRefresh: _refresh,
                child: _body(provider),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _body(NotificationsProvider provider) {
    if (provider.state == ViewState.loading && provider.items.isEmpty) {
      return const AppLoadingState();
    }
    if (provider.state == ViewState.error && provider.items.isEmpty) {
      return AppErrorState(
        title: 'Bildirishnomalar yuklanmadi',
        message: 'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        onRetry: () => provider.refresh(),
      );
    }
    if (provider.items.isEmpty) {
      return const AppEmptyState(
        title: 'Bildirishnoma yo‘q',
        subtitle: 'Yangi xabarlar paydo bo‘lganda shu yerda ko‘rinadi.',
        icon: Icons.notifications_off_outlined,
      );
    }
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 28),
      children: provider.items
          .map((n) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _Tile(
                  item: n,
                  onTap: () => provider.markRead(n),
                ),
              ))
          .toList(),
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.item, required this.onTap});

  final NotificationModel item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final unread = !item.isRead;
    final iconBg = unread ? ParentColors.primaryTint : ParentColors.bgSoft;
    final iconFg = unread ? ParentColors.primaryDeep : ParentColors.textMuted;
    return AppPCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      borderColor: unread ? const Color(0xFFBFDBFE) : null,
      background: unread ? ParentColors.primaryTint : null,
      child: Stack(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: iconBg,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(_iconFor(item.type), size: 22, color: iconFg),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.inter(
                              fontSize: 13.5,
                              fontWeight: FontWeight.w800,
                              color: ParentColors.text,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          Formatters.relative(item.createdAt),
                          style: GoogleFonts.inter(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w600,
                            color: ParentColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                    if (item.body.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        item.body,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: ParentColors.textMuted,
                          height: 1.45,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          if (unread)
            const Positioned(
              top: 0,
              right: 0,
              child: SizedBox(
                width: 8,
                height: 8,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: ParentColors.primary,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  IconData _iconFor(String type) {
    final t = type.toLowerCase();
    if (t.contains('pay')) return Icons.payments_outlined;
    if (t.contains('attend')) return Icons.fact_check_outlined;
    if (t.contains('grade') || t.contains('score') || t.contains('progress')) {
      return Icons.grade_outlined;
    }
    if (t.contains('msg') || t.contains('chat')) return Icons.forum_outlined;
    if (t.contains('system')) return Icons.check_circle_outline_rounded;
    return Icons.notifications_outlined;
  }
}
