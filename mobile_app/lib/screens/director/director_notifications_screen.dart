import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_data.dart';
import 'data/director_provider.dart';
import 'widgets/director_states.dart';

class DirectorNotificationsScreen extends StatefulWidget {
  const DirectorNotificationsScreen({super.key});
  @override
  State<DirectorNotificationsScreen> createState() => _DirectorNotificationsScreenState();
}

class _DirectorNotificationsScreenState extends State<DirectorNotificationsScreen> {
  late Future<List<DirectorNotification>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<DirectorProvider>().loadNotifications();
  }

  Future<void> _reload() async {
    setState(() => _future = context.read<DirectorProvider>().loadNotifications());
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Scaffold(
      backgroundColor: ds.bg,
      appBar: AppBar(title: const Text('Bildirishnomalar')),
      body: FutureBuilder<List<DirectorNotification>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const DirectorLoading();
          }
          if (snapshot.hasError) {
            return DirectorErrorView(onRetry: _reload);
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const DirectorEmptyView(
              icon: Icons.notifications_none_rounded,
              text: 'Hozircha bildirishnoma yo\'q',
            );
          }
          return RefreshIndicator(
            color: ds.primary,
            onRefresh: _reload,
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x5, DsSpace.screen, DsSpace.x8),
              itemCount: items.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) => _NotificationCard(item: items[i]),
            ),
          );
        },
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.item});
  final DirectorNotification item;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final (icon, tone) = _iconFor(item.kind, ds);
    return DsCard(
      padding: const EdgeInsets.all(DsSpace.x4),
      color: item.isRead ? null : ds.primarySoft.withValues(alpha: ds.isDark ? 0.5 : 0.4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(color: tone.$1, borderRadius: DsRadius.all(DsRadius.sm)),
            child: Icon(icon, size: 20, color: tone.$2),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(item.title.isEmpty ? 'Bildirishnoma' : item.title,
                          style: DsType.bodyStrong(ds.textPrimary)),
                    ),
                    if (!item.isRead)
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(color: ds.primary, shape: BoxShape.circle),
                      ),
                  ],
                ),
                if (item.message.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(item.message, style: DsType.caption(ds.textSecondary)),
                ],
                if (item.createdAt.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(_fmtDate(item.createdAt), style: DsType.small(ds.textFaint)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  (IconData, (Color, Color)) _iconFor(String kind, DsColors ds) {
    switch (kind) {
      case 'payment':
        return (Icons.payments_rounded, (ds.successBg, ds.successFg));
      case 'debt':
        return (Icons.account_balance_wallet_rounded, (ds.dangerBg, ds.dangerFg));
      default:
        return (Icons.notifications_rounded, (ds.primarySoft, ds.primarySoftFg));
    }
  }

  String _fmtDate(String iso) {
    final dt = DateTime.tryParse(iso);
    if (dt == null) return iso;
    final l = dt.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(l.day)}.${two(l.month)}.${l.year} · ${two(l.hour)}:${two(l.minute)}';
  }
}
