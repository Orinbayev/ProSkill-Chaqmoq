import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Student notifications — dark glass list, mirrors NotificationsScreen JSX.
class StudentNotificationsScreen extends StatefulWidget {
  const StudentNotificationsScreen({super.key});

  @override
  State<StudentNotificationsScreen> createState() =>
      _StudentNotificationsScreenState();
}

class _StudentNotificationsScreenState
    extends State<StudentNotificationsScreen> {
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
    final tokens = StudentTokens.of(context);
    final provider = context.watch<NotificationsProvider>();
    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        child: RefreshIndicator(
          color: tokens.primary,
          onRefresh: _refresh,
          child: _body(provider, tokens),
        ),
      ),
    );
  }

  Widget _body(NotificationsProvider provider, StudentTokens tokens) {
    if (provider.state == ViewState.loading && provider.items.isEmpty) {
      return AppLoadingState(dark: tokens.isDark);
    }
    if (provider.state == ViewState.error && provider.items.isEmpty) {
      return AppErrorState(
        title: 'Bildirishnomalar yuklanmadi',
        message: 'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        dark: tokens.isDark,
        onRetry: () => provider.refresh(),
      );
    }
    final unread = provider.unreadCount;
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Bildirishnomalar',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 19,
                      fontWeight: FontWeight.w800,
                      color: tokens.text,
                      letterSpacing: -0.2,
                    ),
                  ),
                  const SizedBox(height: 1),
                  Text(
                    '$unread yangi',
                    style: GoogleFonts.inter(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: tokens.textMuted,
                    ),
                  ),
                ],
              ),
            ),
            if (unread > 0)
              Material(
                color: Colors.transparent,
                borderRadius: BorderRadius.circular(12),
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: provider.markAllRead,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(
                      color: tokens.glass,
                      border: Border.all(color: tokens.border),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.done_all_rounded, color: tokens.text, size: 18),
                        const SizedBox(width: 6),
                        Text(
                          'Hammasi',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: tokens.text,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              )
            else
              AppStudentIconButton(icon: Icons.tune_rounded, onTap: () {}),
          ],
        ),
        const SizedBox(height: 14),
        if (provider.items.isEmpty)
          AppEmptyState(
            dark: tokens.isDark,
            title: 'Bildirishnoma yo‘q',
            subtitle: 'Yangi xabarlar paydo bo‘lganda shu yerda ko‘rinadi.',
            icon: Icons.notifications_off_outlined,
          )
        else
          ...provider.items.map((n) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _NotificationTile(
                  item: n,
                  onTap: () => provider.markRead(n),
                ),
              )),
      ],
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item, required this.onTap});

  final NotificationModel item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final unread = !item.isRead;
    final iconBg = unread ? tokens.tonedSurface(tokens.primary) : tokens.glass;
    final iconFg = unread ? tokens.primary : tokens.textMuted;
    return AppGCard(
      borderColor: unread ? tokens.tonedBorder(tokens.primary) : null,
      onTap: onTap,
      padding: const EdgeInsets.all(14),
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
                child: Icon(_iconFor(item.type), color: iconFg, size: 22),
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
                              color: tokens.text,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          Formatters.relative(item.createdAt),
                          style: GoogleFonts.inter(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w600,
                            color: tokens.textMuted,
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
                          color: tokens.textMuted,
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
            Positioned(
              top: 0,
              right: 0,
              child: Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: tokens.primary,
                  shape: BoxShape.circle,
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
    if (t.contains('grade') || t.contains('score') || t.contains('progress')) return Icons.grade_outlined;
    if (t.contains('msg') || t.contains('chat')) return Icons.forum_outlined;
    if (t.contains('system')) return Icons.check_circle_outline_rounded;
    return Icons.notifications_outlined;
  }
}
